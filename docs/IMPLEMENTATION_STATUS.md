# Northstar implementation status

This document records what the current decision-focused implementation completed and what remains partial or future. It should be read with the original [product audit](NORTHSTAR_PRODUCT_AUDIT.md) and [implementation plan](IMPLEMENTATION_PLAN.md).

Northstar is now usable as a personal public-storefront intelligence workspace, but it is not yet a full PPSPY/ShopHunter/Similarweb/BuiltWith/Meta/product-supplier replacement. The most important improvement is that the application now says what its evidence supports and explicitly withholds what it cannot support.

## Completed in this implementation

### Repository and product audit

- Inventoried the React/Vite frontend, FastAPI API, SQLAlchemy/SQLite database, in-process worker, parsers, provider integrations, routes, tests, and snapshot architecture.
- Identified raw fetch telemetry, chronological change feeds, raw variant/availability columns, and unsupported legacy scores as low-value primary UI.
- Preserved historical product, variant, availability, price, landing, traffic, ad, and raw snapshot data for future derived signals.
- Documented the initial capability gaps and an incremental implementation plan.

### Safe intelligence schema foundation

- Made the initial migration portable across SQLite and PostgreSQL JSON types.
- Added safe startup migration/bootstrap behavior for unversioned legacy personal databases.
- Added transactionally consistent SQLite backups with integrity verification before legacy migration.
- Added typed, indexed models for store profiles, store identities, estimation profiles, analysis runs, normalized traffic observations, derived insights, evidence records, and insight/evidence attribution.
- Preserved existing stored scans and compatibility models.

Current schema head: `0009_investigation_shortlist`.

### Unified Store Intelligence Report

- Added `GET /intelligence/stores/{id}` and stable frontend routes under `/stores/:id/:tab`.
- Added a decision-first Overview with verdict, strongest evidence, largest uncertainty, next step, headline ranges/classifications, and overall confidence.
- Added Products, Traffic, Ads, Offers & funnel, Technology, Evidence, and Diagnostics tabs.
- Moved raw source state, HTTP status, job data, fetch timestamps, and scan counts into Diagnostics.
- Added honest loading, error, empty, partial-data, and unsupported states.
- Ensured the product UI withholds visible rankings when product momentum does not pass its evidence gate.

### Versioned estimation engine

- Added pure typed `traffic-trend-v1`, `aov-v1`, `orders-v1`, `revenue-v1`, and `product-momentum-v1` estimators.
- Added ordered low/central/high ranges rather than fake precision.
- Added evidence, assumptions, missing signals, confidence, explanation, units/currency, and estimator version to every result.
- Kept confidence separate from the value/score and grouped correlated evidence.
- Added immutable analysis-run and evidence persistence.
- Added versioned user-adjustable settings for conversion, basket multipliers, traffic envelope, freshness, evidence gates, and product evidence weights.

Exact formulas and gates are documented in [Intelligence methodology](INTELLIGENCE_METHODOLOGY.md).

### Homepage, profile, offer, funnel, and technology collection

- Store scans now fetch the homepage as well as the sitemap.
- Added brand extraction from structured data, Open Graph, title, logo text, and domain.
- Added public Facebook/Instagram identity candidate extraction.
- Added platform, category, country, currency, language, and logo/profile observations where available.
- Added selected homepage technology patterns grouped by business purpose.
- Added explicit Shopify theme-app-extension discovery from public
  `shopify://apps/<slug>` block metadata, including transparent fallback labels
  for previously unknown app slugs.
- Added selected offer and funnel/conversion pattern observations.
- Persisted `StoreSnapshot` and current `StoreProfile` records.

### Product collection quality

- Improved Shopify rich product JSON parsing and retained external ID, handle, vendor, and product type in snapshot payloads where found.
- Merged complementary Shopify inline-product, JSON-LD, and Open Graph image
  evidence so selecting richer variant data no longer discards product images.
