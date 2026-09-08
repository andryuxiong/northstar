# Northstar product roadmap

This is the durable continuation plan for Northstar. It records why each feature
matters, its evidence requirements, dependencies, and what “done” means. Future work
must update this document whenever scope or implementation status changes.

## Product direction

Northstar is a private, single-user commerce research system built around two jobs:

1. **Find an interesting ad or store quickly.**
2. **Decide whether the underlying product is worth a controlled test.**

The target workflow is:

```text
Find or capture an ad
→ identify its advertiser, landing page, store, and product
→ inspect public analytics and creative strategy
→ reverse-engineer the product page and offer
→ find similar sellers and possible suppliers
→ calculate sourceability and break-even economics
→ produce a cited test / reject decision
```

Long-running watchlists and cosmetic store-change tracking are deliberately lower
priority. They should not displace one-session investigation features.

## Rules for every phase

- Exact competitor spend, impressions, clicks, conversions, revenue, profit, CPA,
  and ROAS remain unavailable unless an authorized source explicitly returns them.
- Points, ranges, rounded values, percentiles, classifications, observations, and
  estimates are different data types and may not be silently converted.
- Every metric requires its source, observed/retrieved time, and geography/period when
  known.
- Run duration, creative repetition, and active state are investigation proxies—not
  proof of profitable scaling.
- Collectors may use public pages and authorized APIs only. They must not bypass login,
  CAPTCHA, anti-bot, private endpoints, or provider access controls.
- AI output must cite internal evidence and state when required evidence is missing.

## Current foundation — completed

As of schema revision `0009_investigation_shortlist`, Northstar has:

- safe local crawling and normalized store/product snapshots;
- a decision-focused Store Intelligence Report;
- provider-aware durable ads and a Northstar-owned public-ad library;
- official Meta imports and optional live GetHookd search;
- a narrowly permissioned Chrome/Edge active-tab capture extension;
- source-scoped ad metrics supporting exact, reported/rounded, range, percentile,
  classification, and unavailable values;
- an ad Analytics drawer separating provider metrics from Northstar observations;
- Similarweb traffic estimates and versioned planning ranges;
- evidence/confidence contracts that withhold unsupported claims;
- versioned user-entered product test economics; and
- a durable evidence-linked investigation shortlist with explicit test/reject workflow.

## Decision workspace — complete foundation

Northstar now provides a stable `/shortlist` workspace and idempotent add actions for
stores, products, and ads. Each item records priority, workflow stage, an explicit
investigate/test/reject decision, thesis, risks, next verification action, and optional
normalized evidence links. This replaces a low-information favorites feature without
turning user intent into an inferred product score.

## Product comparison — complete foundation

The stable `/compare` workspace compares two to five products from the known private
corpus. It shows observed catalog fields, collection span, associated collected ads,
typed evidence coverage, and the latest active user-entered economics scenario. It
exports the same comparison as JSON. Supplier matches, verified sales, review velocity,
and worldwide competitor counts remain explicitly unavailable.

Observed Products also supports local store, price, availability, variant, and recent
first-observation filters with safe CSV export. These are observed-catalog filters, not
sales velocity or “winning product” filters. Named filter views persist locally in the
browser for repeat research sessions.

Shortlist entries can also export a `research-dossier-v1` JSON bundle. The bundle
combines the user-authored investigation with the current entity contract and trust
notice; product dossiers include recent observations, active economics, related
collected ads, evidence, and explicit unavailable dimensions.

## Phase 1 — complete Ad Autopsy (complete)

### Outcome

Open a saved ad and understand the creative, analytics, advertiser, landing page,
store, product, offer, and major unknowns in one view.

### Work

- [x] Add a stable `/ads/:id` route and full-page Ad Autopsy.
- [x] Show provenance, media, explicit transcript/OCR state, copy, CTA, provider dates, analytics,
  and unavailable metrics.
- [x] Display landing-page collection state and current fetch failure diagnostics.
- [x] Resolve landing domains to existing stores or offer one-click investigation.
- [x] Show products reached through `AdLandingEdge → LandingProductEdge` relationships.
- [x] Show other ads sharing a landing record/domain, advertiser, platform ad ID,
  provider record, or resolved product.
- [x] Publish an explicit investigate / weak evidence / insufficient data conclusion.

Actual transcription, OCR, and normalized creative processing remain Phase 3 work;
Phase 1 explicitly displays their current `not collected` state.

### Dependencies

- Existing provider-aware ads, metric observations, and landing relationships.

### Completion criteria

