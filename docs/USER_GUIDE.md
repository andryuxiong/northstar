# Northstar personal-use guide

Northstar is a local, single-user e-commerce research application. It collects public storefront observations, can import provider data from Similarweb and Meta when you supply credentials, and builds an evidence-backed Store Intelligence Report. It has no subscriptions, billing, plans, usage credits, teams, or artificial scan quotas of its own.

Northstar does not provide private merchant analytics. A storefront scan alone cannot reveal exact visitors, orders, sales, revenue, ad performance, product costs, or profit. Unsupported conclusions remain `insufficient data`.

## 1. Requirements

The supported personal setup is Windows with PowerShell. Install:

- Python 3.10 or newer and make sure `python` works in PowerShell.
- A current Node.js/npm release supported by Vite 8. The implementation was exercised with Python 3.10 and Node 25.
- Internet access for public storefront scans and any provider requests.

Docker is not required or recommended for the normal personal workflow. The application already uses:

- a local SQLite database;
- a bounded in-process background worker;
- local snapshot files; and
- a Vite development server bound to the loopback interface.

You do not need PostgreSQL, Redis, Celery, or a container runtime.

## 2. Start and stop Northstar

Open PowerShell and run:

```powershell
cd C:\Users\andre\Desktop\dropship-intel-mvp
.\start-northstar.ps1
```

On the first run, the launcher:

1. creates `backend/.venv` if it does not exist;
2. installs the pinned Python packages from `backend/requirements.txt`;
3. installs frontend packages if `frontend/node_modules` does not exist;
4. starts FastAPI at `127.0.0.1:8000`;
5. starts Vite at `127.0.0.1:5173`;
6. waits for both processes to become healthy; and
7. opens the UI in Chrome or the default browser.

The launcher also upgrades the database schema safely before the API begins serving requests. See [Operations and troubleshooting](OPERATIONS.md#database-migrations) for the migration and backup behavior.

To stop both processes:

```powershell
.\stop-northstar.ps1
```

Stopping the app preserves the SQLite database, snapshots, provider imports, settings, and evidence. Background jobs themselves are held in memory, so a job that was still running or queued must be submitted again after a restart.

Useful addresses:

- Northstar UI: <http://127.0.0.1:5173>
- OpenAPI/Swagger UI: <http://127.0.0.1:8000/docs>
- API health check: <http://127.0.0.1:8000/snapshots/health>

## 3. What Northstar's labels mean

The application distinguishes the origin of a value:

- **Observed**: fetched from a public store page by the local crawler.
- **Imported**: returned by an official external provider, currently Meta's Graph API.
- **Provider estimate**: modeled by the provider, currently Similarweb traffic. It is not first-party analytics.
- **Northstar estimate**: calculated as a versioned range from disclosed observations and editable assumptions.
- **Insufficient data**: no responsible value is published because a required input or evidence gate is missing.

A high metric value is not the same as high confidence. For example, a product can eventually have a high momentum evidence score with low confidence because its supporting history is short or sparse.

## 4. Scan a public store

From **Overview**, choose **Investigate a store** or **Scan store**. You can also use **Scan a store** from **Stores & traffic**.

Paste a public URL, for example:

```text
https://example-store.com
```

You may omit the scheme; the UI adds `https://`. Northstar accepts public HTTP or HTTPS URLs only.

For a store root URL, Northstar immediately creates or reuses the store record, opens its report, and queues collection of:

- the homepage;
- `https://<domain>/sitemap.xml`;
- product links found on the homepage;
- Shopify product sitemap entries and nested same-domain sitemaps; and
- product pages discovered from those sources.

The report may initially show missing data while the background queue is still working. Refresh the report after collection completes. The **Diagnostics** tab shows source states, HTTP results, snapshot counts, recent matching jobs, and collection failures.

### Other accepted URL types

- A direct product URL collects that product and creates its store if necessary.
- A collection or landing-page URL saves the page and queues product links found on it.
- A sitemap URL parses same-domain product and nested sitemap locations.

The store-root workflow is the most complete entry point. Product keyword, product image, brand-only, niche-only, and ad-identifier discovery are future entry modes, not current UI features.

### What the scan can observe

Depending on the storefront markup, Northstar can collect:

- canonical product URLs, names, descriptions, prices, currencies, availability, variants, and images;
- Shopify product JSON and generic structured product metadata;
- content-hashed HTML and normalized JSON snapshots;
- brand candidates from schema, Open Graph, title, logo text, and domain;
- linked Facebook and Instagram identities;
- platform and selected technology patterns;
- homepage offer text and conversion/funnel patterns;
- product links promoted on the homepage; and
- changes across repeated observations.

Storefront parsing is best-effort. A field absent from the page remains absent. Northstar does not bypass authentication, CAPTCHAs, bot challenges, access controls, robots directives, or private Shopify analytics.

### Repeated scans

Choose **New scan** in a store report or submit the same URL again. Existing source records are reused and queued for a new fetch. Historical snapshots remain stored.

Repeated scans are important for trend evidence, but rapidly rescanning the same page does not manufacture momentum. Product momentum requires at least two independent evidence groups and at least 14 days of observation history. Current persistence and restock signals additionally require observations on at least three distinct days; persistence is only added after a 30-day span.

## 5. Read the Store Intelligence Report

Store reports use stable URLs:

```text
/stores/<store-id>/overview
/stores/<store-id>/products
/stores/<store-id>/traffic
/stores/<store-id>/ads
/stores/<store-id>/offers
/stores/<store-id>/technology
/stores/<store-id>/evidence
/stores/<store-id>/diagnostics
```

### Overview

The Overview is the decision screen. It shows:

- a short verdict;
- the strongest available evidence;
- the largest uncertainty;
- the recommended next investigation;
- store identity, platform, category, market, and catalog count when detected;
- monthly visits, AOV, monthly orders, gross monthly revenue, momentum, ad status, and dropshipping likelihood; and
- overall evidence confidence.

Open **Inspect basis** on a metric to see its range or classification, evidence, assumptions, missing signals, explanation, confidence, and estimator version.

Do not interpret **Little evidence of meaningful demand** as proof that the store has no demand. It means Northstar currently has little evidence. When traffic is missing, orders and revenue are intentionally withheld.

### Products

The sidebar's **Product discovery** destination uses `/shopify-product` (the
older `/products` URL remains compatible). It searches the products Northstar
has actually collected across your stores, with images, store, price,
availability, variant, observation-date, sorting, saved-view, and CSV controls. It is a
known-corpus explorer, not a global product or sales database.

