# Local API reference

The complete generated schema is available while Northstar is running at <http://127.0.0.1:8000/docs>. This document covers the supported personal research workflows and the behavior that is easy to miss from an endpoint list.

Base URL:

```text
http://127.0.0.1:8000
```

## Authentication

The personal UI logs in automatically. For PowerShell/API use, request a loopback token:

```powershell
$login = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/auth/local

$headers = @{
  Authorization = "Bearer $($login.access_token)"
}
```

`POST /auth/local` is only accepted from loopback. Its JWT lasts eight hours. All examples below assume `$headers` is present.

Public utility endpoints:

- `GET /` — basic API status;
- `GET /snapshots/health` — launcher/UI health check;
- `POST /auth/local` — loopback personal login;
- `POST /auth/register` and `POST /auth/login` — retained account-based paths.

Most other endpoints require `Authorization: Bearer <token>`.

## Scan and job endpoints

### Submit any public URL

`POST /ingest/url`

```powershell
$scan = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ingest/url `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"url":"https://example-store.com"}'

$scan
```

The response contains:

- `id`: source URL ID;
- `store_id` when the submitted URL was classified as a store root;
- `type`;
- `job_id`; and
- `status`.

Submitting the same normalized source again reuses it and queues a rescan. A store-root task then queues homepage and sitemap child jobs; the parent job completing does not mean the entire catalog has finished.

### Inspect a job

`GET /ingest/jobs/{job_id}`

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/ingest/jobs/$($scan.job_id)" `
  -Headers $headers
```

Jobs are in-memory. After an API restart, an old ID returns `status: unknown` even though already persisted scan data remains.

### Explicit store submission

`POST /ingest/store`

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ingest/store `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"domain":"example-store.com"}'
```

The general `/ingest/url` path is preferred because it performs URL normalization and classification.

## Store Intelligence Report

### Build/get the report

`GET /intelligence/stores/{store_id}`

```powershell
$report = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/intelligence/stores/$($scan.store_id)" `
  -Headers $headers

$report.executive_summary
```

The response contains:

- `report_version` and `generated_at`;
- normalized `store` identity;
- `executive_summary` and headline metrics;
- `traffic` periods and trend;
- product intelligence rows;
- ads;
- offers/funnel;
- technology;
- evidence/assumptions; and
- diagnostics.

Each metric follows the same typed insight contract: available range/classification/score or explicit insufficient data, confidence, evidence, assumptions, missing signals, explanation, and estimator version.

Important: this GET creates a new immutable analysis run and persists its derived insights/evidence links. It does not rewrite an earlier completed run.

### Explicit recompute

`POST /intelligence/stores/{store_id}/recompute`

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/intelligence/stores/$($scan.store_id)/recompute" `
  -Headers $headers
```

This exposes an explicit recalculation action. The current GET path also calculates and persists a new immutable run, so recompute does not currently differ by using a cached report.

### Evidence ledger

`GET /intelligence/stores/{store_id}/evidence`

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/intelligence/stores/$($scan.store_id)/evidence" `
  -Headers $headers
```

Returns up to 1,000 newest normalized evidence records with typed source relationships, independence group, values, reliability/confidence, contradiction flag, observation/retrieval/freshness times, and collector version.

## Store identities

### List candidates

`GET /intelligence/stores/{store_id}/identities`

```powershell
$identities = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/intelligence/stores/$($scan.store_id)/identities" `
  -Headers $headers

$identities
```

Candidates can include brand, Facebook, and Instagram values extracted from the public homepage. Meta advertiser/page identities can also be represented, but automatic candidate search is not complete.

### Confirm or unconfirm

`PATCH /intelligence/stores/{store_id}/identities/{identity_id}`

```powershell
Invoke-RestMethod `
  -Method Patch `
  -Uri "http://127.0.0.1:8000/intelligence/stores/$($scan.store_id)/identities/$($identities[0].id)" `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"confirmed":true}'
```

Only confirm an identity you have verified. A confirmed `meta_page` or `meta_advertiser` normalized identity can participate in store/ad matching.

## Estimation settings

### List profiles

`GET /intelligence/settings`

```powershell
$profiles = Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/intelligence/settings `
  -Headers $headers