- One captured ad can be followed to a collected landing page and store report.
- Every analytic value shows source and value kind.
- Missing impressions/spend/ROAS are visible as unavailable, not absent or zero.

## Phase 2 — source-specific capture and a first-party discovery corpus

### Outcome

Capture a public Meta, TikTok, or Google ad card accurately with little manual copying,
then search the accumulated private corpus.

### Work

- [x] Add versioned extension adapters for Meta Ad Library, TikTok Creative Center, and
  Google Ads Transparency Center.
- [x] Capture the selected card/nearby panel when available, retaining active-page
  fallback for pages without a selection.
- Extract advertiser, copy, media, CTA, source/landing URLs, dates, geography, and
  visible analytics when present.
- [x] Keep the generic selected-text adapter as fallback.
- [ ] Add capture preview/diff and partial-capture warnings. Preview and warnings are
  complete; a field-level previous-capture diff remains.
- [ ] Deduplicate by provider record, source URL, creative hash, and landing URL.
  Exact normalized source-URL recaptures now update in place; creative hashing and
  broader landing/provider-record consolidation remain.
- Add local filters for platform, advertiser, domain, format, source, date, geography,
  and available metric.

Progress: local free-text, platform, provider/source, creative-format, advertiser,
landing-domain, saved-metric, metric-geography, observation-window, saved/observed
date, and completed-delivery-duration ordering are available. Product filter presets
are reusable; ad-filter presets and arbitrary date ranges remain.

### Dependencies

- Provider/source provenance and metric schema (complete).
- Saved fixture pages for repeatable adapter tests.

### Completion criteria

- Fixtures for every supported source pass without network access.
- Duplicate capture updates observations without duplicating the ad.
- DOM changes create explicit partial results rather than incorrect fields.

## Phase 3 — creative transcription, OCR, and concepts

### Outcome

Understand what an ad says, how it is structured, and which ads are variants of the
same concept.

### Work

- Establish permitted asset storage/reference and retention rules.
- Extract duration, frames, audio transcript, and on-screen OCR.
- Segment hook, problem, demonstration, proof, offer, and CTA.
- Store normalized angle, persona, format, proof, offer, and objection tags.
- Compute image/video-frame perceptual hashes.
- Cluster near-duplicate variations separately from broader concepts.
- Show concept/variant counts, dates, and advertisers.

### Dependencies

- OCR/transcription provider or local-model decision.
- Normalized creative and creative-observation tables.

### Completion criteria

- Resized/reposted media clusters as a variation with inspectable similarity.
- AI labels cite transcript/OCR/frame evidence.
- No “winning concept” label appears without real performance evidence.

## Phase 4 — ad → landing page → store → product graph

### Outcome

Move from an ad to the underlying product opportunity without manually rebuilding the
relationships.

### Work

- Normalize redirects/tracking links to final public destinations.
- Classify funnels, listicles, advertorials, PDPs, and homepages.
- Associate landing pages to products through canonical URL, structured data, handle,
  image, and title evidence.
- Score association confidence and expose competing candidates.
- Group ads by underlying product across advertisers.
- Show the relationship graph and evidence supporting every edge.

### Completion criteria

- High-confidence direct product links resolve automatically.
- Ambiguous homepage/listicle links require confirmation.
- Ad counts never transfer to a product without a stored association edge.

## Phase 5 — product-page and offer teardown

### Outcome

See how a product page attempts to convert visitors and what could be tested
differently.

### Work

- Segment hero, benefits, demonstration, proof, reviews, guarantee, shipping, FAQ,
  comparisons, bundles, upsells, and CTA blocks.
- Detect sticky cart, subscriptions, quantity breaks, gifts, urgency, and payments.
- Capture annotated mobile/desktop screenshots.
- Score evidence coverage/page completeness—not conversion performance.
- Compare pages selling the same underlying product.
- Identify missing objection handling and differentiation opportunities.

### Completion criteria

- Every finding links to DOM or screenshot evidence.
- Urgency/dark-pattern detection is descriptive, not a success claim.

## Phase 6 — product similarity, competition, and diffusion

### Outcome

Determine whether stores sell the same underlying item and how differentiated the
observed market is.

### Work

- Image perceptual hashing and optional embeddings.
- OCR of model numbers, packaging, and specifications.
- Normalize titles, descriptions, variants, SKU/model, and dimensions.
- Create product clusters with match reasons/confidence.
- Show known-store count, price/offer distribution, advertiser count, creative-concept
  diversity, and first-observed distribution.
- Keep corpus coverage separate from worldwide-market claims.

### Completion criteria

