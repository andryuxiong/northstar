# Existing-system gap review — 2026-07-12

This review was performed against the current code, documentation, personal
SQLite records, and immutable saved storefront snapshots. Its purpose is to
improve existing behavior before adding new product areas.

## What the personal data showed

### Vibes Point

- 11 collected product records and 53 product snapshots.
- The persisted homepage profile reported three technologies: Shopify,
  Judge.me, and Hotjar.
- The same immutable homepage HTML also contains explicit Shopify app blocks
  for Kaching Bundles and PageFly.
- Replaying the improved detector against the saved homepage and product pages
  returns Shopify plus Judge.me, Hotjar, Google Analytics 4 / Google tag,
  Kaching Bundles, and PageFly.

The missing detections were a Northstar collector limitation, not missing
source evidence.

### Slumblr

- 156 collected products and 192 product snapshots.
- None of the latest normalized snapshots contained an image even though the
  saved pages expose public Open Graph product images.
- Replaying the improved image resolver against the existing saved HTML
  resolves images for all 156 latest product records in about 0.55 seconds on
  the current machine, without making network requests or rewriting history.

The root cause was source precedence: Shopify's inline product object supplied
good identity/variant data but commonly omitted images, and Northstar returned
it before merging image-bearing JSON-LD or Open Graph data.

## Changes completed from this review

- Merge complementary Shopify inline product, JSON-LD, and Open Graph fields.
- Normalize string and object-form product images and deduplicate URLs.
- Recover images for historical empty normalized records through a bounded,
  cached immutable-HTML fallback.
- Detect explicit public Shopify theme app blocks, with known labels and a
  transparent generic label for unknown app slugs.
- Automatically surface previously unseen third-party script, stylesheet, and
  iframe hosts as unclassified integrations; known signatures now improve
  naming and deduplication rather than deciding whether evidence is visible.
- Aggregate technology evidence across the saved homepage and up to 24 current
  saved product pages instead of treating one page as the whole storefront.
- Extract the public `Shopify.theme` object, including theme/schema name,
  version, Theme Store ID, and role when exposed.
- Separate Shopify as commerce-platform context from the app/integration count,
  and render favicon-based integration artwork with a local letter fallback.
- Add PPSPY-inspired `/shopify-product` and `/library-product` routes for the
  known Northstar product corpus and saved/provider ad discovery workspace.
- Add durable advertiser watches with scheduled official Meta queries,
  collection-run audit records, per-watch recurrence observations, explicit
  absence semantics, and metadata/evidence/creative/research retention tiers.
- Replace horizontally oversized global/report product tables with responsive
  cards that keep all evidence visible without a bottom scrollbar.
- Add an Overview section for directly observed, API-free storefront value:
  product count, image coverage, technology count, and offer/funnel signals.
- Add data-readiness guidance that explains when a missing result needs a
  provider, more history, or a new collector rather than another identical scan.

## Why Overview still withholds some metrics

These are evidence gates, not rendering failures:

| Metric | Why it can remain unavailable | What unlocks it |
| --- | --- | --- |
| Monthly visits | Public storefront HTML does not disclose traffic | Eligible Similarweb visits response or another normalized traffic provider |
| Monthly orders | Requires a traffic range; catalog size is not orders | Available traffic plus disclosed conversion assumptions |
| Gross revenue | Requires both order and AOV ranges | Traffic plus enough sellable same-currency products |
| AOV | Requires at least five eligible merchandise products in one currency | Better product/currency parsing or a genuinely larger eligible catalog |
| Store momentum | Requires at least three consecutive monthly traffic periods | Repeated provider traffic observations |
| Product momentum | Requires at least two independent evidence groups and 14 days | Reviews, associated ads, merchandising, inventory, offer/page, or longer persistence evidence |
| Advertising status | Empty local matches have unknown search coverage | Durable store-scoped provider search/status observations |
| Dropshipping likelihood | Both supporting and counter-signals are absent | Supplier/image overlap, shipping/policy, brand, and cross-store collectors |

The Overview now shows collected storefront facts separately so these honest
gates do not make a successful scan appear empty.

## Highest-value remaining work on existing foundations

1. **Product review collection.** Review count and velocity are the clearest
   missing non-traffic demand evidence and can strengthen product momentum.
2. **Durable store-scan orchestration.** The current store job queues child jobs
   and completes before all descendants; the product budget is not truly
   store-wide.
3. **Technology coverage depth.** Homepage and product-page aggregation,
   explicit Shopify app blocks, and unknown external-host discovery are
   implemented. Server-side, historical, disabled, authenticated, or fully
   obfuscated applications still cannot be inferred from absent public
   evidence. Cart-page and browser-runtime/network collection can expand honest
   coverage further.
4. **Discovery-corpus breadth.** The PPSPY-inspired routes search Northstar's
   collected products and saved/provider ads. Meta rejected the configured
   personal developer token with permission code 10/subcode 2332002, and manual
   capture is too slow for the desired primary workflow. The recommended next
   adapter is a budget-capped, replaceable Apify public Meta Ad Library collector;
   it is planned but not implemented.
5. **Ad/product association and watch seeding.** Durable query scope, run status,
   recurrence, absence semantics, and retention tiers are now implemented.
   Remaining work is automatic store-to-advertiser identity resolution and
   stronger landing/creative-to-product graph evidence.
6. **Report analysis-run retention.** Opening a report creates an immutable run;
   there is no retention or history-management UI.
7. **Frontend decomposition and code splitting.** The production build passes,
   but the main bundle remains above Vite's 500 kB warning threshold and
   `App.tsx` is still monolithic.

## Validation

- Backend: 71 tests passed.
- Frontend: production build passed.
- Browser extension: 4 offline adapter tests passed.
- Live saved-data replay: Vibes Point inspected 11 pages and returned Shopify
  plus 5 integrations and the Shrine PRO 1.2.3 theme.
- Live saved-data replay: Slumblr inspected 25 pages and returned Shopify plus
  9 integrations (including Monimo and product-page Yotpo) and Impact 7.2.0.
- Saved-data replay: Slumblr image resolution increased from 0/156 to 156/156.
