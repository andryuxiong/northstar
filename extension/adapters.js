(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.NorthstarAdapters = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const VERSION = "capture-adapters-v1";
  const CTA_PATTERN = /^(shop now|learn more|buy now|get offer|sign up|download|apply now|book now|order now)$/i;

  function clean(value, max = 2000) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, max);
  }

  function host(rawUrl) {
    try { return new URL(rawUrl).hostname.toLowerCase(); } catch { return ""; }
  }

  function platform(rawUrl) {
    const value = host(rawUrl);
    if (value.includes("facebook.com") || value.includes("instagram.com")) return "meta";
    if (value.includes("tiktok.com")) return "tiktok";
    if (value.includes("google.com")) return "google";
    return "manual";
  }

  function unwrapRedirect(rawUrl) {
    try {
      const url = new URL(rawUrl);
      if (url.hostname.endsWith("facebook.com") && url.pathname.includes("/l.php")) {
        return url.searchParams.get("u") || rawUrl;
      }
      if (url.hostname === "www.google.com" && url.pathname === "/url") {
        return url.searchParams.get("q") || url.searchParams.get("url") || rawUrl;
      }
    } catch { /* Keep the public URL as captured. */ }
    return rawUrl;
  }

  function externalLink(nodes, sourceHost) {
    for (const node of nodes) {
      if (!node.href) continue;
      const candidate = unwrapRedirect(node.href);
      const candidateHost = host(candidate);
      if (candidateHost && candidateHost !== sourceHost && !candidateHost.endsWith("facebook.com") && !candidateHost.endsWith("tiktok.com") && !candidateHost.endsWith("google.com")) return candidate;
    }
    return "";
  }

  function media(nodes) {
    const candidates = nodes.filter((node) => node.src && ["IMG", "VIDEO", "SOURCE"].includes(node.tag));
    candidates.sort((left, right) => ((right.width || 0) * (right.height || 0)) - ((left.width || 0) * (left.height || 0)));
    const chosen = candidates[0];
    return chosen ? { creativeUrl: chosen.src, creativeType: chosen.tag === "VIDEO" || chosen.mediaParent === "VIDEO" ? "video" : "image" } : { creativeUrl: "", creativeType: "unknown" };
  }

  function textCandidates(nodes) {
    return nodes.map((node) => clean(node.text, 1000)).filter((text) => text.length >= 2);
  }

  function labeledValue(nodes, labels) {
    const normalized = labels.map((label) => label.toLowerCase());
    for (let index = 0; index < nodes.length; index += 1) {
      const text = clean(nodes[index].text, 300);
      const lower = text.toLowerCase();
      for (const label of normalized) {
        if (lower.startsWith(`${label}:`)) return clean(text.slice(label.length + 1), 300);
        if (lower === label && nodes[index + 1]) return clean(nodes[index + 1].text, 300);
      }
    }
    return "";
  }

  function extract(snapshot) {
    const nodes = Array.isArray(snapshot.nodes) ? snapshot.nodes : [];
    const texts = textCandidates(nodes);
    const detectedPlatform = platform(snapshot.url);
    const selected = clean(snapshot.selectedText, 5000);
    const selectedLines = selected.split(/\r?\n/).map((line) => clean(line, 500)).filter(Boolean);
    const headings = nodes.filter((node) => /^H[1-4]$/.test(node.tag)).map((node) => clean(node.text, 500)).filter(Boolean);
    const cta = texts.find((text) => CTA_PATTERN.test(text)) || "";
    const sourceHost = host(snapshot.url);
    const mediaResult = media(nodes);
    const warnings = [];
    let advertiser = "";
    let adapterId = "generic_selection";

    if (detectedPlatform === "meta") {
      adapterId = "meta_ad_library";
      advertiser = labeledValue(nodes, ["advertiser", "page name"]) || clean(nodes.find((node) => node.href && host(node.href).endsWith("facebook.com") && !node.href.includes("/ads/library") && clean(node.text).length > 1)?.text, 255);
    } else if (detectedPlatform === "tiktok") {
      adapterId = "tiktok_creative_center";
      advertiser = labeledValue(nodes, ["advertiser", "brand", "account"]);
    } else if (detectedPlatform === "google") {
      adapterId = "google_ads_transparency";
      advertiser = labeledValue(nodes, ["advertiser name", "advertiser"]);
    }

    const headline = clean(selectedLines.find((line) => line.length <= 160) || headings[0] || "", 500);
    const landingUrl = externalLink(nodes, sourceHost);
    if (!selected) warnings.push("No selected text was found; copy may be partial or absent.");
    if (!advertiser) warnings.push("Advertiser was not identified confidently; review it manually.");
    if (!landingUrl) warnings.push("No external landing destination was identified.");
    if (!mediaResult.creativeUrl) warnings.push("No public creative asset URL was identified.");

    const capturedFields = [
      ["ad_text", selected], ["advertiser_name", advertiser], ["headline", headline],
      ["cta", cta], ["creative_url", mediaResult.creativeUrl], ["landing_url", landingUrl],
    ].filter(([, value]) => Boolean(value)).map(([key]) => key);

    return {
      adapterId,
      adapterVersion: VERSION,
      platform: detectedPlatform,
      confidence: capturedFields.length >= 5 ? "high" : capturedFields.length >= 3 ? "medium" : "low",
      warnings,
      capturedFields,
      fields: {
        sourceUrl: snapshot.url || "",
        advertiser,
        headline,
        adText: selected,
        cta,
        creativeUrl: mediaResult.creativeUrl,
        creativeType: mediaResult.creativeType,
        landingUrl,
      },
    };
  }

  return { VERSION, extract, platformForUrl: platform, unwrapRedirect };
});
