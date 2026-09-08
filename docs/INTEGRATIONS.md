# External integrations

Northstar works without external credentials, but provider-backed traffic and ad records require your own Similarweb, Meta, or GetHookd access. The integrations use documented provider APIs; they are not demo feeds and do not scrape provider websites.

Provider access, fields, retention, billing, and rate limits are controlled by the providers and can change independently of Northstar. Check the provider's current documentation and your account entitlements before relying on a request.

Official references used by this implementation:

- [Similarweb visits API](https://developers.similarweb.com/reference/visits)
- [Similarweb global rank API](https://developers.similarweb.com/reference/global-rank)
- [Meta Ad Library API](https://www.facebook.com/ads/library/api/)
- [GetHookd public API](https://www.gethookd.ai/api/)

## Credential storage and precedence

You can configure credentials in either of two ways.

### Option A: environment file

From the repository root:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set one or both values:

```dotenv
META_ADS_ACCESS_TOKEN=your-token
GETHOOKD_API_TOKEN=your-token
SIMILARWEB_API_KEY=your-key
```

Environment credentials take precedence over credentials saved through the UI. The Settings screen labels such a credential as managed by the environment. Removing a UI-saved credential does not remove an environment value.

The backend reads the repository-root `.env` when it starts. Restart Northstar after editing it.

### Option B: Settings UI

Open **Settings & sources** and save the credential on this computer. Northstar writes it to:

```text
backend/data/integrations.json
```

The file is plaintext. Northstar attempts restrictive file permissions where supported, but Windows `chmod` does not guarantee an exclusive ACL. Do not commit, share, email, or cloud-sync this file. Provider status responses return only masked values; they never return the full secret.

The frontend never receives or bundles the configured secret. Provider requests are made by the backend.

## Similarweb

### What the integration does

Northstar currently calls these Similarweb REST paths:

- `global-rank/global-rank` for global rank; and
- `total-traffic-and-engagement/visits` for monthly visits.

Both are called under `/v1/website/<domain>/...`. The visits request uses monthly granularity and the selected country, while both requests honor the requested period and `main_domain_only` setting.

The provider response is stored in two forms:

- `traffic_snapshots`: the source-specific result, including series, status for each metric, fetch state, request scope, and provider last-updated value; and
- `traffic_observations`: normalized per-period metrics used by the intelligence estimators.

Similarweb visits are provider estimates. They are not exact live visitors, sessions from a merchant dashboard, or Northstar measurements.

### Connect through the UI

1. Obtain a Similarweb REST API key with access to the requested endpoints.
2. Open **Settings & sources**.
3. Save the key under **Similarweb API**.
4. Open **Stores & traffic**.
5. Choose **Fetch previous month** on an observed store.

The UI requests the previous completed month, worldwide, and the main domain.

### Provider credits

A normal one-month refresh makes two provider metric requests: one for monthly visits and one for global rank. It may consume up to two Similarweb results/data credits, subject to Similarweb's current account and billing rules.

The API can request a range of up to 12 months, but provider credit use for multi-month requests is controlled by Similarweb. Do not assume it costs the same as a one-month refresh.

The **Test connection** API also calls both paid endpoints and does not persist or cache the result. It can therefore consume provider credits.

### 24-hour credit-protection cache

Before calling Similarweb, a normal refresh looks for a successful or partial snapshot collected in the preceding 24 hours with the exact same:

- workspace;
- normalized domain;
- start and end month;
- country; and
- `main_domain_only` value.

If found, Northstar reuses it and returns `cached: true` with a cache notice. Unavailable or failed snapshots are not reused by this cache.

The local API accepts `force: true` to bypass the cache. Use it deliberately because it causes new provider requests. The current UI does not expose a force toggle.

### Partial and unavailable results

Each metric is evaluated independently. A refresh is:

- `success` when both metrics succeed;
- `partial` when only one succeeds; or
- `unavailable` when neither succeeds.

Northstar persists partial and unavailable responses so the report can distinguish no data, plan restriction, credits, rate limiting, and provider failure. It never fabricates the missing metric and never converts global rank into visits.

Common normalized provider states include:

- `access_or_credits` for an invalid/inactive key, exhausted credits, or a metric outside the plan;
- `rate_limited` for HTTP 429;
- `data_not_found_or_unauthorized` for a no-data/authorization response;
- date, granularity, or country not available;
- `provider_error` for server errors;
- `network_error`;
- `invalid_response`; and
- `no_data`.

### Retry and timeout behavior

Each metric request has a 30-second client timeout and up to three attempts for network errors, HTTP 429, and provider 5xx responses. Backoff begins at 0.5 seconds and doubles. A numeric `Retry-After` value is honored but capped at five seconds. Non-retryable provider rejections return immediately.

### Metrics not currently collected

The implementation does not currently request:

- country rank;
- category rank;
- top countries;
- direct/search/social/referral/display/email/paid-search channels;
- visit duration;
- pages per visit; or
- bounce rate.

The report lists unavailable traffic metrics instead of filling them from another source or attributing supplemental indicators to Similarweb.

### Relevant API endpoints

- `GET /integrations/similarweb/status`
- `PUT /integrations/similarweb/config`
- `DELETE /integrations/similarweb/config`
- `POST /integrations/similarweb/test`
- `POST /traffic/stores/{store_id}/refresh`
- `GET /traffic/stores/{store_id}`
- domain equivalents under `/traffic/domains/{domain}`

See [API reference](API_REFERENCE.md#similarweb-traffic) for examples.

## Meta Ad Library

### What the integration does

Northstar calls Meta's official Graph API:

```text
https://graph.facebook.com/<configured-version>/ads_archive
```

The default configured version is `v25.0` and can be changed with `META_GRAPH_VERSION` if the code and provider contract are reviewed for a newer version.

Northstar does not scrape the public Ad Library UI. It normalizes and upserts returned public records by workspace, platform, and Meta external ad ID.

Normalized fields can include:

- external ad ID;
- advertiser/page name and ID;
- creative body and headline;
- call to action;
- provider creation, delivery-start, and delivery-stop times;
- publisher platforms;
- creative asset URLs when returned;
- landing URL when returned; and
- a safe public Ad Library permalink.

Meta's provider snapshot URLs can embed a caller token. Northstar never stores that provider URL directly: it stores a public `facebook.com/ads/library/?id=<ad-id>` permalink. Known `access_token` and `appsecret_proof` query parameters are stripped from other normalized URLs before storage or API output.

### Provider coverage is narrower than the website

The application displays this coverage warning based on the [official Meta Ad Library API](https://www.facebook.com/ads/library/api/) contract used during implementation:

- issue, election, and political ads have worldwide API coverage for the provider's published seven-year window; and
- ads of any type delivered to the UK/EU are available for the provider's published one-year window.

This is not worldwide coverage of every commercial or dropshipping ad. Meta controls current eligibility, geography, retention, and fields. The public interactive Ad Library may expose searches that the API does not return to your token.

An empty API search is therefore not proof that a brand has no ads.

### Connect and search through the UI

1. Follow Meta's current Ad Library API authorization process.
2. Open **Settings & sources**.
3. Save the eligible Meta access token.
4. Open **Find ads** and select **Official Meta API**.
5. Enter a brand/advertiser search term and a reached country.
6. Run the search.

The synchronous UI search requests at most 500 records. The default is 50. The client follows Meta cursors while rebuilding every request against the configured Graph host; it does not follow arbitrary provider paging URLs.

The API requires either search terms or numeric Meta page IDs. Reached-country values are two-letter codes or `ALL`, subject to Meta's contract. Optional active status is `ACTIVE`, `INACTIVE`, or `ALL`, and optional delivery dates use `YYYY-MM-DD`.

### Retry, timeout, and error behavior

Meta requests use a 30-second total timeout with a 10-second connect timeout. Network errors, HTTP 429, and 5xx responses receive up to three attempts with the same bounded exponential/`Retry-After` behavior as Similarweb.

Provider error messages are normalized and redacted so the configured token is not echoed in an API error. Northstar returns an explicit provider error shape instead of fabricated empty records.

Meta searches do not currently have a 24-hour result cache. Repeated searches call the provider again and should respect Meta's rate limits.

### Store identity and association state

A storefront scan extracts candidate brand, Facebook, and Instagram identities from public homepage metadata and links. Those candidates have source and confidence fields and can be confirmed through the identity API.

The following are partial rather than complete:

- automatic searching of every identity candidate is not implemented;
- the frontend exposes candidate source inspection and confirm/unconfirm controls in the store report;
- normalized advertiser/search-coverage records are not yet modeled separately;
- current active status is not considered verified merely because a delivery-stop time is absent;
- ad-to-product links require collected landing-page relationships and are not comprehensive; and
- creative deduplication/concept/hook/angle grouping is not implemented.

The store report can match ads by exact landing-page domain or a confirmed advertiser identity. Matched records remain evidence, not proof of ad success or sales.

### Data Meta does not provide here

Northstar does not claim:

- spend;
- impressions or reach when not returned and normalized;
- clicks;
- conversions;
- return on ad spend;
- winning creatives; or
- current activity based only on a missing stop date.

Terms such as longest-running or most repeated describe observable records, not performance.

### Relevant API endpoints

- `GET /integrations/meta/status`
- `PUT /integrations/meta/config`
- `DELETE /integrations/meta/config`
- `POST /integrations/meta/test`
- `POST /ads/meta/search`
- `GET /ads?platform=meta&official_only=true`
- `POST /ingest/meta-ads-search` for the older asynchronous search path

See [API reference](API_REFERENCE.md#meta-ad-library) for examples.

## GetHookd ad discovery

### What the integration does

Northstar calls GetHookd's documented public `GET /api/v1/explore` endpoint through
the local backend. The **Find ads** screen supports keyword, platform, active state,
creative format, and minimum-run-time filters and requests up to 30 results at a
time. Results can include creative media, advertiser identity, copy, landing page,
provider dates, duration, and provider classifications when returned.

This optional integration is deliberately live-search-only. Northstar's durable ad
library is built from official imports and public ads you choose to save; it does not
depend on GetHookd. The normalized ad schema preserves provider and source provenance,
so future collectors can be added without confusing a provider record with an official
Meta import or a user-saved observation.

### Connect and search through the UI

1. Obtain a GetHookd public API token with `explore:read` access and an eligible plan.
2. Open **Settings & sources**.
3. Save the token under **GetHookd public API**.
4. Open **Find ads** and select **GetHookd search**.
5. Enter a product, problem, hook, brand, or ad-copy phrase.
6. Adjust filters and run the live search.

Search/list calls can consume GetHookd credits based on returned results. Northstar
shows `used_credits` and `remaining_credits` from the provider response. It does not
cache or silently repeat a search.

Provider scores, named classifications, activity, run duration, and reuse counts are
imported research signals. They are not Northstar measurements and do not establish
spend, conversions, ROAS, or profitability.

### Relevant API endpoints

- `GET /integrations/gethookd/status`
- `PUT /integrations/gethookd/config`
- `DELETE /integrations/gethookd/config`
- `POST /ads/gethookd/search`

See [API reference](API_REFERENCE.md#gethookd-ad-discovery) for an example.

## Public-data and legal boundaries

Northstar is designed for public research within provider and site rules:

- The storefront crawler respects `robots.txt`.
- It does not log in, solve CAPTCHAs, bypass access controls, or evade anti-bot systems.
- It does not access private Shopify analytics or merchant dashboards.
- It validates DNS and redirects to prevent scanning private/local networks.
- Provider access uses the credentials and permissions you supply.
- You remain responsible for complying with the target site's terms, provider terms, local law, and how you use the resulting research.

Provider estimates and public observations should be treated as research signals, not audited business facts.
