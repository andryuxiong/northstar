# Northstar intelligence methodology

This document describes the calculation code currently used by the Store Intelligence Report. The estimators are deterministic, versioned Python modules under `backend/app/services/intelligence/`. They do not fetch data themselves; the report service passes normalized observations and the active estimation profile into them.

The important contract is:

> A result is either a disclosed value/range/classification with evidence and assumptions, or it is `insufficient_data` with the required missing signals. Northstar does not replace missing inputs with plausible-looking values.

## Common insight contract

Each derived insight contains:

- `metric`;
- `status`: `available` or `insufficient_data`;
- `low`, `central`, and `high` for range metrics;
- `classification` or `score` for non-range metrics;
- unit and currency where relevant;
- confidence score and label;
- evidence records and their independence groups;
- assumptions used;
- missing signals;
- a plain-language explanation;
- estimator version; and
- calculation time.

An available range must contain all three ordered values. An insufficient result cannot contain a value, score, or partial range.

## Confidence is not the metric

Confidence describes the quality and coverage of the evidence, not whether a result is attractive.

Default labels are:

| Score | Label |
| --- | --- |
| 0.75–1.00 | High |
| 0.50–0.749… | Medium |
| 0.25–0.499… | Low |
| Below 0.25, or a required input is absent | Insufficient data |

The product momentum estimator caps confidence below High in v1, even when its score is high. Orders and revenue are capped Low while they rely on a generic conversion-rate prior. A high product score with low confidence is possible and should be treated as a hypothesis.

## Evidence independence

Evidence has an `independence_group`. Correlated facts are collapsed within their group before confidence is calculated. Examples:

- monthly visits, global rank, and a traffic change calculated from the same Similarweb series remain one provider traffic group;
- ad count and ad longevity from one Meta import do not become two independent confirmations;
- catalog prices and a homepage offer remain part of a catalog/pricing/offer context rather than separate proof of sales.

This prevents a verbose provider payload from creating artificial confidence.

Evidence records are content-addressed and linked to versioned derived insights. Completed analysis runs and evidence links are immutable. Reopening a report creates another analysis run rather than rewriting a past calculation.

## Active defaults

The initial `general_ecommerce` estimation profile uses:

| Setting | Low | Central | High |
| --- | ---: | ---: | ---: |
| Conversion rate | 0.5% | 1.2% | 2.5% |
| Items per order | 1.00 | 1.15 | 1.50 |
| Traffic planning multiplier | 0.70 | 1.00 provider point | 1.40 |

Other defaults:

- evidence freshness: 45 days;
- minimum sellable products for AOV: 5;
- traffic median-monthly direction threshold: 5%;
- traffic endpoint direction threshold: 10%;
- product momentum minimum groups: 2;
- product momentum minimum history span: 14 days.

These are editable planning assumptions, not universal e-commerce facts.

## 1. Monthly traffic and direction

Estimator: `traffic-trend-v1`

### Required input

At least one non-negative provider monthly-visits observation with a usable fetch status. Global rank alone is not sufficient and is never transformed into visits.

Northstar currently normalizes Similarweb snapshots into typed monthly `TrafficObservation` rows. Repeated fetches for the same provider/month are deduplicated by using the newest relevant observation. Trend calculations use one provider series; observations from different providers are not mixed.

### Range

For the newest provider point `V`:

```text
traffic low     = V × traffic envelope low
traffic central = V
traffic high    = V × traffic envelope high
```

With defaults:

```text
low = V × 0.70
central = V
high = V × 1.40
```

The low/high values are Northstar planning bounds. They are not a Similarweb confidence interval and should never be attributed to Similarweb.

### Direction

Northstar uses at most the newest six consecutive monthly points.

- One point: no month-over-month or longer direction.
- Two consecutive points: month-over-month change can be shown, but direction remains insufficient.
- Three or more consecutive points: calculate each month-over-month change, its median, and the total endpoint change from the first to last point.

The default classifications are:

- **Growing** when median monthly change is greater than +5% and endpoint change is greater than +10%.
- **Declining** when median monthly change is less than −5% and endpoint change is less than −10%.
- **Stable** otherwise.

### Confidence

The initial confidence is 0.65 for a successful latest visit response or 0.50 for a partial response. It gains 0.05 for at least three consecutive months and another 0.05 for six months, capped at 0.75. If the newest visit retrieval is undated or older than the configured freshness limit, confidence is multiplied by 0.55.

A newer rank-only fetch does not make an older visits observation fresh.

## 2. Average order value

Estimator: `aov-v1`

This is a catalog-derived planning range, not observed basket value.

