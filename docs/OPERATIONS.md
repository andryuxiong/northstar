# Operations, backups, migrations, and troubleshooting

This guide is for the local Windows/PowerShell installation. Northstar is a personal research tool, not a production service, so operational simplicity and data preservation take priority over distributed infrastructure.

## Normal start and stop

From the repository root:

```powershell
.\start-northstar.ps1
```

Stop it with:

```powershell
.\stop-northstar.ps1
```

The stop script terminates listeners on ports 5173 and 8000. It does not delete the database or snapshots.

The backward-compatible `start-local.ps1` simply calls `start-northstar.ps1`.

## Runtime files

| Location | Contents |
| --- | --- |
| `backend/data/northstar.db` | Primary SQLite database |
| `backend/data/northstar.db-wal` | SQLite write-ahead log while running |
| `backend/data/northstar.db-shm` | SQLite shared-memory file while running |
| `backend/data/snapshots/html/` | Content-hashed public HTML snapshots |
| `backend/data/snapshots/json/` | Content-hashed normalized extraction snapshots |
| `backend/data/integrations.json` | Optional plaintext locally saved provider credentials |
| `backend/data/backups/` | Automatic pre-migration and manual database backups |
| `backend/data/logs/api.log` | API standard output |
| `backend/data/logs/api-error.log` | API/migration/traceback standard error |
| `backend/data/logs/ui.log` | Vite standard output |
| `backend/data/logs/ui-error.log` | Vite standard error |

Do not commit the data directory or integration credential file. The snapshots and history can become large; preserve them unless you deliberately accept losing historical evidence.

## Logs

Tail a log in a separate PowerShell window:

```powershell
Get-Content .\backend\data\logs\api-error.log -Wait
```

For the UI:

```powershell
Get-Content .\backend\data\logs\ui-error.log -Wait
```

The launcher redirects the two processes into these files. If startup times out, inspect both the normal and error logs before retrying.

## Database migrations

The current expected Alembic head is:

```text
0009_investigation_shortlist
```

FastAPI calls the safe schema upgrader during startup before accepting requests.

### Fresh database

An empty database is upgraded through the normal Alembic chain. Revision 0001 is dialect-safe for SQLite and PostgreSQL JSON variants; PostgreSQL-only GIN behavior is not applied to SQLite.

### Legacy unversioned personal database

Early Northstar versions created tables directly without an `alembic_version`. The startup upgrader does not blindly stamp such a file. It:

1. makes a transactionally consistent SQLite backup;
2. runs `PRAGMA integrity_check` on that backup;
3. verifies the expected legacy tables and key columns;
4. applies only known additive gaps through the 0004 baseline;
5. stamps the verified baseline; and
6. upgrades normally through 0009.

If the schema is partial or unknown, startup stops with `SchemaBootstrapError` instead of guessing. The error includes the backup location when one was created.

### Existing versioned database

When the database is behind head, the SQLite upgrader makes a pre-migration backup and applies the normal Alembic chain. When it is already at 0009, it returns without another backup.

### Inspect the revision

With Northstar stopped or running:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic current
cd ..
```

You can also inspect the version directly:

```powershell
.\backend\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'backend/data/northstar.db'); print(c.execute('select version_num from alembic_version').fetchall()); c.close()"
```

Do not run an Alembic downgrade against the personal database casually. The 0009 downgrade removes investigation shortlist items and citations, 0008 removes saved product economics scenarios, 0007 removes ad metric observations, 0006 removes ad provenance fields, and 0005 drops the analysis/evidence foundation tables.

## Manual backup

Automatic backups are migration backups, not a general backup schedule. Make a manual backup before risky maintenance or periodically if the research matters.

The safest simple process is to stop Northstar first so the WAL is checkpointed, then copy the database:

```powershell
.\stop-northstar.ps1
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force .\backend\data\backups | Out-Null
Copy-Item `
  .\backend\data\northstar.db `
  ".\backend\data\backups\northstar.manual.$stamp.db"
