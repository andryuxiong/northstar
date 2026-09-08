"""Pure v1 unit-economics calculations for user-entered product test scenarios."""

from decimal import Decimal, ROUND_HALF_UP


VERSION = "unit-economics-v1"
MONEY = Decimal("0.01")
RATIO = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


def _positive(value: Decimal) -> Decimal:
    return max(Decimal("0"), value)


def calculate_product_economics(values: dict) -> dict:
    price = Decimal(values["selling_price"])
    payment_fee = price * Decimal(values["payment_fee_rate"]) + Decimal(values["payment_fee_fixed"])
    refund_allowance = price * Decimal(values["refund_allowance_rate"])
    cost_low = sum(
        Decimal(values[key])
        for key in ("product_cost_low", "shipping_cost_low", "fulfillment_cost_low", "other_variable_cost_low")
    )
    cost_high = sum(
        Decimal(values[key])
        for key in ("product_cost_high", "shipping_cost_high", "fulfillment_cost_high", "other_variable_cost_high")
    )
    contribution_low_raw = price - payment_fee - refund_allowance - cost_high
    contribution_high_raw = price - payment_fee - refund_allowance - cost_low
    contribution_low = _money(contribution_low_raw)
    contribution_high = _money(contribution_high_raw)
    break_even_cpa_low = _money(_positive(contribution_low_raw))
    break_even_cpa_high = _money(_positive(contribution_high_raw))
    target_deduction = price * Decimal(values["target_profit_margin"])
    target_cpa_low_raw = contribution_low_raw - target_deduction
    target_cpa_high_raw = contribution_high_raw - target_deduction
    target_cpa_low = _money(_positive(target_cpa_low_raw))
    target_cpa_high = _money(_positive(target_cpa_high_raw))

    def roas(cpa: Decimal) -> Decimal | None:
        return _ratio(price / cpa) if cpa > 0 else None

    if target_cpa_low_raw > 0:
        status = "target_viable"
        label = "Target margin survives the high-cost case"
        explanation = "Both entered cost cases leave room for acquisition while preserving the target profit margin."
    elif target_cpa_high_raw > 0:
        status = "cost_sensitive"
        label = "Viability depends on the cost case"
        explanation = "Only the low-cost case leaves room for acquisition at the selected target margin."
    elif contribution_high_raw > 0:
        status = "break_even_only"
        label = "Positive contribution, but no target-margin ad room"
        explanation = "At least one cost case contributes before ads, but the target margin consumes the available acquisition allowance."
    else:
        status = "negative_contribution"
        label = "Negative contribution before advertising"
        explanation = "Even the low-cost case does not cover the entered variable costs and allowances."

    return {
        "version": VERSION,
        "status": status,
        "label": label,
        "explanation": explanation,
        "landed_variable_cost_low": _money(cost_low),
        "landed_variable_cost_high": _money(cost_high),
        "payment_fee": _money(payment_fee),
        "refund_allowance": _money(refund_allowance),
        "pre_ad_contribution_low": contribution_low,
        "pre_ad_contribution_high": contribution_high,
        "contribution_margin_low": _ratio(contribution_low_raw / price),
        "contribution_margin_high": _ratio(contribution_high_raw / price),
        "break_even_cpa_low": break_even_cpa_low,
        "break_even_cpa_high": break_even_cpa_high,
        "break_even_roas_low": roas(break_even_cpa_high),
        "break_even_roas_high": roas(break_even_cpa_low),
        "target_cpa_low": target_cpa_low,
        "target_cpa_high": target_cpa_high,
        "target_roas_low": roas(target_cpa_high),
        "target_roas_high": roas(target_cpa_low),
        "formula_notice": (
            "User-entered planning scenario. Break-even CPA equals selling price minus entered variable costs, "
            "payment fees, and refund allowance. Target CPA also reserves the selected profit margin."
        ),
    }
