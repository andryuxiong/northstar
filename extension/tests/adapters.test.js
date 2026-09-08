const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const adapters = require("../adapters.js");

function fixture(name) {
  return JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", `${name}.json`), "utf8"));
}

for (const [name, adapterId, platform, advertiser, landingHost] of [
  ["meta", "meta_ad_library", "meta", "BlendGo", "blendgo.example"],
  ["tiktok", "tiktok_creative_center", "tiktok", "CleanFast", "cleanfast.example"],
  ["google", "google_ads_transparency", "google", "Deskly LLC", "deskly.example"],
]) {
  test(`${name} snapshot uses its versioned adapter`, () => {
    const result = adapters.extract(fixture(name));
    assert.equal(result.adapterId, adapterId);
    assert.equal(result.adapterVersion, "capture-adapters-v1");
    assert.equal(result.platform, platform);
    assert.equal(result.fields.advertiser, advertiser);
    assert.equal(new URL(result.fields.landingUrl).hostname, landingHost);
    assert.ok(result.fields.creativeUrl);
    assert.ok(result.capturedFields.includes("landing_url"));
  });
}

test("partial generic capture warns instead of guessing missing fields", () => {
  const result = adapters.extract({ url: "https://example.org/ad", selectedText: "", nodes: [] });
  assert.equal(result.adapterId, "generic_selection");
  assert.equal(result.confidence, "low");
  assert.equal(result.fields.advertiser, "");
  assert.ok(result.warnings.length >= 3);
});