```

If provider credentials matter, back up `backend/data/integrations.json` separately into an encrypted/private location. Do not place it in a normal source-control backup.

Snapshots are outside the database. Back up `backend/data/snapshots/` as well if you need a complete research archive.

## Verify a SQLite backup

```powershell
.\backend\.venv\Scripts\python.exe -c "import sqlite3,sys; p=sys.argv[1]; c=sqlite3.connect(p); print(c.execute('pragma integrity_check').fetchone()[0]); c.close()" .\backend\data\backups\your-backup.db
```

The expected result is `ok`.

## Restore a database backup

Stop Northstar. Preserve the current files instead of deleting them, then copy the selected backup into place:

```powershell
.\stop-northstar.ps1
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Move-Item .\backend\data\northstar.db ".\backend\data\northstar.before-restore.$stamp.db"
if (Test-Path .\backend\data\northstar.db-wal) {
  Move-Item .\backend\data\northstar.db-wal ".\backend\data\northstar.before-restore.$stamp.db-wal"
}
if (Test-Path .\backend\data\northstar.db-shm) {
  Move-Item .\backend\data\northstar.db-shm ".\backend\data\northstar.before-restore.$stamp.db-shm"
}
Copy-Item .\backend\data\backups\your-backup.db .\backend\data\northstar.db
.\start-northstar.ps1
```

Starting the current application automatically upgrades an older backup to the current head. If you are investigating a migration failure, keep the application stopped and inspect/copy the backup first; otherwise it will attempt the same migration again.

Database restore does not alter snapshot files. A backup and snapshot directory from different points in time may not form a perfectly matched archive.

## Start with a fresh database without destroying the old one

Only do this when you intentionally want an empty local index:

```powershell
.\stop-northstar.ps1
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Move-Item .\backend\data\northstar.db ".\backend\data\northstar.archived.$stamp.db"
if (Test-Path .\backend\data\northstar.db-wal) {
  Move-Item .\backend\data\northstar.db-wal ".\backend\data\northstar.archived.$stamp.db-wal"
}
if (Test-Path .\backend\data\northstar.db-shm) {
  Move-Item .\backend\data\northstar.db-shm ".\backend\data\northstar.archived.$stamp.db-shm"
}
.\start-northstar.ps1
```

The old snapshots are not automatically reindexed into the fresh database. Move or archive them separately if you want an entirely clean data directory.

## Automated verification

### Backend tests

From the repository root:

```powershell
Push-Location backend
try {
  .\.venv\Scripts\python.exe -m pytest tests -q
} finally {
  Pop-Location
}
```

The test bootstrap sets `DATABASE_URL` and `INTEGRATION_CONFIG_PATH` before the application imports, so automated tests use:

```text
backend/tests/.data/northstar-test.db
backend/tests/.data/integrations-test.json
```

They do not write to `backend/data/northstar.db` or the personal integration file. Migration tests use additional temporary databases.

At completion of this implementation, the backend suite reported 54 passing tests. Coverage includes:

- crawler SSRF/redirect/robots/size safety;
- secure sitemap parsing;
- Shopify/generic parsing and product identity consolidation;
- Meta normalization/token redaction/provider errors;
- Similarweb partial/unavailable normalization;
- store profile extraction;
- estimator low/medium/high/missing/stale cases;
- immutable report/evidence runs and workspace isolation;
- traffic credit cache; and
- fresh and unversioned-legacy migration paths.

### Frontend build

```powershell
cd frontend
npm run build
cd ..
```

This runs TypeScript/Vite production compilation. The frontend currently has no unit/e2e test runner; verification is build plus manual/headless visual inspection. Vite may report a large-chunk warning for the monolithic application bundle; that is a performance follow-up, not a build failure.

### Dependency audits

Frontend production dependencies:

```powershell
cd frontend
npm audit --omit=dev
cd ..
```

Backend:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install pip-audit
.\backend\.venv\Scripts\python.exe -m pip_audit -r .\backend\requirements.txt
```

`pip-audit` is an optional verification tool and is not pinned in the application requirements.

