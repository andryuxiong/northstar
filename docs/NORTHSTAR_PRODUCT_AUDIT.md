# Northstar product and repository audit

Date: 2026-07-10

> This is the point-in-time audit completed before the current intelligence implementation. Findings labeled “current” below describe that audited baseline, not the finished state. See [Implementation status](IMPLEMENTATION_STATUS.md) for the authoritative post-implementation inventory.

## What Northstar is today

Northstar is a local React/TypeScript and FastAPI application backed by SQLAlchemy and SQLite (WAL mode by default, with partial PostgreSQL support). Public collection runs in a bounded in-process thread pool. Raw HTML and normalized JSON snapshots are retained on disk. The crawler validates public destinations and redirects, respects `robots.txt`, rate-limits requests, limits response size, and parses sitemaps with entity and network resolution disabled.

The two external providers are real integrations, not demo feeds:

- Similarweb currently requests estimated visits and global rank, stores time series, and preserves partial/unavailable responses.
- Meta uses the official Graph API `ads_archive`, normalizes returned ads, and does not scrape the Ad Library UI. Official API coverage restrictions still apply.

The personal database at audit time contained one store, ten products, eleven product snapshots, no store snapshots, no traffic snapshots, and no ads. Nine products had one observation; one had two unchanged observations about an hour apart. That data cannot responsibly support claims about traffic, revenue, orders, store growth, winning products, or saturation.

## Architecture inventory

| Area | Current implementation | Assessment |
| --- | --- | --- |
| Frontend | React 18, TypeScript, Vite, Lucide, Recharts; one large `App.tsx` and global stylesheet | Working, but monolithic and organized around collection telemetry |
| API | FastAPI/Pydantic, synchronous SQLAlchemy sessions, JWT plus loopback local login | Good local foundation; several older routes lack workspace checks |
| Database | SQLite by default; SQLAlchemy models; Alembic revisions also exist | Existing local DB was created with `create_all` and is not Alembic-stamped; initial migration was PostgreSQL-specific |
| Background work | Bounded in-process `ThreadPoolExecutor` | Appropriate for personal use; jobs are volatile and not durable scan records |
| Store collection | Root URL creates a store, then requests a hard-coded HTTPS sitemap | No homepage/profile scan or fallback; nested scan budget is not store-wide |
| Product collection | Shopify and generic HTML parsers, current variants, immutable product snapshots | Useful raw history; Shopify extraction is often sparse and current variants lose identity on replacement |
| Landing collection | Saves page snapshot and extracts product links | Product-edge association races asynchronous product creation and is usually missing |
| Traffic | Similarweb visits/global rank and series | Real but narrow; no derived trend, reliability envelope, or credit cache |
| Ads | Official Meta API import with normalized core fields | Real but manual and not connected to store identities or products |
| Signals/scores | Generic mutable Signal/Score tables | Legacy implementation is not suitable for decision intelligence |
| Tests | 23 backend tests at audit time | Security/provider basics covered; estimator, report, migration, isolation, and complete/partial fixtures missing |

## Preserve

- SSRF, redirect, response-size, sitemap, and token-redaction protections.
- Raw product, landing-page, price, availability, variant, catalog, and provider observations.
- Store, product, variant, snapshot, traffic snapshot, ad, and landing-edge foundations.
- The real Similarweb and official Meta provider clients and their honest unavailable states.
- SQLite WAL, local task runner, integration credential masking, isolated test database, and local launcher.
- Existing provider/settings, empty-state, modal, card, table, chart, and status UI primitives where their semantics remain correct.

Raw observations remain available as estimator inputs and diagnostics. They are not deleted merely because the primary report no longer displays them.

## Remove or demote from the primary experience

- The legacy `winner` score. Every current product receives 20 points solely because no exact-title duplicate was found; zero matches in a one-store corpus is unknown, not evidence of uniqueness or demand.
- The legacy momentum score as a demand claim. It treats price changes, stock flips, and variant additions as positive momentum even though those events can have unrelated or opposite meanings.
- Fetch-count KPIs, collection-activity charts, raw source URLs, HTTP codes, job timestamps, and completed scan progress. Retain them under Scan Diagnostics.
- Availability, raw variant count, last-fetch time, chronological price/stock feeds, and serialized signal JSON as primary product intelligence.
- The inactive alert/tag surfaces until an evaluator and management workflow exist.
- `/library` as the main intelligence contract. It remains a compatibility and collection-summary endpoint.

## Correctness and architecture issues

1. Store scans do not fetch the homepage, extract a brand identity, or persist a store scan. `StoreSnapshot` is never populated and `Store.last_seen_at` is not maintained by the current scan path.
2. Landing-to-product edges are checked before asynchronous product creation and are not reconciled.
3. The legacy migration chain cannot safely initialize SQLite because revision 0001 uses PostgreSQL JSONB and GIN SQL. The live personal DB has no `alembic_version` row.
4. `/signals`, `/scores`, `/track`, `/recompute`, and alert reads have workspace-isolation gaps. The default `/products?sort=momentum` inner join hides products without a momentum score.
5. A store scan's product cap is applied per sitemap, not across the whole traversal. Cross-domain sitemap URLs and recursive depth need scan-level limits.
6. Provider refreshes have no freshness cache or retry/backoff policy. Similarweb refreshes may consume credits repeatedly.
7. Meta ads have no confirmed store identity, normalized advertiser/creative observations, or reliable ad-to-product association. Ad activity and longevity are evidence, never proof of sales.
8. Current money/rate columns use floats. New estimates and assumptions should use fixed-point numeric values.
9. The frontend performs broad polling of the full library, ads, auth, health, and provider status every five seconds, has no stable report URL, and converts some request failures into misleading empty states.

## Capability gap summary

### Fully or substantially present

- Safe public crawling and raw snapshot retention.
- Basic store/product catalog normalization.
- Real Similarweb visits/global-rank collection where credentials and plan allow.
- Official Meta Ad Library API import where access and coverage allow.
- Local personal-use runtime without Docker, billing, quotas, or subscriptions.

### Partial

- Product history, platform detection, landing-page capture, discount data, Meta fields, traffic time series, and confidence fields.
- These are data foundations, not yet decision-ready features.

### Missing before this implementation

- Unified store report; typed evidence and confidence; configurable assumptions; AOV/order/revenue ranges; traffic direction; defensible product ranking; brand/social identity; normalized offers/funnel/technology; durable scans; advertiser/creative/product matching; similarity clusters; competitors; suppliers/margins; saturation/opportunity; dropshipping likelihood; evidence-grounded AI analysis.

## Product decision

The correct first milestone is not an AI summary or a larger crawler dashboard. It is a trustworthy store report that can say either:

- what the evidence supports, as a range or classification with sources and assumptions; or
- `insufficient_data`, with the exact missing signals and next collection action.

The current store should produce an AOV planning range only if enough non-gift merchandise remains after classification. Orders and revenue must remain unavailable until monthly visits exist. Product momentum, saturation, supplier margin, and dropshipping likelihood must remain unknown until their required evidence is collected.
