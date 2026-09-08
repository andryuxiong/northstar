# Northstar architecture

Northstar extends the existing local application rather than replacing it. The raw crawler, snapshots, product history, official provider clients, and SQLite workflow remain in place. The new intelligence layer normalizes selected observations and builds versioned, evidence-backed reports above those foundations.

## Runtime stack

| Layer | Implementation |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Lucide icons, Recharts |
| API | FastAPI, Pydantic v2, synchronous SQLAlchemy sessions |
| Database | SQLite by default with foreign keys, WAL mode, 30-second busy timeout; SQLAlchemy/Alembic also contain PostgreSQL-compatible paths |
| Background work | Bounded in-process `ThreadPoolExecutor`; one worker by default |
| Public collection | `httpx`, BeautifulSoup, lxml, Shopify and generic parsers |
| External providers | Similarweb REST API and Meta Graph API `ads_archive` |
| Raw storage | Content-hashed HTML and normalized JSON files under `backend/data/snapshots/` |
| Schema management | Alembic through safe startup bootstrap/migration code |

Docker, Redis, Celery, and PostgreSQL are not required for the personal installation. SQLite is the exercised primary runtime. PostgreSQL support exists in the models and migrations but has not received the same live personal-workflow verification.

## Repository layout

```text
dropship-intel-mvp/
├── backend/
│   ├── alembic/                 # versioned database migrations
│   ├── app/
│   │   ├── api/                 # HTTP routes and Pydantic contracts
│   │   ├── core/                # settings and logging
│   │   ├── db/                  # SQLAlchemy models/session/schema bootstrap
│   │   ├── services/
│   │   │   ├── intelligence/    # pure estimators and report assembly
│   │   │   ├── parsers/         # Shopify and generic product parsers
│   │   │   └── ...              # crawling, providers, snapshots, identity
│   │   ├── utils/               # URL, hashing, and auth/security helpers
│   │   └── workers/             # task runner and collection tasks
│   ├── data/                    # personal DB, logs, snapshots, backups, secrets
│   └── tests/                   # isolated backend test suite
├── frontend/
│   └── src/                     # React application and API client
├── docs/                        # product, user, method, and engineering docs
├── .env.example
├── start-northstar.ps1
└── stop-northstar.ps1
```

## End-to-end data flow

```text
Public URL submitted
        │
        ▼
URL normalization and type classification
        │
        ├── store root ──► queue homepage + /sitemap.xml
        ├── sitemap ─────► queue same-domain product/nested sitemap URLs
        ├── collection ──► save landing snapshot + queue product links
        └── product ─────► parse and save product observation
        │
        ▼
SQLite normalized records + content-hashed disk snapshots
        │
        ├── public homepage profile/identity/offer/technology evidence
        ├── Similarweb traffic snapshots/observations, when requested
        └── Provider-labeled or user-saved ad records/landing relationships
        │
        ▼
Versioned deterministic estimators
        │
        ▼
Immutable analysis run + derived insights + evidence links
        │
        ▼
Store Intelligence Report API and decision-focused React UI
```

## Frontend

The frontend is currently one large `App.tsx` plus a shared stylesheet and API client. It uses browser history directly rather than a router dependency.

Primary routes:

- `/` — research overview;
- `/products` — collected product observations;
- `/stores` — store list and provider traffic refresh;
- `/ads` — durable provider-aware ad search plus optional live provider discovery;
- `/settings` — local provider credentials and estimation assumptions; and
- `/stores/:id/:tab` — stable report tabs.

Report tabs are Overview, Products, Traffic, Ads, Offers & funnel, Technology, Evidence, and Diagnostics.

The Overview separates directly observed storefront coverage from provider- or
history-gated estimates. Product catalog and report views use responsive cards
so product evidence remains readable without a bottom-only horizontal scrollbar.

The frontend polls the local engine approximately every 30 seconds while idle and every three seconds while background jobs are active, provided the page is visible. A fresh deep link performs loopback local login automatically when the token is missing or expired.

