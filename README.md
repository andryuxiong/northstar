# Northstar Commerce Intelligence

Northstar is a private, single-user e-commerce and dropshipping research workspace. It scans public storefronts, optionally imports real Similarweb and Meta Ad Library data using your credentials, and builds a decision-focused Store Intelligence Report.

It runs locally on Windows and has no subscriptions, billing, teams, artificial scan credits, or monthly scan quotas. Docker, PostgreSQL, Redis, and Celery are not required.

Northstar's central rule is simple: show an evidence-backed range or classification when the inputs support it; otherwise show `insufficient data`. It does not invent exact visitors, orders, sales, revenue, product performance, ad success, supplier relationships, or profit.

## Get the source

```powershell
git clone https://github.com/andryuxiong/northstar.git
```

Local databases, credentials, notification settings, logs, and installed dependencies are excluded from version control. A fresh checkout creates its own local runtime data.

## Quick start

From PowerShell:

```powershell
cd northstar
.\start-northstar.ps1
```

The launcher creates the Python environment and installs packages when needed, starts the API and UI on the loopback interface, upgrades the SQLite schema safely, and opens <http://127.0.0.1:5173>.

Stop it with:

```powershell
.\stop-northstar.ps1
```

Your database, provider imports, settings, evidence, and snapshots are preserved.

## What works now

- Safe, robots-aware crawling of public store, sitemap, collection, landing, and product URLs.
- Shopify and generic product parsing with immutable raw/normalized snapshots.
- Homepage brand/social identity, platform, market/category, offer, funnel, and selected technology detection.
- A unified report with Overview, Products, Traffic, Ads, Offers & funnel, Technology, Evidence, and Diagnostics.
- Versioned traffic, AOV, monthly-order, gross-revenue, store-momentum, and product-momentum estimators.
- Low/central/high ranges, separate confidence, evidence provenance, assumptions, missing signals, and algorithm versions.
- Editable, versioned estimation assumptions.
- Similarweb monthly visits and global-rank collection with partial states, retries, and a 24-hour credit-protection cache.
- A provider-neutral **Find ads** workspace with optional live GetHookd search and official Meta Graph API imports.
- A durable Northstar ad library for saving public ads with source, platform, creative, and landing-page provenance.
- Durable advertiser watches with explicit schedules, official Meta refreshes,
  recurrence history, collection-run diagnostics, and value-based retention
  tiers. TikTok/Google/manual targets remain honest paused queues until their
  official adapter or user capture is available.
- A stable full-page Ad Autopsy joining saved creative, provenance, analytics, landing diagnostics, resolved stores/products, and related ads.
- An unpacked Chrome/Edge capture extension that sends reviewed active-page ad evidence directly to the local library.
- Source-scoped ad analytics for exact values, rounded reports, ranges, percentiles, classifications, and explicit unavailable metrics.
- Versioned, user-entered product test economics with cost sensitivity, contribution margin, break-even CPA/ROAS, and target acquisition limits.
- A durable investigation shortlist for stores, products, and ads with thesis, risks, next action, priority, decision stage, and evidence links.
- A known-corpus product comparison matrix with observations, evidence coverage, related ads, saved economics, explicit unknowns, and JSON export.
- In-report review and confirmation of collected brand/social identity candidates.
- Safe legacy-database migration to the normalized intelligence/evidence schema.

The application deliberately keeps competitor clustering, saturation, supplier matching/cost, supplier-derived margin, complete creative intelligence, dropshipping likelihood, and the AI analyst unavailable until their required collectors and evidence coverage exist. Manual test economics are available but never presented as supplier evidence.

## Basic workflow

1. Open Northstar and choose **Investigate a store**.
2. Paste a public store root URL.
3. Let the homepage, sitemap, and product jobs collect available observations.
4. Open the Store Intelligence Report and inspect Overview, Evidence, and Diagnostics.
5. Optionally connect Similarweb and fetch traffic.
6. Optionally connect Meta and manually search the official Ad Library API for the detected brand.
7. Rescan over time to build real history; rapid same-day scans do not create product momentum.

Data labels are explicit:

- **Observed** — fetched from a public storefront.
- **Imported** — returned by an official provider such as Meta.
- **Provider estimate** — modeled by Similarweb, not first-party analytics.
- **Northstar estimate** — a versioned range calculated from disclosed inputs and assumptions.
- **Insufficient data** — a required input/evidence gate is missing.

## Documentation

Start with the [documentation index](docs/README.md).

- [Detailed user guide](docs/USER_GUIDE.md)
- [Intelligence formulas and confidence rules](docs/INTELLIGENCE_METHODOLOGY.md)
- [Similarweb and Meta integrations](docs/INTEGRATIONS.md)
- [Architecture, data flow, schema, and security](docs/ARCHITECTURE.md)
- [Local API reference](docs/API_REFERENCE.md)
- [Backups, migrations, testing, and troubleshooting](docs/OPERATIONS.md)
- [Completed, partial, and future capabilities](docs/IMPLEMENTATION_STATUS.md)
- [Detailed product roadmap and continuation plan](docs/PRODUCT_ROADMAP.md)
- [Repository/product audit](docs/NORTHSTAR_PRODUCT_AUDIT.md)
- [Existing-system gap review and completed fixes](docs/EXISTING_SYSTEM_GAP_REVIEW_2026-07-12.md)
- [Competitor benchmark and ranked improvement ideas](docs/COMPETITOR_BENCHMARK_2026.md)
- [Phased implementation plan](docs/IMPLEMENTATION_PLAN.md)

## Provider credentials

The easiest setup is **Settings & sources** in the UI. Credentials saved there are plaintext in `backend/data/integrations.json`; do not share or sync that file.

For environment-managed secrets:

```powershell
Copy-Item .env.example .env
```

Set `META_ADS_ACCESS_TOKEN`, `GETHOOKD_API_TOKEN`, and/or `SIMILARWEB_API_KEY`, then restart Northstar. Environment values take precedence and are never exposed to the frontend.

Meta API coverage is narrower than the public interactive Ad Library. GetHookd and Similarweb control their own entitlements and credit charges. See [Integrations](docs/INTEGRATIONS.md) before repeatedly calling a provider.

## Useful locations

- UI: <http://127.0.0.1:5173>
- API docs: <http://127.0.0.1:8000/docs>
- SQLite database: `backend/data/northstar.db`
- Automatic pre-migration backups: `backend/data/backups/`
- Raw/normalized snapshots: `backend/data/snapshots/`
- Runtime logs: `backend/data/logs/`
- Browser capture extension: `extension/`

## Verify the project

```powershell
Push-Location backend
try {
  .\.venv\Scripts\python.exe -m pytest tests -q
} finally {
  Pop-Location
}

cd frontend
npm run build
npm audit --omit=dev
cd ..

cd extension
node --test tests\adapters.test.js
cd ..
```

Backend tests use `backend/tests/.data/` and do not write to the personal database. At completion of the current implementation, 65 backend tests, 4 offline extension adapter tests, and the frontend production build passed.

## Safety and scope

Northstar only collects legally and technically accessible public pages and provider records available to your credentials. It validates DNS and redirects against private networks, respects `robots.txt`, limits response size and crawl rate, and does not bypass logins, CAPTCHAs, anti-bot controls, or private Shopify analytics.

The results are research signals, not audited business facts. Use them to decide what deserves deeper validation—not as proof that a store or product is profitable.