The product table prioritizes product demand evidence instead of raw variant counts or fetch times. It can show current price, first seen, momentum, related ad state, reviews, estimated contribution, saturation, supplier match, margin, reasons, uncertainty, and confidence.

### Plan product test economics

Open a product from **Observed products**, then use **Test economics** in the product
drawer. Create one or more named scenarios and enter your own selling price, low/high
product and shipping cost, fulfillment and other variable costs, payment fee, refund
allowance, and target profit margin.

Northstar calculates pre-ad contribution, break-even CPA/ROAS, target CPA/ROAS, and
whether viability survives the high-cost case. Editing creates an immutable revision;
archiving hides the scenario while preserving its history. These values are always
labeled **User entered**. They do not confirm a supplier, landed cost, demand, or ad
performance.

### Build an investigation shortlist

Use **Add to shortlist** from a Store Intelligence Report, product drawer, or Ad
Autopsy. Open **Investigation shortlist** from the sidebar and record:

- the current workflow stage and priority;
- an explicit investigate, test, reject, or undecided decision;
- the product/store/ad thesis;
- the largest risks and unknowns; and
- the next concrete verification action.

Where normalized evidence IDs are attached, the API validates that they belong to the
same workspace. Archiving removes an item from the active workspace without deleting
its history. Shortlist decisions are your research notes; Northstar does not treat them
as observed demand or scoring evidence.

### Compare collected products

Open **Compare products**, select between two and five products, and choose **Compare
selected**. The matrix compares observed catalog facts, Northstar observation span,
collected related ads, evidence coverage, and the latest active user-entered economics
scenario. Use **Export JSON** for a portable copy of the exact comparison contract.

Verified sales, supplier match, review velocity, and missing economics remain visibly
unavailable. Corpus counts describe only your private Northstar database.

