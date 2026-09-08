# Northstar implementation plan

This plan extends the current architecture. It does not replace the crawler, provider clients, raw snapshots, or historical data.

Implementation note: phases 1–3 and the homepage/identity foundation of phase 4 are now substantially implemented. See [Implementation status](IMPLEMENTATION_STATUS.md) for the authoritative completed/partial/future inventory; this document retains the phased design that guided the work.

## Phase 1 — truthfulness, migration, and cleanup

1. Make the initial Alembic revision dialect-safe and bootstrap the existing unversioned personal SQLite database only after verifying its schema and making a backup.
2. Add typed analysis profiles, analysis runs, derived insights, evidence records, insight/evidence links, store identity/profile records, and normalized traffic observations.
3. Stop using legacy Score rows in the report and primary product UI.
4. Move source URLs, jobs, HTTP status, fetch timestamps, and raw snapshot history into Scan Diagnostics.
5. Fix workspace-scoping and default product-query defects on touched legacy routes.

## Phase 2 — unified store report

Add `GET /intelligence/stores/{store_id}` and a stable `/stores/:id/:tab` UI. The report contains:

- an explicit verdict, strongest evidence, largest uncertainty, and next investigation;
- store identity/platform/category/market when collected;
- traffic history and availability, with provider provenance;
- transparent AOV, order, and gross-revenue estimates or explicit insufficient-data results;
- conservative ranked-product evidence states;
- store-scoped ad evidence where matching is supportable;
- offers/funnel/technology collection states;
- evidence, assumptions, missing signals, versions, and freshness;
- scan diagnostics separated from business conclusions.

Keep old endpoints during migration so stored scans and the current UI remain compatible.

## Phase 3 — versioned estimator v1

### Traffic (`traffic-trend-v1`)

- Never infer visits from rank.
- Use the newest provider observation for each month and deduplicate repeated fetches.
- One month: no direction. Two consecutive months: provisional month-over-month change. Three or more: robust median monthly change, with growing/declining thresholds disclosed in settings.
- A planning envelope around a Similarweb point is a Northstar assumption, not a Similarweb confidence interval. Default: 0.70–1.40. In v1, stale or partial data lowers confidence and is disclosed; it does not silently widen the configured bounds.

### AOV (`aov-v1`)

- Exclude zero-price products, free gifts, shipping protection, warranties, tips, donations, and obvious services/add-ons from price anchors.
- Require at least five eligible products in one dominant currency.
- Low = eligible price P25 × items/order low.
- Central = eligible median × items/order central.
- High = eligible P75 × items/order high.
- Initial disclosed planning priors: 1.0 / 1.15 / 1.5 items per order. Catalog price is not observed basket value, so confidence remains low without basket/bundle evidence.

### Orders (`orders-v1`)

- Require monthly visits. Ads, rank, or catalog size alone cannot produce orders.
- Low = traffic low × conversion low; central = traffic central × conversion central when justified; high = traffic high × conversion high.
- Initial editable general planning prior: 0.5% / 1.2% / 2.5%. No ad-count multiplier in v1.

### Gross revenue (`revenue-v1`)

- Low = orders low × AOV low; central = central × central when both exist; high = high × high.
- Always label this estimated gross store revenue, not profit.
- Revenue confidence cannot exceed its weakest required input and is capped low when conversion relies on a generic prior.

### Product momentum (`product-momentum-v1`)

- Use an evidence score, not a calibrated winning probability.
- Evidence groups: related advertising, review velocity, merchandising prominence, verified restock/availability trend, persistence/launch evidence, and offer/page support.
- Publish a numeric score only with at least two independent groups and sufficient coverage. Direction requires at least three unique observations over fourteen days (thirty preferred).
- Product existence, raw variant count, discount, or an active ad alone never proves sales.

## Confidence rules

- Confidence is independent of the estimated value or score.
- Evidence quality combines relevance, source reliability, parse quality, freshness, and independence group.
- Correlated fields from Similarweb, one Meta search, one review provider, or one inventory parser are aggregated as one group rather than double-counted.
- Labels: high at 0.75+, medium at 0.50–0.749, low at 0.25–0.499, and insufficient below 0.25 or when a required input is absent.
- Every result exposes evidence, sources, assumptions, missing signals, calculated time, freshness, and estimator version.

## Phase 4 — identity, ads, and creative intelligence

1. Fetch and analyze store homepages for domain/title/schema/Open Graph/logo/footer/social identity candidates.
2. Persist Facebook/Instagram/Meta Page candidates with match confidence and manual confirmation.
3. Normalize advertisers, ad observations, creatives, destinations, and ad-to-product matches.
4. Group creatives by product, concept, hook, angle, format, offer, CTA, and landing page.
5. Describe repeated/long-running/recent patterns without claiming performance.

## Phase 5 — opportunities, competitors, and suppliers

1. Add perceptual hashes, image embeddings, normalized titles/descriptions, SKU/model matches, and product clusters.
2. Derive competitor relationships, price distributions, ad prevalence, and saturation only from known corpus coverage.
3. Add legally available supplier search providers and persist possible matches with evidence and confidence.
4. Calculate gross margin ranges only when a plausible cost range exists.
5. Add demand, competition, saturation, margin, creative-potential, differentiation, and opportunity scores with separate confidence.

## Phase 6 — evidence-grounded analyst

Add the AI analyst only after report evidence contracts are stable. It may summarize and reason over stored evidence, cite internal records, identify missing information, and recommend tests. It must not invent traffic, sales, ad performance, supplier relationships, or profit.

## API direction

- `GET /intelligence/stores/{id}` — unified report.
- `POST /intelligence/stores/{id}/recompute` — versioned recalculation.
- `GET /intelligence/settings` and `PUT /intelligence/settings/{category}` — adjustable assumptions.
- `GET /intelligence/stores/{id}/evidence` — normalized evidence.
- `GET /intelligence/stores/{id}/identities` and `PATCH /intelligence/stores/{id}/identities/{identity_id}` — candidate review and confirmation API (frontend workflow remains partial).
- Future: durable `POST /store-scans`, `GET /store-scans/{id}`, competitors, clusters, suppliers, and analyst Q&A.

## Test strategy

- Pure estimator tests for available/partial/unavailable/stale and monotonic ranges.
- Fixtures for complete, partial, unavailable, contradictory, mixed-currency, and gift-heavy catalogs.
- Correlation tests proving same-provider fields do not inflate confidence.
- API report and workspace-isolation tests.
- Migration tests for fresh SQLite and a legacy unversioned SQLite copy; row counts and raw JSON must remain unchanged.
- Existing provider and crawler security tests remain in place.