- Added a cached saved-HTML image fallback so historical empty image arrays can
  be displayed without refetching pages or rewriting immutable observations.
- Added safer generic JSON-LD `@graph` handling and stopped assuming availability is true when absent.
- Normalized Shopify locale product URLs.
- Added conservative duplicate consolidation through same handle/external ID or direct canonical/redirect proof while preserving/reassigning history and relationships.
- Reclassified product URLs that redirect to non-product pages.
- Added homepage fallback discovery when a sitemap is missing.
- Restricted a store scan's sitemap traversal to the same domain.
- Reconciled landing-product edges after asynchronous product creation.
- Reduced duplicate queuing for already queued/fetching product sources.
- Replaced horizontally oversized product intelligence tables with responsive
  product cards and added an observed-without-APIs overview plus actionable data
  readiness summary.

### Similarweb integration hardening

- Kept the real visits/global-rank REST integration and normalized its series into typed traffic observations.
- Added three-attempt bounded retries/backoff for network errors, 429, and 5xx responses.
- Added a 24-hour successful/partial exact-scope cache to protect provider credits, with explicit `force` override in the API.
- Kept partial/unavailable metric states instead of inventing missing provider data.
- Ensured newer rank-only fetches cannot make an older visits estimate appear fresh.

### Meta integration hardening

- Kept the official Graph API `ads_archive` integration; no Ad Library UI scraping.
- Added bounded retry/backoff behavior.
- Normalized advertiser, creative text, calls to action, provider delivery dates, platforms, assets, and destinations when returned.
- Removed provider access tokens/app-secret proof from stored/output URLs and converted snapshot URLs to public Ad Library permalinks.
- Added store/ad matching through exact landing domain or a confirmed Meta identity.
- Deliberately kept current advertising status Unknown without recent successful scoped search coverage.

### Provider-neutral ad discovery foundation

- Renamed the primary ad workspace to **Find ads** with explicit provider selection.
- Added optional GetHookd public API credential storage with environment precedence and masked status output.
- Added live GetHookd Explore search by keyword, platform, activity, format, and minimum run duration.
- Added creative/advertiser cards, landing and creative links, and provider-reported credit usage.
- Added durable provider/source provenance so official imports and user-saved public ads cannot overwrite or masquerade as one another.
- Added a Northstar-owned ad library and manual public-ad import workflow with source, creative, and landing-page URLs.
- Added a narrowly permissioned Chrome/Edge active-tab capture extension with editable evidence fields and direct loopback saving.
- Added extension-origin CORS coverage restricted to valid Chrome extension IDs and stripped known Meta token parameters before URL storage.
- Kept optional GetHookd searches live-only by product choice; Northstar's durable library does not depend on GetHookd.
- Labeled provider scores, duration, and classifications as research signals rather than proof of performance.

### Source-scoped ad analytics foundation

- Added durable `ad_metric_observations` with source, value kind, geography, period, confidence, and timestamps.
- Kept exact, reported/rounded, range, percentile, classification, and unavailable values structurally distinct.
- Added metric list/create and consolidated ad Analytics API endpoints.
- Added optional visible-metric capture in both the web import form and Chrome/Edge extension.
- Added an Analytics drawer with source-reported values, Northstar/provider observations, and explicit unavailable competitor metrics.
- Added a detailed [product roadmap](PRODUCT_ROADMAP.md) with dependencies and completion criteria for future phases.

### Ad Autopsy foundation

- Added a stable `/ads/:id` frontend route backed by `GET /ads/{id}/autopsy`.
- Joined saved creative/copy, provider provenance and dates, source-scoped analytics,
  unavailable metrics, landing diagnostics, resolved stores/products, and related ads.
- Added an evidence-gated investigate / weak evidence / insufficient data conclusion
  and a direct action into the existing safe landing-page collector.
- Added explicit saved-media, transcript, and OCR collection states; actual processing
  remains deferred until a permitted media pipeline exists.