The **Observed products** page also supports store, observed-price, availability,
minimum-variant, and recent-first-observation filters. **Export CSV** downloads only
the filtered rows and protects spreadsheet cells from formula injection. These filters
describe collected catalog observations, not sales or product performance.

Expand **Saved product research views** to name and persist the current filter
configuration. Views are stored only in that browser's local storage and do not create
a cloud account or call a provider.

Use **Dossier** on an investigation card to download a versioned JSON bundle containing
the decision notes and current evidence/report state. A dossier is a point-in-time
research artifact, not an audited business report; its trust notice and unavailable
fields travel with the export.

Most advanced product columns currently remain `insufficient data` because the application does not yet collect review velocity, product clusters, a competitor corpus, supplier matches, or cost data. Product rows are unranked in the UI until the momentum publication gate is satisfied. Catalog presence alone is never treated as sales evidence.

Obvious auxiliary entries such as free gifts, shipping protection, warranties, gift cards, and zero-price items are hidden from the primary product intelligence table but retained in storage and counted in Diagnostics.

### Traffic

The Traffic tab shows imported Similarweb periods when available, including monthly visits, global rank, source, retrieval date, and the Northstar trend result.

At least three consecutive monthly visit periods are required for a Growing, Stable, or Declining direction. Global rank is displayed as context but is never converted into visits.

Only monthly visits and global rank are currently collected. Traffic channels, engagement, top countries, country rank, and category rank remain unavailable unless future provider endpoints are added.

### Ads

This tab shows store-matched imported Meta records when a match is supportable. Matching currently uses either:

- an imported ad landing on the exact store domain; or
- a confirmed Meta advertiser identity.

Even with matched records, current advertising status remains unknown unless Northstar has reliable, recent, store-scoped search coverage and status observations. A missing delivery-stop date is not interpreted as an active ad. Ad longevity and repeated records are evidence, not proof of performance.

### Offers & funnel

This tab displays detected homepage offer text and conversion patterns such as review widgets, email capture, free-shipping language, installment services, or other supported patterns.

These are page-pattern observations, not conversion-rate measurements. Current implementation does not yet crawl the full cart, checkout, post-purchase flow, or product-page funnel systematically, and it does not yet establish offer persistence across scans in the report.

### Technology

Technology detections are grouped by business purpose and include a short explanation of why the category matters. A pixel or analytics tool indicates measurement capability or intent; it does not prove traffic, active ads, or successful advertising.

Northstar aggregates public markers from the saved homepage and up to 24 saved
product pages. The report shows the number of pages inspected. Shopify appears
separately as the commerce platform and is excluded from the app count. When
the storefront exposes `Shopify.theme`, the Technology tab also shows the theme
schema/name, version, Theme Store ID, and role. Integration cards use public
domain favicons where available and retain a letter fallback when artwork is
missing.

For Shopify storefronts, Northstar also reads explicit public theme app-block
metadata. This can identify apps that do not expose one of the older hard-coded
script patterns. It remains a public-page inventory rather than a guarantee that
every installed, server-side, disabled, or obfuscated app is detectable.

Detection is based on publicly visible homepage patterns. It is not a complete BuiltWith-style inventory and may miss server-side or heavily obfuscated tools.

### Evidence

The Evidence tab exposes the active estimation profile, source records used by the headline insights, assumption snapshots, missing signals, and analysis version. Evidence uses independence groups so multiple correlated facts from one provider do not masquerade as multiple independent confirmations.

Every report load creates a new immutable analysis run. Historical runs keep the estimator versions and assumptions used at that moment; completed runs and their evidence links are not rewritten.

### Diagnostics

Diagnostics contains technical collection information that should not be mistaken for business intelligence:

- source URLs and their state;
- HTTP status codes;
- fetch timestamps;
- crawler/background job state;
- raw snapshot counts; and
- auxiliary product counts.

Use this tab when a report is incomplete or a scan failed. Do not use a completed job count or successful HTTP response as evidence of sales.

## 6. Connect Similarweb and fetch traffic

Similarweb is optional and requires your own eligible REST API key.

1. Open **Settings & sources**.
2. Find **Similarweb API**.
3. Paste the key and save it.
4. Open **Stores & traffic**.
5. Choose **Fetch previous month** for a collected store.

