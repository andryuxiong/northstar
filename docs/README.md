# Northstar documentation

- [Existing-system gap review (2026-07-12)](EXISTING_SYSTEM_GAP_REVIEW_2026-07-12.md)

This directory documents the personal-use Northstar implementation as it exists now. Start with the user guide, then use the more technical references when you need to understand a calculation, integration, database change, or API call.

## Documentation map

| Document | Use it for |
| --- | --- |
| [User guide](USER_GUIDE.md) | Installation, scanning stores, reading reports, finding/capturing public ads, fetching traffic, and changing assumptions |
| [Intelligence methodology](INTELLIGENCE_METHODOLOGY.md) | Exact v1 formulas, defaults, publication gates, confidence rules, evidence handling, and honesty limitations |
| [Integrations](INTEGRATIONS.md) | Similarweb and Meta credentials, provider coverage, cache/retry behavior, credit and rate-limit considerations, and public-data boundaries |
| [Architecture](ARCHITECTURE.md) | Frontend/backend structure, collection and analysis data flow, background jobs, database model groups, security controls, and technical limitations |
| [API reference](API_REFERENCE.md) | Supported local API workflows, authentication, report/settings/traffic/ad endpoints, and example PowerShell requests |
| [Operations and troubleshooting](OPERATIONS.md) | Logs, backups, safe migrations, restore procedures, tests, dependency audits, and common failures |
| [Implementation status](IMPLEMENTATION_STATUS.md) | What this implementation completed, what is partial, what is deliberately withheld, and the recommended next phases |
| [Product and repository audit](NORTHSTAR_PRODUCT_AUDIT.md) | The pre-implementation repository audit, preserved foundations, low-value UI findings, and original gaps |
| [Competitor benchmark](COMPETITOR_BENCHMARK_2026.md) | July 2026 competitor feature matrix, product decisions, and ranked improvement ideas |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | The phased design and calculation plan that guided this implementation |
| [Product roadmap](PRODUCT_ROADMAP.md) | Detailed future features, dependencies, evidence rules, completion criteria, and resume checklist |

## Fast path

From PowerShell in the repository root:

```powershell
.\start-northstar.ps1
```

Open <http://127.0.0.1:5173>, choose **Investigate a store**, and paste a public storefront URL. Docker is not required.

Northstar is intentionally conservative. `Insufficient data` is a valid result: it means the application does not have enough independent public or provider evidence to publish the requested estimate responsibly.