- Similarity reports precision/recall on labeled fixtures.
- UI says “observed in N known stores,” never “N stores worldwide.”
- Saturation stays unavailable until coverage/category thresholds exist.

## Phase 7 — review velocity and customer-language mining

### Outcome

Find demand signals, complaints, desired outcomes, and differentiation ideas from
legitimate public reviews.

### Work

- Add adapters for selected public review platforms with source rules.
- Snapshot rating/count/distribution and collection time.
- Calculate velocity only across comparable dated observations.
- Extract motivations, complaints, delivery/quality issues, requests, and FAQs.
- Associate reviews to exact products or retain store-level scope.

### Completion criteria

- Review velocity requires multiple observations.
- Deleted/duplicated reviews do not become fake sales estimates.
- Recommendations cite themes without excessive reproduced text.

## Phase 8 — supplier matching and unit economics

### Outcome

Determine whether a product can be sourced and what ad economics a test requires.

### Work

Completed early dependency-independent slice:

- [x] Add versioned user-entered cost scenarios, contribution ranges, break-even
  CPA/ROAS, target CPA/ROAS, and explicit manual-input trust labeling.

Supplier-dependent work remains:

- Add authorized supplier/search connectors.
- Match through image, model/SKU, title, attributes, packaging, and variants.
- Preserve confirmed, likely, and possible supplier distinctions.
- Normalize unit price, shipping, MOQ, origin, delivery range, and rating.
- Calculate delivered-cost range, gross profit before ads, break-even CPA, and
  break-even ROAS.
- Allow versioned manual cost overrides.

### Completion criteria

- Economics show formula, assumptions, and ranges.
- Supplier confidence remains separate from margin attractiveness.
- No relationship is confirmed without direct evidence.

## Phase 9 — connect the user's own ad and commerce data

### Outcome

Compare public competitor patterns with real personal performance and economics.

### Work

- Optional read-only Meta Ads and Shopify connectors for the user's accounts.
- Import first-party impressions, reach, clicks, spend, conversions, CPA, ROAS,
  orders, contribution margin, refunds, and product results.
- Keep first-party data in a separate trust class from competitor observations.
- Match personal creatives to concepts and compare hooks/formats/offers.
- Add retention, deletion, and credential controls.

### Dependencies

- OS-backed/encrypted credential storage before broad first-party access.

### Completion criteria

- Every metric says “your account” or “competitor/public source.”
- Recommendations use contribution margin/test history when available.
- Disconnect/delete workflows are tested.

## Phase 10 — evidence-grounded opportunity and test planner

### Outcome

Receive a cited decision and original controlled test plan—not generic AI copy.

### Work

- Combine demand, advertising, competition, sourceability, economics, PDP quality,
  review gaps, and differentiation evidence.
- Add category-specific publication gates and calibrated ranges.
- Produce investigate/test/reject outcomes with evidence, risks, missing verification,
  and kill criteria.
- Generate original hook/angle matrices, scripts, storyboards, and landing-message
  briefs based on patterns rather than copied assets or wording.
- Record user tests and feed results into later recommendations.

### Completion criteria

- Every recommendation cites internal evidence IDs.
- Unsupported dimensions remain unavailable instead of receiving neutral scores.
- Generated concepts state differentiation rationale and controlled variables.

## Infrastructure work supporting all phases

- Durable scans, provider searches, tasks, retry state, and parent/child status.
- Resumable bounded collectors and source-coverage observations.
- Provider-neutral advertisers, creatives, destinations, associations, and metrics.
- Database retention/export/import tools and verified automatic backups.
- Frontend route/code splitting as the bundle grows.
- Fixture-based collector tests and migration tests for every revision.
- Credential encryption or OS-backed storage before first-party integrations.

## Explicitly deprioritized

- High-frequency price/theme monitoring without a decision use case.
- Fake live-sales notifications.
- Exact competitor revenue/profit/ROAS estimates from public catalog presence.
- Broad scraping intended to replicate a commercial provider's entire corpus.
- AI creative generation before evidence extraction and opportunity analysis work.
- Team billing, subscriptions, credits, and SaaS administration.

## Resume checklist

1. Read `README.md`, `IMPLEMENTATION_STATUS.md`, and this roadmap.
2. Confirm Alembic head and personal-database backup state.
3. Run backend tests and the frontend production build before editing.
4. Choose the earliest incomplete phase whose dependencies are satisfied.
5. Implement one end-to-end user outcome, not isolated fragments.
6. Add migration, API, service, UI, tests, and documentation together.
7. Update this roadmap and `IMPLEMENTATION_STATUS.md` with actual progress.