```

Calling the endpoint creates the disclosed general default profile if none exists.

### Create a new active profile version

`PUT /intelligence/settings/{category_key}`

```powershell
$settingsBody = @{
  name = "Personal planning assumptions"
  conversion_rate_low = 0.005
  conversion_rate_central = 0.012
  conversion_rate_high = 0.025
  basket_multiplier_low = 1.0
  basket_multiplier_central = 1.15
  basket_multiplier_high = 1.5
  traffic_reliability_low = 0.70
  traffic_reliability_central = 1.0
  traffic_reliability_high = 1.40
  freshness_limit_days = 45
  minimum_evidence_count = 2
  score_weights = @{
    advertising = 0.30
    reviews = 0.25
    merchandising = 0.15
    inventory = 0.15
    persistence = 0.10
    offer_page = 0.05
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Method Put `
  -Uri http://127.0.0.1:8000/intelligence/settings/general_ecommerce `
  -Headers $headers `
  -ContentType application/json `
  -Body $settingsBody
```

The update is partial: omitted fields inherit the currently active category profile, or the general profile when creating a category profile. Saving creates a new row/version and deactivates the prior active version for that category.

Validation includes:

- ordered low ≤ central ≤ high ranges;
- conversion values from 0 to 1;
- positive basket values no greater than 20;
- traffic multipliers no greater than 5 with high at least 1;
- freshness from 1 to 365 days;
- exactly six known score-weight keys, each 0–1, totaling 1; and
- minimum evidence no greater than enabled weight groups.

Advanced `thresholds` keys are `minimum_sellable_products`, `traffic_monthly_direction`, `traffic_endpoint_direction`, and `momentum_minimum_span_days`.

## Similarweb traffic

### Integration status

`GET /integrations/similarweb/status`

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/integrations/similarweb/status `
  -Headers $headers
```

The full key is never returned.

### Save/remove local credential

`PUT /integrations/similarweb/config`

```powershell
Invoke-RestMethod `
  -Method Put `
  -Uri http://127.0.0.1:8000/integrations/similarweb/config `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"api_key":"your-key"}'
```

`DELETE /integrations/similarweb/config` removes only the local-file credential. An environment value remains active.

### Test without persistence

`POST /integrations/similarweb/test`

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/integrations/similarweb/test `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"domain":"example-store.com","country":"world"}'
```

The omitted period defaults to the previous completed month. The test calls both provider endpoints, can consume provider credits, does not persist a snapshot, and does not use the 24-hour traffic cache.

### Refresh a collected store

`POST /traffic/stores/{store_id}/refresh`

```powershell
$trafficBody = @{
  start_date = "2026-06"
  end_date = "2026-06"
  country = "world"
  main_domain_only = $true
  force = $false
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/traffic/stores/$($scan.store_id)/refresh" `
  -Headers $headers `
  -ContentType application/json `
  -Body $trafficBody
```

The range accepts `YYYY-MM` and is limited to 12 months. Normal successful/partial exact-scope snapshots are cached for 24 hours. Set `force` only when a deliberate new provider request is worth the credit cost.

History:

- `GET /traffic/stores/{store_id}?limit=24`
- `POST /traffic/domains/{domain}/refresh`
- `GET /traffic/domains/{domain}?limit=24`

## Meta Ad Library

### Integration status

`GET /integrations/meta/status`

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/integrations/meta/status `
  -Headers $headers
```

### Save/remove local credential

`PUT /integrations/meta/config`

```powershell
Invoke-RestMethod `
  -Method Put `
  -Uri http://127.0.0.1:8000/integrations/meta/config `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"access_token":"your-token"}'
```

`DELETE /integrations/meta/config` removes only the local-file credential.

### Test without persistence

`POST /integrations/meta/test`

```powershell
$metaTest = @{
  search_terms = "Example Brand"
  ad_reached_countries = @("GB")
  ad_type = "ALL"
  limit = 5
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/integrations/meta/test `
  -Headers $headers `
  -ContentType application/json `
  -Body $metaTest
```

This makes a real provider request but does not persist ads.

### Search and persist

`POST /ads/meta/search`

```powershell
$metaSearch = @{
  search_terms = "Example Brand"
  ad_reached_countries = @("GB")
  ad_type = "ALL"
  ad_active_status = "ALL"
  limit = 50
} | ConvertTo-Json

$result = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ads/meta/search `
  -Headers $headers `
  -ContentType application/json `
  -Body $metaSearch

$result.ads
```

The request requires search terms or numeric `search_page_ids`, one to 25 reached-country values, and a limit from 1 to 500. Optional delivery dates use `YYYY-MM-DD`.

Imported list/detail endpoints:

- `GET /ads?platform=meta&official_only=true&sort=newest`
- `GET /ads/{ad_id}`

The older `POST /ingest/meta-ads-search` path queues the same provider collection in the volatile background runner.

## GetHookd ad discovery

### Integration status and credential

- `GET /integrations/gethookd/status`
- `PUT /integrations/gethookd/config`
- `DELETE /integrations/gethookd/config`

```powershell
Invoke-RestMethod `
  -Method Put `
  -Uri http://127.0.0.1:8000/integrations/gethookd/config `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"api_token":"your-public-api-token"}'
```

The token must have GetHookd `explore:read` access. Environment-managed
`GETHOOKD_API_TOKEN` takes precedence over a locally saved credential.

### Live Explore search

`POST /ads/gethookd/search`

```powershell
$gethookdSearch = @{
  query = "portable blender"
  platform = "facebook"
  status = "active"
  ad_format = "video"
  minimum_days_active = 14
  limit = 30
  sort_column = "days_active"
  sort_direction = "desc"
} | ConvertTo-Json

$result = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ads/gethookd/search `
  -Headers $headers `
  -ContentType application/json `
  -Body $gethookdSearch

$result.ads
$result.used_credits
$result.remaining_credits
```

Supported platform values are `facebook`, `instagram`, `tiktok`, and `google`;
status is `active` or `inactive`; formats are `image`, `video`, or `carousels`.
The limit is 1–100. Results are normalized and returned live but are not persisted.
Provider scores and classifications are signals, not verified profitability metrics.

## Northstar public-ad library

`POST /ingest/ad` saves public ad evidence directly to the personal Northstar
library. It does not fetch or scrape the source platform.

```powershell
$publicAd = @{
  platform = "tiktok"
  source_url = "https://ads.tiktok.com/business/creativecenter/..."
  advertiser_name = "Example merchant"
  headline = "Portable blender demonstration"
  ad_text = "Visible public ad copy"
  creative_type = "video"
  creative_urls = @("https://cdn.example.com/creative.mp4")
  landing_url = "https://merchant.example/products/blender"
  cta = "Shop now"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/ingest/ad `
  -Headers $headers `
  -ContentType application/json `
  -Body $publicAd
```

Platforms are `meta`, `tiktok`, `google`, or `manual`. Creative types are
`image`, `video`, `carousel`, or `unknown`. At least one public source URL,
creative URL, or landing URL is required. The saved record is labeled
`northstar_manual` / `manual_public_import` rather than as an official provider
record.

Extension captures may also send `capture_metadata` with `adapter_id`,
`adapter_version`, `confidence`, `warnings`, and `captured_fields`. These records use
the `browser_extension_capture` source type. Reposting the same normalized public
source URL updates the existing Northstar manual record rather than creating another
ad or duplicate landing edge.

The bundled Chrome/Edge extension calls this same endpoint after obtaining the local
single-user token from `POST /auth/local`. CORS accepts Chrome extension origins while
the extension manifest restricts network access to Northstar's loopback API.

Use `GET /ads?sort=newest`, optionally with `query`, `platform`, or `provider`,
to search durable records. `official_only=true` returns only official Meta API
imports.

`GET /ads/facets` returns saved metric keys and geographies plus their ad-ID mappings.
It reads only the local database and never calls Meta, GetHookd, or another provider.

### Ad metric observations and Analytics

- `GET /ads/{ad_id}/metrics` lists source-scoped metric observations.
- `POST /ads/{ad_id}/metrics` adds one observation.
- `GET /ads/{ad_id}/analytics` returns saved metrics, Northstar/provider observations,
  explicit unavailable competitor metrics, and the data-use notice.
- `GET /ads/{ad_id}/autopsy` returns the saved ad, analytics, landing collection
  state, resolved store/products, related saved ads with match reasons, and an
  evidence-gated conclusion. It also reports saved-media, transcript, and OCR states;
  related ads can match through the same resolved product across different landings.

```powershell
$metric = @{
  metric_key = "reach"
  value_kind = "range"
  range_low = 10000
  range_high = 50000
  unit = "people"
  provider = "manual_public_source"
  source_type = "manual_public_capture"
  geography = "US"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/ads/$adId/metrics" `
  -Headers $headers `
  -ContentType application/json `
  -Body $metric
```

`value_kind` is one of `exact`, `reported_value`, `range`, `percentile`,
`classification`, or `unavailable`. Exact requires `value_numeric`; ranges require
ordered low/high values; other kinds require numeric or textual evidence. An ad may
also include up to 25 metric objects in the original `POST /ingest/ad` body.

## Product test economics

- `GET /products/{product_id}/economics` lists active named scenarios.
- `GET /products/{product_id}/economics?include_history=true` includes superseded and
  archived revisions.
- `POST /products/{product_id}/economics` creates a scenario.
- `PUT /products/{product_id}/economics/{scenario_id}` supersedes the active revision
  with a new immutable revision.
- `DELETE /products/{product_id}/economics/{scenario_id}` archives a scenario.

Inputs include selling price; low/high product, shipping, fulfillment, and other
variable cost; payment fee rate/fixed fee; refund allowance rate; and target margin.
Rates use decimal fractions (`0.029` means 2.9%). Results return contribution,
break-even CPA/ROAS, target CPA/ROAS, sensitivity status, `unit-economics-v1`, and the
formula notice. Every stored scenario is labeled `user_entered`.

```powershell
$scenario = @{
  name = "Conservative test"
  currency = "USD"
  selling_price = 49.99
  product_cost_low = 11
  product_cost_high = 16
  shipping_cost_low = 3
  shipping_cost_high = 6
  payment_fee_rate = 0.029
  payment_fee_fixed = 0.30
  refund_allowance_rate = 0.05
  target_profit_margin = 0.20
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/products/$productId/economics" `
  -Headers $headers -ContentType application/json -Body $scenario
```

Manual economics are planning assumptions, not proof of supplier cost, competitor
margin, ad performance, or product profitability.

## Investigation shortlist

- `GET /investigations` lists active items. Optional filters are `entity_type`,
  `entity_id`, and `workflow_stage`; `include_archived=true` includes history.
- `POST /investigations` idempotently adds a store, product, or ad.
- `PUT /investigations/{item_id}` updates workflow, decision, priority, thesis, risks,
  next action, and optional evidence IDs.
- `DELETE /investigations/{item_id}` archives the item.

Entity types are `store`, `product`, and `ad`. Workflow stages are `inbox`,
`researching`, `ready_to_test`, `testing`, `decided`, and `archived`. Decisions are
`undecided`, `investigate`, `test`, or `reject`. Evidence IDs are validated against
the current workspace; an invalid or cross-workspace citation is rejected.

```powershell
$item = @{
  entity_type = "product"
  entity_id = $productId
  workflow_stage = "researching"
  decision = "investigate"
  priority = "high"
  thesis = "The offer may justify a controlled test."
  risks = "Supplier and review evidence are missing."
  next_action = "Build a conservative economics scenario."
  evidence_ids = @()
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/investigations" `
  -Headers $headers -ContentType application/json -Body $item
```

Shortlist decisions are user-authored research state, not Northstar estimates.

## Product comparison

`GET /comparisons/products?ids=1,2` compares between two and five products in the
current workspace. It returns observed catalog fields, collected related-ad and
evidence counts, the latest active user-entered economics scenario, explicit unknowns,
known-corpus counts, and the data-use notice.

The endpoint rejects missing or cross-workspace product IDs. Collection span is not
product age, collected ad count is not worldwide ad coverage, and economics remain
user-entered. The frontend `/compare` workspace exports this response as JSON.

## Research dossier export

`GET /exports/investigations/{item_id}` returns `research-dossier-v1` JSON and an
attachment filename. It combines the investigation notes and citations with the
current Store Intelligence Report, Ad Autopsy, or product dossier. Product dossiers
include up to 25 recent snapshots, active user-entered economics, related collected
ads, normalized evidence, and explicit unavailable dimensions. Workspace isolation is
enforced before entity data or citations are returned.

## Compatibility/read endpoints

The UI still uses these collection-oriented endpoints:

- `GET /library` — local summary, stores, products, sources, jobs, and traffic compatibility payload;
- `GET /stores` and `GET /stores/{id}`;
- `GET /stores/{id}/history`;
- `GET /products` and `GET /products/{id}`;
- `GET /products/{id}/history`;
- `GET /graph/product/{id}`;
- signal/score, tracking, recompute, and alert endpoints retained for compatibility.

The `/library`, legacy Signal, and legacy Score contracts are not the primary intelligence API. Use `/intelligence/stores/{id}` for decision-facing data.

## Error interpretation

- 401: token missing/expired/invalid; obtain a new local token.
- 403 on a scan: crawler rejected a non-public destination or `robots.txt` disallowed it.
- 404: store/product/identity does not exist in the current workspace.
- 409: required provider credential is not configured.
- 413 in diagnostics: public response exceeded the configured byte limit.
- 422: URL/body/settings validation failed.
- 502 from provider paths: Meta or another upstream request returned a normalized error.

Never turn an empty provider response, failed fetch, or 404 into a business conclusion. Inspect the returned detail and report missing signals.