Current frontend limitations:

- no frontend unit/e2e test framework;
- one comparatively large application bundle;
- identity confirmation is not exposed fully;
- category-specific estimation profiles are API-only; and
- components should eventually be split out of `App.tsx` as features grow.

## API and authentication

FastAPI binds to `127.0.0.1:8000` in the launcher. The personal UI uses `POST /auth/local`, which is rejected unless the request comes from loopback. It creates or reuses `local@northstar` and a Personal workspace, then returns an eight-hour signed JWT.

The browser stores that token in local storage and sends it as a Bearer token. On an authenticated request returning 401, the API client performs one shared local-login refresh and retries once.

Most data queries are scoped to the current user's default workspace. The touched legacy signal/score/track/recompute/alert paths were tightened to verify workspace ownership.

This is convenient local authentication, not an internet-facing security model. Do not bind the personal application to a public interface or expose it through a tunnel without replacing the authentication, secret storage, deployment, and rate-limit design.

See [API reference](API_REFERENCE.md) for supported workflows.

## Background jobs

`backend/app/workers/runner.py` uses a bounded `ThreadPoolExecutor`. The default is one worker, configurable through `LOCAL_TASK_WORKERS`.

Each job has an in-memory ID, label, status, timestamps, error, and optional result. The task runner deliberately avoids Redis/Celery for a single-user application.

Important behavior:

- Jobs are not persisted and disappear when the API process restarts.
- A store-level job queues homepage and sitemap child jobs, then completes. Its completion does not mean every child product fetch has completed.
- The Diagnostics tab is the best place to inspect current source and matching job state.
- Each task uses its own database session.
- Failures preserve already committed observations and mark the relevant source failed; partial success does not roll back the entire store scan.

The current product cap is applied by homepage and individual sitemap handlers, not by a durable store-scan orchestration record. A nested sitemap scan can therefore schedule more than the configured value across the whole traversal. A durable scan model with a true store-wide budget remains future work.

## Storefront collection

### URL and crawl safety

The crawler:

- accepts only HTTP/HTTPS;
- resolves DNS before each request;
- rejects any host resolving to a private, local, reserved, or otherwise non-global address;
- revalidates every redirect and allows at most five redirects;
- respects `robots.txt` for the configured user agent;
- enforces a per-domain interval, one second by default;
- caps each fully decompressed response at 10 MB by default;
- retries a public page fetch up to three times for generic errors;
- parses sitemaps with DTD loading, entity resolution, external networking, and huge-tree mode disabled; and
- refuses cross-domain sitemap traversal within a store scan.

The crawler does not authenticate, bypass blocks, or evade site controls. A missing/unreachable robots file is treated as having no published rules, while an explicit disallow is honored.

### Homepage path

A store scan fetches the homepage and persists:

- a landing snapshot and outgoing product URLs;
- a `StoreSnapshot` containing the profile payload;
- the current `StoreProfile`;
- candidate `StoreIdentity` records;
- detected platform/category/market/currency/language where available;
- selected technology and funnel patterns; and
- offer candidates.

Brand candidates are drawn from organization schema, Open Graph/site name, logo alt text, page title, and domain. Social identity candidates come from organization `sameAs` values and public homepage links.

`StoreProfile` holds the latest normalized profile. Historical source material remains in snapshots and evidence rather than being flattened into the current row.

Technology discovery is layered. Known signatures provide canonical commercial
names, Shopify app blocks and extension asset slugs are parsed generically, and
previously unseen executable/style/iframe hosts are surfaced as low-confidence
unclassified integrations instead of being silently omitted. Infrastructure
hosts are filtered and aliases are deduplicated. A maintained signature catalog
or external provider can improve naming later without being the detection gate.

### Product path

Product pages use the Shopify parser when Shopify markers are present and otherwise the generic structured-data parser. A collection can retain:

