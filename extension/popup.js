const API_URL = "http://127.0.0.1:8000";

const byId = (id) => document.getElementById(id);
const fields = {
  platform: byId("platform"),
  creativeType: byId("creative-type"),
  sourceUrl: byId("source-url"),
  advertiser: byId("advertiser"),
  headline: byId("headline"),
  adText: byId("ad-text"),
  cta: byId("cta"),
  creativeUrl: byId("creative-url"),
  landingUrl: byId("landing-url"),
  impressions: byId("impressions"),
  reach: byId("reach"),
  likes: byId("likes"),
  comments: byId("comments"),
  shares: byId("shares"),
  ctr: byId("ctr"),
  metricGeography: byId("metric-geography"),
};

function setMessage(message, tone = "") {
  const element = byId("message");
  element.textContent = message;
  element.className = `message ${tone}`.trim();
}

let latestCapture = null;

function capturePageSnapshot() {
  const selectedText = window.getSelection?.().toString().trim() || "";
  const selection = window.getSelection?.();
  const node = selection?.anchorNode;
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  const container = element?.closest?.("article, [role='article'], section") || element?.parentElement;
  const primaryRoot = container || document;
  const selector = "a[href], img[src], video, video source[src], button, [role='button'], h1, h2, h3, h4, [data-testid], [aria-label]";
  let candidates = Array.from(primaryRoot.querySelectorAll?.(selector) || []);
  if (container && candidates.length < 12) candidates = candidates.concat(Array.from(document.querySelectorAll(selector)));
  const seen = new Set();
  const nodes = [];
  for (const candidate of candidates) {
    if (seen.has(candidate) || nodes.length >= 500) continue;
    seen.add(candidate);
    const rect = candidate.getBoundingClientRect?.() || { width: 0, height: 0 };
    const parentTag = candidate.parentElement?.tagName || "";
    nodes.push({
      tag: candidate.tagName || "",
      text: (candidate.innerText || candidate.textContent || candidate.getAttribute?.("aria-label") || "").trim().slice(0, 1000),
      href: candidate.href || "",
      src: candidate.currentSrc || candidate.src || candidate.getAttribute?.("src") || "",
      ariaLabel: candidate.getAttribute?.("aria-label") || "",
      dataTestId: candidate.getAttribute?.("data-testid") || "",
      className: typeof candidate.className === "string" ? candidate.className.slice(0, 500) : "",
      width: Math.round(rect.width || 0),
      height: Math.round(rect.height || 0),
      mediaParent: parentTag,
    });
  }

  return {
    url: window.location.href,
    title: document.title || "",
    selectedText,
    nodes,
  };
}

function renderCapturePreview(capture) {
  latestCapture = capture;
  const preview = byId("capture-preview");
  preview.hidden = false;
  byId("adapter-name").textContent = `${capture.adapterId.replaceAll("_", " ")} · ${capture.adapterVersion}`;
  const confidence = byId("adapter-confidence");
  confidence.textContent = `${capture.confidence} confidence`;
  confidence.className = `confidence ${capture.confidence}`;
  byId("captured-fields").textContent = capture.capturedFields.length
    ? `Captured: ${capture.capturedFields.map((field) => field.replaceAll("_", " ")).join(", ")}.`
    : "No structured fields were captured.";
  const warnings = byId("capture-warnings");
  warnings.replaceChildren(...capture.warnings.map((warning) => {
    const item = document.createElement("li");
    item.textContent = warning;
    return item;
  }));
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function capturePage() {
  setMessage("Capturing the active public page…");
  try {
    const tab = await activeTab();
    if (!tab?.id || !/^https?:/i.test(tab.url || "")) {
      throw new Error("Open a public HTTP or HTTPS ad page first.");
    }
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: capturePageSnapshot,
    });
    const capture = NorthstarAdapters.extract(result || { url: tab.url, nodes: [] });
    const captured = capture.fields;
    fields.sourceUrl.value = captured.sourceUrl || tab.url || "";
    fields.platform.value = capture.platform;
    if (captured.adText) fields.adText.value = captured.adText;
    if (captured.advertiser) fields.advertiser.value = captured.advertiser;
    if (captured.headline) fields.headline.value = captured.headline;
    if (captured.cta) fields.cta.value = captured.cta;
    if (captured.creativeUrl) fields.creativeUrl.value = captured.creativeUrl;
    if (captured.landingUrl) fields.landingUrl.value = captured.landingUrl;
    fields.creativeType.value = captured.creativeType || "unknown";
    renderCapturePreview(capture);
    setMessage(
      capture.warnings.length
        ? "Partial capture. Review the warnings and every field before saving."
        : "Structured capture ready. Review every field before saving.",
    );
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "The page could not be captured.", "error");
  }
}