- Related ads now match through shared resolved products across different landing URLs,
  with provider/platform scoping protecting against identifier collisions.
- Added private-corpus filters for platform, provider/source, creative format, and
  advertiser, landing domain, saved metric, metric geography, observation window, and
  useful saved/observed/delivery-duration ordering without provider calls or credits.
- Added versioned Meta, TikTok, and Google capture adapters with an editable preview,
  confidence, partial-capture warnings, generic fallback, and offline snapshot fixtures.
- Persisted extension adapter provenance and made exact normalized source-URL
  recaptures update the existing ad and landing relationship instead of duplicating it.

### Versioned product test economics

- Added multiple named, user-entered economics scenarios per product with immutable
  revisions and archive behavior.
- Added low/high product, shipping, fulfillment, and other variable costs; payment
  fees; refund allowance; and target profit margin inputs.
- Added disclosed `unit-economics-v1` contribution, break-even CPA/ROAS, target
  CPA/ROAS, sensitivity classification, formulas, and explicit user-entered labeling.
- Kept manual planning assumptions separate from observed supplier evidence and did
  not unlock supplier-match or supplier-derived margin claims.

### Decision-focused investigation shortlist

- Added an idempotent shortlist action to store reports, product drawers, and Ad
  Autopsy plus a stable `/shortlist` workspace.
- Added workflow stage, investigate/test/reject decision, priority, thesis, risks, and
  required next-verification-action fields.
- Added optional workspace-scoped links to normalized evidence records and preserved
  archived items outside the active view.
- Kept decisions user-authored; adding an entity never manufactures a score or claim.

### Known-corpus product comparison

- Added a stable `/compare` workspace for selecting two to five collected products.
- Added side-by-side store/platform, observed price, variants/images, availability,
  observation span, collected related ads, normalized evidence, and saved economics.
- Added explicit verified-sales, supplier, review-velocity, and economics unavailable
  fields plus private-corpus coverage labeling.
- Added portable JSON export containing the same provenance and honesty notice shown in
  the UI.
- Added downloadable `research-dossier-v1` exports from shortlist items, combining the
  user's decision notes with the current store report, Ad Autopsy, or product
  observations/economics/evidence and an explicit trust notice.
- Expanded Observed products with store, price, availability, minimum-variant, and
  first-observed-date filters plus formula-injection-safe CSV export of the filtered
  public catalog observations.
- Added named product research views that persist the current filter configuration in
  local browser storage without accounts, provider calls, or server-side profile data.

### Correctness and local UX

- Fixed touched legacy workspace-isolation paths and product query behavior.
- Added frontend API auto-relogin for fresh deep links and expired local sessions.
- Reduced idle full-app polling from five seconds to approximately 30 seconds, while retaining faster polling during active jobs.
- Removed subscriptions, monthly scan quotas, credits, and SaaS billing concepts from the personal UI.
- Updated the primary product views to avoid legacy winner/momentum claims and raw change telemetry.

### Verification

At the completion point:

- 65 backend tests and 4 offline extension adapter tests passed;
- the frontend production build passed;
- the frontend production dependency audit found no known vulnerabilities;
- the backend requirements audit found no known vulnerabilities; and
- the real local database was backed up and migrated through `0009_investigation_shortlist`, with verified pre-change backups retained under `backend/data/backups/`.

The backend test suite is isolated from the personal database.

## Partially implemented

### Meta identity workflow

Working:

- brand/social candidate extraction;
- candidate confidence/source storage;
- identity list and confirm/unconfirm API;
- frontend candidate review, source inspection, and confirmation workflow; and
- confirmed-identity or landing-domain ad matching.

Missing:

- automatic candidate searches against Meta for every scanned store;
- normalized advertiser/search coverage records; and
- robust disambiguation when brands share a name.

### Product momentum

Working:

- evidence-group architecture;
- publication gates;
- homepage placement, imported related-ad, persistence, and public restock inputs; and
- configurable weights and confidence.

Missing:

- review count/velocity collector;
- product-level offer/page-quality input;
- reliable landing-page traffic evidence;
- broader promotion/collection/nav prominence; and
- calibrated probability or product sales share.

As a result, product momentum will correctly remain unavailable for many newly scanned stores.

### Offers, funnel, and technology

Working:

- useful homepage pattern detection;
- evidence/confidence display; and
- business-function grouping.

Missing:

- normalized historical offer observations;
- full product-page, collection, cart, checkout, exit-intent, and post-purchase analysis;
- offer comparison across similar stores; and
- exhaustive technology coverage.

### Traffic intelligence

Working:

- Similarweb monthly visits and global rank;
- multi-period history;
- month-over-month calculation and three-to-six-month direction;
- freshness handling and disclosed planning envelope.

Missing:

- country/category ranks;
- top countries;
- channel mix;
- engagement metrics;
- SEO/backlink/search-visibility supplemental collectors; and
- an alternate traffic provider.

### Scan orchestration

Working:

- local bounded background execution;
- partial success and per-source diagnostics; and
- homepage/sitemap/product fan-out.

Missing:

- durable `store_scans` and task rows;
- resumable scans;
- a true store-wide discovery budget;
- durable rate-limit scheduling; and
- parent/child completion aggregation.

## Not implemented yet

The report deliberately exposes these as missing/unknown rather than fabricating them:

### Product similarity and competitors

- image perceptual hashes and embeddings;
- normalized title/description/model/SKU matching;
- product clusters;
- competitor relationships;
- cross-store price/offer distribution;
- known-store coverage denominators; and
- saturation scoring.

### Suppliers and margin

- supplier marketplace/search-provider integrations;
- image/title/model supplier matching;
- unit cost, MOQ, origin, or delivery estimate normalization;
- confirmed/possible supplier-source distinction; and
- gross margin ranges.

### Opportunity scoring

- defensible demand, competition, saturation, margin, creative-potential, differentiation, and overall opportunity scores; and
- category-specific evidence thresholds for those scores.

### Creative intelligence

- normalized creative entities and observations;
- near-duplicate grouping;
- hook, angle, format, offer, CTA, and landing-page classification;
- repeated/new/long-running concept summaries; and
- creative-gap recommendations.

### Dropshipping likelihood

- marketplace image overlap;
- supplier-style catalog/shipping/policy signals;
- branded/proprietary counter-signals; and
- a versioned likelihood estimator with evidence on both sides.

The headline remains Unknown until those inputs exist.

### AI analyst

- evidence-grounded Q&A;
- internal evidence citations in generated answers;
- actionable product/store/offer/creative recommendations; and
- safeguards against unsupported model claims.

The analyst is intentionally deferred until the underlying evidence contracts and missing data collectors are mature.

## Current report honesty boundaries

Northstar cannot currently know or responsibly claim:

- exact or live website visitors;
- merchant orders, sales, revenue, or conversion rate;
- product-level sales;
- profit;
- ad spend, conversions, ROAS, or which creative won;
- worldwide Meta commercial-ad coverage;
- supplier relationship or landed cost;
- the number of all stores selling a product; or
- whether a store is definitively dropshipping.

It can provide an observed public catalog/profile, official imported provider records within provider coverage, and disclosed planning ranges from those inputs.

## Recommended next implementation phase

The highest-value next phase is **durable Meta identity/search coverage and ad-to-product association**, followed by review collection.

Recommended order:

1. Add durable store scan and provider search coverage models so `active`, `inactive`, and `no returned records` have a known query scope and date.
2. Automatically generate and execute eligible Meta advertiser/page searches after confirmation.
3. Normalize advertiser, creative, creative observation, destination, and product-association tables.
4. Add product review count/velocity collection for supported public review platforms.
5. Feed those independent groups into product momentum before building similarity/supplier/AI layers.

This phase improves the central decision—whether a store and product show meaningful demand—without pretending that catalog presence or an unscoped empty search is proof.