- current normalized `Product` identity;
- current `ProductVariant` rows;
- immutable `ProductSnapshot` history;
- raw extracted JSON;
- content-hashed HTML/JSON disk snapshots; and
- landing-page relationships.

Shopify normalization merges its complementary public sources: inline product
objects provide variant/identity detail, while JSON-LD and Open Graph commonly
provide currency and images. When an older normalized snapshot has no image,
the API can recover the image from its immutable saved HTML through a bounded
content-hash cache; this does not create a new observation or rewrite history.

The current variants table is a latest-state representation and is replaced on each product fetch. Historical variant/price/availability material remains inside product snapshots.

Shopify locale-prefixed URLs such as `/fr/products/widget` normalize to `/products/widget`. Direct canonical/HTTP redirect evidence or a shared Shopify external product ID can consolidate duplicates while reassigning snapshots, edges, derived insights, evidence, tags, signals, scores, and alerts. Source URLs remain available for diagnostics.

### Relationship reconciliation

Landing pages are often fetched before their asynchronously queued products exist. Northstar now reconciles stored landing-product URLs after a product is created, preventing that scheduling race from permanently losing the edge.

These edges support conservative ad-to-product and homepage-merchandising evidence. They do not prove that a page receives paid traffic or that a product sells.

## Provider collection

Similarweb and Meta collection are source-specific services. Provider payloads are normalized without being mixed into the public crawler.

- Similarweb source responses are stored in `traffic_snapshots` and normalized into `traffic_observations`.
- Official Meta and user-saved public records are normalized into `ads` with separate
  `data_provider`, `source_type`, provider-record, and source-URL provenance. Landing
  URL edges connect durable records to collected pages.
- Provider timestamps remain distinct from Northstar `first_seen_at`/`last_seen_at` timestamps.
- Credentials remain backend-only.

See [Integrations](INTEGRATIONS.md) for exact provider behavior.

## Intelligence/report layer

The pure estimators accept typed normalized observations and return `InsightResult`. They do not query SQLAlchemy or call a network. This keeps formulas deterministic and unit-testable.

The report service:

1. loads the store and latest profile;
2. chooses the active category profile or falls back to `general_ecommerce`;
3. normalizes traffic observations;
4. identifies current catalog products while retaining historical products in storage;
5. classifies likely sellable merchandise;
6. runs traffic, AOV, orders, revenue, store momentum, product momentum, ad availability, and unsupported-state builders;
7. assembles offer/funnel/technology sections;
8. computes a fingerprint containing inputs, settings, versions, identities, relationships, ads, history, and freshness date;
9. creates an immutable `AnalysisRun`;
10. persists typed `DerivedInsight` rows and content-addressed `EvidenceRecord` links; and
11. returns the unified report.

A report `GET` is therefore not completely read-only: it creates an immutable analysis snapshot each time it is opened. This provides audit history but can grow the local database over time. A report-history/retention UI is not yet implemented.

Legacy `Signal` and `Score` rows remain for compatibility and raw downstream possibilities. The Store Intelligence Report and primary product UI no longer use the legacy winner/momentum score because it turned weak catalog changes into misleading business claims.

## Database model groups

### Ownership and collection

| Tables | Purpose |
| --- | --- |
| `users`, `workspaces` | Local identity and ownership boundary |
| `source_urls` | Submitted/discovered URL, type, fetch state, HTTP diagnostics |
| `stores`, `store_profiles`, `store_identities` | Store identity, latest normalized profile, public identity candidates/confirmation |
| `products`, `product_variants`, `product_snapshots` | Product entity, current variants, immutable observations |
| `store_snapshots`, `landing_page_snapshots` | Store/homepage and landing-page observation history |
| `ad_landing_edges`, `landing_product_edges` | Relationships among ads, pages, and products |
| `traffic_snapshots`, `traffic_observations` | Provider-specific traffic response and normalized period metrics |
| `ads` | Provider-aware official imports and user-saved public ad evidence |
| `ad_metric_observations` | Source-scoped exact/reported/range/percentile/classification/unavailable ad analytics |
| `product_economics_scenarios` | Immutable revisions of user-entered product cost and acquisition-planning scenarios |
| `investigation_items` | User-authored store/product/ad thesis, risks, next action, workflow, priority, and decision |
| `investigation_evidence_links` | Workspace-validated citations from shortlist items to normalized evidence records |