async function localToken(force = false) {
  if (!force) {
    const stored = await chrome.storage.local.get("northstarToken");
    if (stored.northstarToken) return stored.northstarToken;
  }
  const response = await fetch(`${API_URL}/auth/local`, { method: "POST" });
  if (!response.ok) throw new Error("Northstar local login failed.");
  const payload = await response.json();
  await chrome.storage.local.set({ northstarToken: payload.access_token });
  return payload.access_token;
}

async function apiRequest(path, options, retry = true) {
  const token = await localToken(false);
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  if (response.status === 401 && retry) {
    await localToken(true);
    return apiRequest(path, options, false);
  }
  if (!response.ok) {
    let message = `Northstar returned HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") message = payload.detail;
      else if (Array.isArray(payload.detail)) message = payload.detail[0]?.msg || message;
    } catch {
      // Keep the status-based fallback.
    }
    throw new Error(message);
  }
  return response.json();
}

async function checkConnection() {
  const element = byId("connection");
  try {
    const response = await fetch(`${API_URL}/snapshots/health`);
    if (!response.ok) throw new Error();
    element.textContent = "Connected";
    element.className = "connection connected";
  } catch {
    element.textContent = "Offline";
    element.className = "connection offline";
    setMessage("Start Northstar before saving this capture.", "error");
  }
}

byId("recapture").addEventListener("click", capturePage);
byId("capture-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const saveButton = byId("save");
  saveButton.disabled = true;
  setMessage("Saving to your local Northstar library…");
  try {
    const metricProvider = {
      meta: "meta_ad_library",
      tiktok: "tiktok_creative_center",
      google: "google_ads_transparency",
      manual: "manual_public_source",
    }[fields.platform.value];
    const metrics = [
      ["impressions", fields.impressions.value],
      ["reach", fields.reach.value],
      ["likes", fields.likes.value],
      ["comments", fields.comments.value],
      ["shares", fields.shares.value],
      ["ctr", fields.ctr.value],
    ]
      .filter(([, value]) => value.trim())
      .map(([metricKey, value]) => ({
        metric_key: metricKey,
        value_kind:
          metricKey === "ctr" && /(top|percentile)/i.test(value)
            ? "percentile"
            : "reported_value",
        value_text: value.trim(),
        unit: metricKey === "ctr" ? "provider_reported_ctr" : "count",
        provider: metricProvider,
        source_type: "manual_public_capture",
        geography: fields.metricGeography.value.trim() || null,
      }));
    const ad = await apiRequest("/ingest/ad", {
      method: "POST",
      body: JSON.stringify({
        platform: fields.platform.value,
        source_url: fields.sourceUrl.value || null,
        advertiser_name: fields.advertiser.value.trim() || null,
        headline: fields.headline.value.trim() || null,
        ad_text: fields.adText.value.trim() || null,
        creative_type: fields.creativeType.value,
        creative_urls: fields.creativeUrl.value ? [fields.creativeUrl.value] : null,
        landing_url: fields.landingUrl.value || null,
        cta: fields.cta.value.trim() || null,
        metrics,
        capture_metadata: latestCapture ? {
          adapter_id: latestCapture.adapterId,
          adapter_version: latestCapture.adapterVersion,
          confidence: latestCapture.confidence,
          warnings: latestCapture.warnings,
          captured_fields: latestCapture.capturedFields,
        } : null,
      }),
    });
    setMessage(`Saved as Northstar ad #${ad.id}.`, "success");
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "The ad could not be saved.", "error");
  } finally {
    saveButton.disabled = false;
  }
});

checkConnection();
capturePage();