### Representative product price

For each current product, the report prefers:

1. the median positive price among parsed variants;
2. otherwise, the midpoint of `price_min` and `price_max`; or
3. otherwise, `price_min`.

Using a median avoids anchoring every product to its cheapest variant.

### Merchandise eligibility

Northstar excludes:

- missing, invalid, zero, or negative prices;
- explicit free gifts;
- shipping/package/order/delivery protection or insurance;
- warranties;
- tips and donations;
- gift cards; and
- explicitly classified add-ons or services.

The current report can infer some explicit kinds from public URL markers and also applies conservative title patterns. It does not remove unknown products merely because parsing was incomplete; those remain visible in the product table but do not become valid price anchors.

### Publication gate

The estimator requires:

- at least five eligible products by default; and
- exactly one usable catalog currency.

The report may use a detected public storefront currency for product records whose parser omitted product-level currency. When it does, the evidence and assumption are disclosed and AOV confidence is capped at 0.33.

### Formula

For eligible representative product prices:

```text
AOV low     = price P25 × items/order low
AOV central = price median × items/order central
AOV high    = price P75 × items/order high
```

Money is rounded to two decimal places. With defaults, the multipliers are 1.00, 1.15, and 1.50.

### Confidence

Confidence begins at 0.35 and adds 0.01 for each eligible product above five, up to ten added products. It is capped at 0.49 because catalog prices do not reveal actual product mix, bundles, quantity, discounts used at checkout, or basket value.

## 3. Monthly orders

Estimator: `orders-v1`

Orders require an available monthly traffic range. Rank, ad records, catalog size, and homepage activity cannot substitute for visits.

```text
orders low     = floor(traffic low × conversion low)
orders central = round(traffic central × conversion central)
orders high    = ceil(traffic high × conversion high)
```

With defaults, the conversion assumptions are 0.5%, 1.2%, and 2.5%.

Advertising is deliberately not used as a conversion multiplier. The conversion range is a user-adjustable general planning prior, so confidence cannot exceed 0.45 and also cannot exceed the traffic confidence.

## 4. Estimated monthly gross revenue

Estimator: `revenue-v1`

Revenue requires both an available monthly order range and an available AOV range in a known currency.

```text
gross revenue low     = orders low × AOV low
gross revenue central = orders central × AOV central
gross revenue high    = orders high × AOV high
```

The confidence is the weakest of order confidence, AOV confidence, and 0.45.

This is **estimated gross store revenue**, not profit. Northstar does not subtract:

- product or landed cost;
- advertising spend;
- fulfillment or shipping;
- payment fees;
- refunds and chargebacks;
- taxes; or
- operating costs.

Supplier-derived profit and margin remain unavailable until a plausible supplier cost
range and other costs exist. A separately labeled user-entered planning calculator is
available and does not change this store-revenue estimate or establish supplier evidence.

### User-entered product test economics

Calculator: `unit-economics-v1`

Each named scenario is an immutable revision. All values are user-entered and are not
observed supplier, merchant, or advertising facts. For selling price `P`:

```text
landed variable cost case = product cost + shipping + fulfillment + other variable cost
payment fee              = P × payment fee rate + fixed payment fee
refund allowance         = P × refund allowance rate
pre-ad contribution      = P - landed variable cost - payment fee - refund allowance
break-even CPA           = max(0, pre-ad contribution)
break-even ROAS          = P / break-even CPA, when CPA is positive
target CPA               = max(0, pre-ad contribution - P × target profit margin)
target ROAS              = P / target CPA, when target CPA is positive
```

The low outcome uses the high entered cost case; the high outcome uses the low entered
cost case. `Target viable` means both cases leave a positive target CPA. `Cost
sensitive` means only the low-cost case does. `Break-even only` means contribution is
positive in at least one case but no acquisition allowance remains after reserving the
target margin. `Negative contribution` means even the low-cost case is non-positive
before ads.

Taxes, fixed overhead, chargeback-specific losses, customer lifetime value, and actual
ad performance are not inferred. Enter them in other variable cost or adjust the refund
allowance only when doing so matches the scenario's stated assumptions.

## 5. Product momentum evidence score

Estimator: `product-momentum-v1`

Despite some UI/product language inherited from research tools, this is not a calibrated winning-product probability. It is a 0–100 evidence score.

### Evidence groups and default weights