### Intelligence

| Tables | Purpose |
| --- | --- |
| `estimation_profiles` | Versioned, category-keyed adjustable assumptions and score weights |
| `analysis_runs` | Immutable report execution envelope and input fingerprint |
| `derived_insights` | Typed range, score, or classification with confidence, assumptions, missing signals, and estimator version |
| `evidence_records` | Typed provenance with source links, independence group, value, reliability, time, and collector version |
| `insight_evidence` | Many-to-many attribution between a derived insight and its evidence |

### Preserved legacy/supporting models

`tags`, `tag_assignments`, `signals`, `scores`, `alert_rules`, and `alert_events` remain in the schema. They are not part of the primary intelligence report. Keeping them avoids deleting historical data that may still support future derived signals or compatibility routes.

## Snapshot and file storage

Personal runtime material is under `backend/data/`:

- `northstar.db`, `northstar.db-wal`, `northstar.db-shm` — SQLite;
- `snapshots/html/` — content-hashed page bodies;
- `snapshots/json/` — normalized extracted snapshot payloads;
- `backups/` — automatic pre-migration SQLite backups and explicit maintenance backups; and
- `logs/` — API/UI stdout and stderr.

Snapshot storage is intentionally append-oriented. Do not delete it merely because raw changes are hidden in the UI; the history can support discount persistence, catalog movement, product longevity, restock evidence, and future estimators.

## Configuration

The repository-root `.env` is loaded by the backend. Important settings and defaults include:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | local `backend/data/northstar.db` | Alternate SQLAlchemy database URI |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed UI origin |
| `USER_AGENT` | `NorthstarPersonalResearch/1.0` | robots/crawl user agent |
| `CRAWL_MIN_INTERVAL_SECONDS` | `1` | per-domain crawl interval |
| `MAX_PRODUCTS_PER_SCAN` | `100` | current per-handler scheduling cap |
| `MAX_RESPONSE_BYTES` | `10000000` | decompressed response limit |
| `LOCAL_TASK_WORKERS` | `1` | background thread count |
| `MIRROR_PRODUCT_IMAGES` | `false` | image mirroring option retained in settings |
| `META_ADS_ACCESS_TOKEN` | empty | Meta credential |
| `META_GRAPH_VERSION` | `v25.0` | Meta Graph version |
| `SIMILARWEB_API_KEY` | empty | Similarweb credential |

The default `APP_SECRET` is generated at process import when no environment value is set. That invalidates existing JWTs after restart, which the local UI handles by obtaining a fresh loopback token. Set a long fixed `APP_SECRET` in `.env` if you need stable tokens.

## Current architecture limitations

- Background job and store-scan orchestration is not durable.
- A report open creates another analysis run; no retention policy is present.
- The app remains optimized for one local user, not multi-tenant SaaS operations.
- Homepage offers/funnel/technology are stored in flexible profile JSON rather than fully normalized observation tables.
- Meta search coverage and advertiser/creative entities are not separately normalized.
- Review collection, product clusters, competitor relationships, supplier matches, saturation, supplier-derived cost/margin, and AI analysis do not exist yet. User-entered test economics are stored separately and do not establish a supplier relationship.
- Current product-history collection is useful but not a complete inventory ledger.
- SQLite is the verified runtime; live PostgreSQL validation remains limited.

See [Implementation status](IMPLEMENTATION_STATUS.md) for product-facing completion details and the recommended next phases.