## Troubleshooting

### `start-northstar.ps1` times out

Inspect:

```powershell
Get-Content .\backend\data\logs\api-error.log -Tail 100
Get-Content .\backend\data\logs\ui-error.log -Tail 100
```

Common causes are missing `python`/`npm`, package-install failure, a schema bootstrap refusal, or another process occupying port 8000/5173.

Check listeners:

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue
```

The launcher considers an existing listener ready if the expected health endpoints respond. Do not run unrelated services on those ports.

### UI says the local engine is offline

Confirm:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/snapshots/health
```

If that fails, restart Northstar and inspect the API error log. If the API works but the UI does not, inspect `ui-error.log` and verify <http://127.0.0.1:5173>.

### A deep link reports `Not authenticated`

The current API client should perform loopback local login and retry once. Hard-refresh the page. If it persists, clear the `token` value from the browser's local storage and reload, or restart the backend so the UI obtains a token signed by the current `APP_SECRET`.

### A scan shows 403

Possible reasons:

- `robots.txt` disallows the configured user agent;
- DNS or a redirect resolved to a non-public address; or
- the target returned HTTP 403.

Northstar does not bypass these conditions. Check the source entry in Diagnostics and the public page manually.

### A scan shows 413

The response exceeded `MAX_RESPONSE_BYTES` after decompression (10 MB by default). Increase the limit only if you understand the memory/storage consequence and the target is trusted enough for the research use case, then restart the backend.

### A scan parent job completed but products are still loading

This is expected with the in-process fan-out design. The store job queues homepage and sitemap work; those tasks queue product work. Watch source states and matching jobs in Diagnostics. The UI polls faster while jobs are active.

### A product appears more than once

Shopify locale-prefixed URLs and proven redirect aliases are consolidated conservatively. Duplicates can remain if the store exposes genuinely different URLs without a common handle, external ID, canonical URL, or direct redirect proof. Northstar avoids title-only merging because two similar titles do not prove identical products.

### Traffic is partial or unavailable

Inspect the metric-specific status. One Similarweb endpoint may be outside your plan even when the other succeeds. Other causes include credits, unavailable dates/countries, no provider data, rate limits, or an invalid key. Global rank alone never creates a visits range.

### Traffic refresh returns old data

Successful/partial exact-scope snapshots are reused for 24 hours. The response includes `cached: true`. Use the API's `force: true` only when a new paid provider request is intended.

### Meta returns no ads

Check:

- official API token eligibility;
- reached country and delivery dates;
- query/page ID spelling;
- Meta's current API coverage; and
- the structured provider error.

The official API is narrower than the public website. Empty results are Unknown, not proof of no ads.

### A report shows `insufficient data` after a successful scan

Successful collection and sufficient decision evidence are different states. Typical missing inputs are:

- Similarweb monthly visits for orders/revenue;
- at least five eligible single-currency products for AOV;
- at least three consecutive months for store direction;
- at least two independent product evidence groups plus 14 days for product momentum;
- recent scoped ad coverage;
- reviews, competitor clusters, supplier matches, or cost data that are not yet collected.

Open **Inspect basis**, **Evidence**, and **Diagnostics**. Do not repeatedly rescan in one session to try to force a score.

### Database migration refuses to start

Read the `SchemaBootstrapError` in `api-error.log`. The upgrader refuses unknown partial schemas. Preserve the automatic backup, run its integrity check, and compare the error's missing tables/columns before changing anything. Do not manually stamp an unverified database.

### SQLite reports `database is locked`

SQLite uses WAL and a 30-second busy timeout. Stop duplicate API processes and use one Northstar instance against the file. Avoid opening the database in another tool with a long write transaction. Restart after the other writer releases it.

## What not to treat as an operational error

- `Insufficient data` can be the correct intelligence result.
- A partial provider snapshot is intentionally preserved.
- A missing current-ad count is safer than treating missing stop dates as active.
- A product remaining unranked is expected until its publication gate is met.
- Technical HTTP/job timestamps are diagnostics, not business metrics.
