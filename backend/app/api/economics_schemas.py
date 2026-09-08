from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductEconomicsIn(BaseModel):
    name: str = Field(default="Base case", min_length=1, max_length=120)
    currency: str = Field(default="USD", min_length=3, max_length=10)
    selling_price: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    product_cost_low: Decimal = Field(default=Decimal("0"), ge=0)
    product_cost_high: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_cost_low: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_cost_high: Decimal = Field(default=Decimal("0"), ge=0)
    fulfillment_cost_low: Decimal = Field(default=Decimal("0"), ge=0)
    fulfillment_cost_high: Decimal = Field(default=Decimal("0"), ge=0)
    other_variable_cost_low: Decimal = Field(default=Decimal("0"), ge=0)
    other_variable_cost_high: Decimal = Field(default=Decimal("0"), ge=0)
    payment_fee_rate: Decimal = Field(default=Decimal("0.029"), ge=0, le=1)
    payment_fee_fixed: Decimal = Field(default=Decimal("0.30"), ge=0)
    refund_allowance_rate: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
    target_profit_margin: Decimal = Field(default=Decimal("0.20"), ge=0, lt=1)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_ranges(self):
        for prefix in ("product_cost", "shipping_cost", "fulfillment_cost", "other_variable_cost"):
            if getattr(self, f"{prefix}_high") < getattr(self, f"{prefix}_low"):
                raise ValueError(f"{prefix}_high cannot be lower than {prefix}_low")
        self.currency = self.currency.strip().upper()
        self.name = self.name.strip()
        self.notes = self.notes.strip() if self.notes and self.notes.strip() else None
        return self


class ProductEconomicsStored(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    scenario_key: str
    revision: int
    supersedes_id: Optional[int] = None
    is_active: bool
    name: str
    version: str
    input_source: str
    currency: str
    selling_price: Decimal
    product_cost_low: Decimal
    product_cost_high: Decimal
    shipping_cost_low: Decimal
    shipping_cost_high: Decimal
    fulfillment_cost_low: Decimal
    fulfillment_cost_high: Decimal
    other_variable_cost_low: Decimal
    other_variable_cost_high: Decimal
    payment_fee_rate: Decimal
    payment_fee_fixed: Decimal
    refund_allowance_rate: Decimal
    target_profit_margin: Decimal
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProductEconomicsCalculation(BaseModel):
    version: str
    status: Literal["target_viable", "cost_sensitive", "break_even_only", "negative_contribution"]
    label: str
    explanation: str
    landed_variable_cost_low: Decimal
    landed_variable_cost_high: Decimal
    payment_fee: Decimal
    refund_allowance: Decimal
    pre_ad_contribution_low: Decimal
    pre_ad_contribution_high: Decimal
    contribution_margin_low: Decimal
    contribution_margin_high: Decimal
    break_even_cpa_low: Decimal
    break_even_cpa_high: Decimal
    break_even_roas_low: Optional[Decimal] = None
    break_even_roas_high: Optional[Decimal] = None
    target_cpa_low: Decimal
    target_cpa_high: Decimal
    target_roas_low: Optional[Decimal] = None
    target_roas_high: Optional[Decimal] = None
    formula_notice: str


class ProductEconomicsOut(ProductEconomicsStored):
    calculation: ProductEconomicsCalculation