The UI requests the previous completed month, worldwide, for the main domain. One normal refresh requests the visits endpoint and global-rank endpoint. Similarweb may charge up to two results/data credits for that one-month refresh, depending on the provider account and billing model.

A successful or partial result for the same domain, period, country, and main-domain setting is reused for 24 hours to reduce duplicate provider credit use. The UI has no force-refresh control; the local API supports `force: true` when you deliberately need a new provider call.

If the plan returns only one metric, Northstar stores a partial snapshot. It never fills in the other metric. Full details are in [Integrations](INTEGRATIONS.md#similarweb).

## 7. Find ads with GetHookd or Meta

Open **Ad library** (`/library-product`; the older `/ads` URL remains
compatible) to choose among three distinct sources:

- **Northstar library** contains durable official Meta imports and public ads you
  save yourself. Choose **Save public ad**, record the public source URL, and add any
  visible advertiser, copy, creative, CTA, or landing-page evidence. Northstar stores
  the source/provider separately from the advertising platform.

- **GetHookd search** performs a live, provider-credit-metered search across the ad
  records available to your GetHookd public API token. Search by product, problem,
  hook, brand, or copy and filter by platform, activity, format, and minimum run time.
- **Official Meta API** searches the narrower transparency API coverage available to
  your Meta token and saves returned public records locally.

To connect GetHookd, open **Settings & sources**, save a public API token with
`explore:read` access, then return to **Find ads**. Northstar displays the provider's
reported credit usage after every search. GetHookd results remain optional and
live-only; save public evidence separately to the Northstar library when appropriate.

Run duration and GetHookd classifications are investigation signals—not evidence of
competitor spend, conversions, ROAS, or profit.

### Capture a public ad from Chrome or Edge

Northstar includes an unpacked local extension under `extension/`:

1. Start Northstar.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode** and choose **Load unpacked**.
4. Select `C:\Users\andre\Desktop\dropship-intel-mvp\extension`.
5. Pin **Northstar Public Ad Capture**.
6. Open a public ad-library page and select the visible ad copy when possible.
7. Open the extension, review every inferred field, and choose **Save to Northstar**.

The extension reads only the active tab after you invoke it. Versioned Meta, TikTok,
and Google adapters inspect the selected card or nearby panel; a generic selected-text
adapter remains the fallback. The preview identifies captured fields, confidence, and
partial-capture warnings. It does not run a background crawler, receive blanket site
access, log in, or bypass provider controls. Public page structures change, so inferred
fields must be reviewed. Adapter provenance remains visible later in Ad Autopsy.

### Record and read ad analytics

The web import form and browser extension include optional visible analytics. Enter
only values the public source actually displays. Northstar preserves distinctions:

- `12043` can be stored as an exact numeric value only when the source is exact;
- `34K` remains a provider-reported rounded value;
- `10K–50K` is stored as a range when entered through the metric API;
- `Top 18%` remains a percentile label; and
- missing impressions, clicks, spend, conversions, CPA, or ROAS remain unavailable.

Open **Find ads → Northstar library → Analytics** on a saved record. The drawer has:

- source-reported metrics with provider and geography;
- Northstar/provider observations such as collection time, creative count, and
  completed provider delivery window; and
- an expandable list of competitor metrics the evidence does not provide.

The Northstar library can filter by platform, provider/source, creative format,
advertiser, landing domain, saved metric, metric geography, and recent observation
window. These facets query only locally saved observations and consume no provider
credits.

Collection time is not ad launch time, and a completed delivery window does not prove
continuous spend or profitable performance.

Choose **Autopsy** on a saved record to open its stable `/ads/<ad-id>` investigation
page. It combines creative/copy, provider provenance and dates, analytics, landing
collection diagnostics, resolved store/products, and related saved ads. Its conclusion
is limited to **Product path resolved**, **Evidence saved, product unresolved**, or
**Landing evidence not collected**; it never labels an ad a winner. Use **Investigate
landing page** to send the public destination through the normal safe collector.
Saved media, audio transcript, and on-screen OCR have separate states. Until a media
processing pipeline is configured, transcript and OCR correctly read **Not collected**.

### Connect Meta and search its official API

Meta is optional and requires an access token eligible for Meta's official Ad Library API.

1. Open **Settings & sources**.
2. Find **Meta Ad Library API**.
3. Paste the access token and save it.
4. Open **Find ads** and select **Official Meta API**.
5. Enter a brand or advertiser query.
6. Select a reached country supported by the query and run the search.

For a scanned store, open its report and select **Ads** to review the brand,
Facebook, and Instagram candidates collected from the public homepage. Inspect the
source link before confirming a candidate. You can remove a confirmation at any
time; collector confidence is evidence quality, not proof of ownership.

Northstar calls the official Graph API `ads_archive` endpoint and persists the public records returned. It does not scrape Meta's Ad Library website.

The official API is not a worldwide commercial-ad feed. Its coverage and retention rules are set by Meta and can be narrower than the public interactive website. An empty result can mean no provider coverage, no query match, token restrictions, date/country restrictions, or no returned ads; it is not proof that the brand is inactive.

### Advertiser watches and historical retention

Open **Ad library → Advertiser watches** to save a repeatable collection target.
A watch stores the provider, brand/product search or advertiser ID, countries,
result budget, and refresh interval. Enabled Meta watches use the configured
official Ad Library API while Northstar is running. You can pause a watch or
run it immediately. TikTok Commercial Content, Google Transparency, and manual
capture targets can be recorded now, but are created paused until Northstar has
authorized official access or you import evidence through the extension.

Each attempt produces a durable collection-run record with fetched, inserted,
updated, recurring, and error counts. Ads linked to a watch also accumulate an
observation count. Northstar intentionally distinguishes a provider-confirmed
stop date from an ad merely missing from the latest limited query.

Historical records use tiered retention:

- **Metadata:** a single or brief observation keeps compact normalized fields
  and provider references.
- **Evidence:** a repeatedly observed ad keeps its longevity evidence.
- **Creative:** recurring or long-running ads preserve available creative
  references as higher-value research material.
- **Research:** ads saved into an investigation receive the highest priority.

The local scheduler checks for due watches once per minute and only runs while
`start-northstar.ps1` is active. Deleting a watch removes its schedule and
watch-observation links but leaves already collected ads in the durable library.

Store scans extract likely brand and social identities, and the store report now
supports reviewing and confirming them. Automatic provider searches after
confirmation are not implemented, so Meta searching is still manual. The same
workflow is available through the local API; see [API reference](API_REFERENCE.md#store-identities).

## 8. Adjust estimation assumptions

Open **Settings & sources → Estimation assumptions**. The UI edits the active `general_ecommerce` profile.

You can change:

- low, central, and high conversion-rate planning assumptions;
- low, central, and high items-per-order multipliers;
- low and high traffic planning-envelope multipliers;
- evidence freshness limit in days;
- minimum independent product evidence groups; and
- weights for advertising, reviews, merchandising, inventory, persistence, and offer/page evidence.

The default conversion range is 0.5% / 1.2% / 2.5%. These are planning priors, not facts about a scanned store. The default items-per-order range is 1.0 / 1.15 / 1.5, and the traffic envelope is 0.70× to 1.40× around a Similarweb visit point.

Product weights must be non-negative, include exactly the six groups, and total 100%. The minimum evidence count cannot exceed the number of groups with a positive weight.

Saving does not overwrite the old profile. It creates a new version and makes that version active. Existing analysis runs preserve their prior assumption snapshot; newly opened reports use the newly active profile.

The API supports category-specific profiles with general-profile fallback. The current UI only edits the general profile.

## 9. A practical research workflow

For a new store:

1. Scan the store root, not just one product.
2. Wait for the homepage and sitemap/product jobs to complete.
3. Read Overview and Diagnostics before interpreting missing fields.
4. Connect Similarweb and fetch traffic if your account permits it.
5. Search Meta manually using the strongest detected brand or linked social handle.
6. Treat AOV, orders, and revenue as planning ranges, not reported merchant results.
7. Rescan over weeks, not minutes, to build genuine history.
8. Investigate products only when at least two independent evidence groups support them.
9. Keep supplier cost, saturation, competitor coverage, and profit unknown until those data sources are actually implemented and populated.

The goal is to decide what deserves further validation. Northstar is not a substitute for a supplier quote, ad test, customer research, or your own store analytics.