| Group | Weight | Current collection state |
| --- | ---: | --- |
| Advertising | 30% | Can use imported ads associated through collected landing-page links; current active status is not assumed |
| Reviews | 25% | Framework exists, but review count/velocity collection is not implemented |
| Merchandising | 15% | Uses a product link observed on the collected homepage |
| Inventory | 15% | Can use an observed unavailable-to-available Shopify transition with enough history |
| Persistence | 10% | Can use persistence across at least three distinct observation days and a 30-day span |
| Offer/page | 5% | Framework exists, but no product-level offer/page momentum evidence is currently generated |

Current signal strengths and reliability are intentionally conservative:

- Homepage placement: strength 0.65, reliability 0.70.
- Related imported ad records: logarithmic count strength capped at 1.0, reliability 0.62, explicitly marked as not verifying current activity.
- Persistence: strength grows with span up to 180 days, reliability 0.50.
- Observed restock: strength 0.55, reliability 0.55.

### Publication gate

A numeric score is withheld unless:

- at least two enabled independent evidence groups are present; and
- the observation span is at least 14 days by default.

Facts within one group cannot satisfy the multi-group gate. Fresh evidence is also tracked; evidence older than the freshness limit receives a 0.50 freshness factor.

### Score

For each group, Northstar keeps its strongest effective signal:

```text
effective signal = signal strength × reliability × freshness factor
```

Then:

```text
score = sum(group weight × effective signal)
        / sum(weights of groups that are present)
        × 100
```

Classifications are:

- **Weak** below 40;
- **Moderate** from 40 to below 70; and
- **Strong** at 70 or above.

Because the score is normalized over present groups, confidence must always be read beside it.

### Confidence

```text
confidence = sum(present group weights)
             × weighted effective reliability
             × min(observation span / 30 days, 1)
```

Confidence is capped at 0.74. Missing evidence groups remain listed. A product can therefore score Strong while confidence remains Low or Medium.

Product existence, variant count, discounting, availability, one imported ad, or one price change is never enough to prove demand.

## 6. Store momentum

Estimator: `store-momentum-v1`

The current store momentum follows the supported multi-month provider traffic direction. It is available only when traffic has a Growing, Stable, or Declining classification. Catalog additions, price changes, and advertising changes are not treated as store sales momentum without independent corroboration.

## 7. Advertising status

Estimator/report version: `advertising-status-v1`

Imported ads are associated with a store only through:

- an exact landing-page domain match; or
- a manually confirmed Meta advertiser identity.

The report may show matched-record counts, known historical records with delivery-stop dates, distinct creative-record keys, earliest delivery start, or completed durations. However, it currently keeps the headline advertising status Unknown because recent successful store-scoped search coverage is not persisted as a normalized coverage observation.

A missing delivery-stop time does not prove an ad is active. An ad's first Northstar observation time is not its provider delivery start. No claim of success, spend, reach, clicks, or return on ad spend is made.

## 8. Offers, funnel elements, and technology

These sections currently use public homepage pattern observations persisted in the store profile.

- Offer types include percentage discount, free shipping, buy-one-get-one, buy-X-get-Y, free gift, and first-order language where a supported pattern matches.
- Funnel and technology patterns are categorized and accompanied by evidence and a confidence label.
- Offer persistence remains Unknown until repeated observations are interpreted.
- Detection does not measure conversion lift or business performance.
- Pixel detection is not evidence of active advertising.

The report's primary offer is currently the first normalized detected offer, not a proven highest-impact offer.

## 9. Overall report confidence and verdict

Overall confidence combines evidence quality from headline areas:

```text
overall = traffic confidence × 45%
        + AOV confidence × 25%
        + best product momentum confidence × 20%
        + advertising confidence × 10%
```

It is capped at 0.74 in the current report. The standard confidence labels are then applied.

Verdicts are gated by evidence:

- **Worth studying, with product-level validation still required** requires traffic confidence of at least 0.50 and at least one product momentum result with confidence of at least 0.50.
- **Traffic evidence exists, but product demand is not yet verified** requires available traffic with confidence of at least 0.25.
- **Advertising activity exists, but meaningful demand is still unverified** requires an available advertising classification.
- Otherwise the report says **Little evidence of meaningful demand**.

These verdicts describe Northstar's evidence state. They are not declarations about the merchant's actual performance.

## 10. Explicitly unavailable conclusions

The current report deliberately withholds:

- product review signal and review velocity;
- product-level sales contribution;
- product saturation and competitor counts;
- supplier matches and cost ranges;
- gross margin;
- dropshipping likelihood;
- ad performance, spend, impressions, and verified current activity;
- traffic channels, engagement, country/category ranks, and top countries; and
- AI-generated strategic recommendations.

Those features require additional normalized collectors and coverage records. Zero local matches are Unknown, not zero competition, zero suppliers, zero ads, or low saturation.
