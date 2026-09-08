# Northstar competitor benchmark — July 2026

This point-in-time benchmark uses competitors' own public product pages and help
centers. Marketing claims are recorded as claims, not independently verified facts.
Northstar must not copy claims such as exact competitor sales, spend, orders, or ROAS
when available evidence cannot support them.

## Products reviewed

- [PPSPY Shopify Spy](https://www.ppspy.com/shopify-spy)
- [ShopHunter](https://www.shophunter.io/)
- [Dropship.io 2.0](https://help.dropship.io/en/articles/9329212-getting-started-with-dropship-io-2-0)
- [Dropship.io Competitor Research](https://www.dropship.io/solutions/competitor-research)
- [Minea AdSpy](https://www.minea.com/adspy)
- [Koala Inspector](https://koala-apps.io/learn-more/)
- [Similarweb Website Performance](https://support.similarweb.com/hc/en-us/articles/360010749958-View-Website-Performance)
- [BuiltWith features](https://builtwith.com/all-features)

## Capability matrix

| Capability competitors promote | Northstar July 2026 | Decision |
| --- | --- | --- |
| Large cross-store product, store, and ad corpus | Private user-built corpus plus optional provider search | Do not attempt broad scraping. Improve capture, import, search, comparison, and coverage labels. |
| Real-time/exact competitor sales, orders, revenue, spend, or ROAS | Honest ranges or unavailable states | Preserve Northstar's stricter boundary. Never convert public catalog/ad presence into exact performance. |
| Store/product/ad search with advanced filters and presets | Basic product search; improving ad filters | Add local facets, saved research views, CSV/JSON export, and corpus coverage counts. |
| Product/store watchlists and change alerts | Historical snapshots; legacy tracking is incomplete | Add durable investigation watchlists only after durable scan/task state exists. |
| Theme and installed-app detection | Platform plus selected business-purpose technologies | Expand theme/app fingerprints with evidence and history, without claiming exhaustive coverage. |
| Traffic channels, geography, engagement, keywords, and comparisons | Similarweb visits/global rank only | Add metrics only when configured provider entitlements return them; compare existing observations side by side. |
| Ad creative analysis, transcript, OCR, concepts, and similar ads | Explicit not-collected states; product/landing related ads | Continue permitted media pipeline, hashes, concepts, and cited extraction in Phase 3. |
| Ad-to-product-to-supplier workflow | Ad-to-landing-to-store/product graph; no supplier connector | Strengthen association evidence first, then add authorized supplier connectors. |
| Profit calculator, break-even CPA/ROAS, shipping and product-cost scenarios | **Implemented:** versioned user-entered test economics with formulas and ranges | Continue supplier integration later; never convert manual costs into supplier evidence. |
| Product similarity and competitor counts | Not implemented | Add image/title/model matching with labeled fixtures and known-corpus denominators. |
| Favorites, portfolio, notes, and curated shortlist | **Implemented:** evidence-linked decision shortlist for stores, products, and ads | Continue with saved filter presets and dossier export. |
| Export/import | Raw DB and documents only | Add scoped CSV/JSON dossier exports after comparison/search contracts stabilize. |

## Ranked improvement ideas

1. **Test economics planner — implemented.** Selling price, landed cost, payment fee, fulfillment,
   refund allowance, target margin, break-even CPA, break-even ROAS, and scenario
   sensitivity. User-entered values remain distinct from observed or supplier data.
2. **Investigation shortlist — implemented.** Save products/ads/stores with thesis, risks, next
   verification action, status, and cited evidence IDs.
3. **Product comparison matrix — implemented foundation.** Compare price, variants, corpus age, traffic
   evidence, ads, offer coverage, and economics without global-market claims.
4. **Advanced local corpus search — product and ad foundations implemented.** Reusable presets and remaining cross-entity facets,
   reusable presets, and coverage-aware result counts.
5. **Research dossier export — JSON foundation implemented.** Portable JSON and future readable HTML/CSV with provenance,
   assumptions, unavailable fields, and generation time.
6. **Traffic comparison** — side-by-side observed Similarweb periods and ranks across
   selected saved stores, with provider coverage/freshness visible.
7. **Theme/app fingerprint expansion** — evidence-backed fingerprints and technology
   change history, emphasizing business function over exhaustive vendor lists.
8. **Creative processing** — permitted asset references, transcript/OCR, hashes,
   normalized concepts, and variants with evidence citations.
9. **Review velocity/customer language** — public-source adapters, comparable dated
   observations, and cited themes.
10. **Supplier matching** — authorized connectors, match confidence, landed-cost
    normalization, and explicit confirmed/likely/possible states.

## Implementation policy

- Prefer complete one-session investigation outcomes over dashboard volume.
- Separate observed, provider-reported, provider-estimated, Northstar-estimated, and
  user-entered values in storage and presentation.
- Every derived value exposes its formula, assumptions, version, and missing inputs.
- Corpus counts always say “known Northstar corpus,” never worldwide coverage.
- Provider calls remain optional, credential-scoped, cached where appropriate, and
  explicit about credits or entitlement limitations.
