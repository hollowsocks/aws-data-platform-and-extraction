from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional


@dataclass(slots=True)
class HourlyRegionMetrics:
    """Normalized Triple Whale metrics at hourly granularity."""

    region: str
    timestamp_utc: datetime
    meta_spend: float = 0.0
    google_spend: float = 0.0
    new_customer_orders: int = 0
    new_customer_sales: float = 0.0
    total_sales: float = 0.0
    currency: str = "USD"
    total_orders: float = 0.0
    gross_sales: float = 0.0
    gross_product_sales: float = 0.0
    refund_money: float = 0.0
    discount_amount: float = 0.0
    cost_of_goods: float = 0.0
    shipping_costs: float = 0.0
    estimated_shipping_costs: float = 0.0
    handling_fees: float = 0.0
    payment_gateway_costs: float = 0.0
    non_tracked_spend: float = 0.0
    impressions: float = 0.0
    clicks: float = 0.0
    onsite_purchases: float = 0.0
    onsite_conversion_value: float = 0.0
    meta_purchases: float = 0.0

    @property
    def total_spend(self) -> float:
        return self.meta_spend + self.google_spend


@dataclass(slots=True)
class DailyRegionReport:
    """Derived KPIs per region per local day."""

    region: str
    local_date: date
    meta_spend: float
    google_spend: float
    total_spend: float
    new_customer_orders: int
    new_customer_sales: float
    total_sales: float
    new_customer_aov: Optional[float]
    new_customer_roas: Optional[float]
    blended_roas: Optional[float]
    new_customer_cpp: Optional[float]
    currency: str = "USD"
    returning_orders: Optional[float] = None
    returning_sales: Optional[float] = None
    net_sales: Optional[float] = None
    gross_sales: Optional[float] = None
    gross_product_sales: Optional[float] = None
    refund_money: Optional[float] = None
    discount_amount: Optional[float] = None
    cost_of_goods: Optional[float] = None
    shipping_costs: Optional[float] = None
    estimated_shipping_costs: Optional[float] = None
    handling_fees: Optional[float] = None
    payment_gateway_costs: Optional[float] = None
    gross_profit: Optional[float] = None
    gross_margin: Optional[float] = None
    discount_rate: Optional[float] = None
    refund_rate: Optional[float] = None
    non_tracked_spend: Optional[float] = None
    impressions: Optional[float] = None
    clicks: Optional[float] = None
    ctr: Optional[float] = None
    cpc: Optional[float] = None
    cpm: Optional[float] = None
    meta_purchases: Optional[float] = None
    onsite_purchases: Optional[float] = None
    onsite_conversion_value: Optional[float] = None
    onsite_roas: Optional[float] = None

    def as_dict(self) -> dict[str, object]:
        return {
            "region": self.region,
            "local_date": self.local_date.isoformat(),
            "meta_spend": round(self.meta_spend, 2),
            "google_spend": round(self.google_spend, 2),
            "total_spend": round(self.total_spend, 2),
            "new_customer_orders": self.new_customer_orders,
            "new_customer_sales": round(self.new_customer_sales, 2),
            "total_sales": round(self.total_sales, 2),
            "returning_orders": round(self.returning_orders, 2) if self.returning_orders is not None else None,
            "returning_sales": round(self.returning_sales, 2) if self.returning_sales is not None else None,
            "net_sales": round(self.net_sales, 2) if self.net_sales is not None else None,
            "gross_sales": round(self.gross_sales, 2) if self.gross_sales is not None else None,
            "gross_product_sales": round(self.gross_product_sales, 2) if self.gross_product_sales is not None else None,
            "refund_money": round(self.refund_money, 2) if self.refund_money is not None else None,
            "discount_amount": round(self.discount_amount, 2) if self.discount_amount is not None else None,
            "cost_of_goods": round(self.cost_of_goods, 2) if self.cost_of_goods is not None else None,
            "shipping_costs": round(self.shipping_costs, 2) if self.shipping_costs is not None else None,
            "estimated_shipping_costs": round(self.estimated_shipping_costs, 2) if self.estimated_shipping_costs is not None else None,
            "handling_fees": round(self.handling_fees, 2) if self.handling_fees is not None else None,
            "payment_gateway_costs": round(self.payment_gateway_costs, 2) if self.payment_gateway_costs is not None else None,
            "gross_profit": round(self.gross_profit, 2) if self.gross_profit is not None else None,
            "gross_margin": round(self.gross_margin, 3) if self.gross_margin is not None else None,
            "discount_rate": round(self.discount_rate, 3) if self.discount_rate is not None else None,
            "refund_rate": round(self.refund_rate, 3) if self.refund_rate is not None else None,
            "non_tracked_spend": round(self.non_tracked_spend, 2) if self.non_tracked_spend is not None else None,
            "impressions": round(self.impressions, 2) if self.impressions is not None else None,
            "clicks": round(self.clicks, 2) if self.clicks is not None else None,
            "ctr": round(self.ctr, 4) if self.ctr is not None else None,
            "cpc": round(self.cpc, 4) if self.cpc is not None else None,
            "cpm": round(self.cpm, 4) if self.cpm is not None else None,
            "meta_purchases": round(self.meta_purchases, 2) if self.meta_purchases is not None else None,
            "onsite_purchases": round(self.onsite_purchases, 2) if self.onsite_purchases is not None else None,
            "onsite_conversion_value": round(self.onsite_conversion_value, 2) if self.onsite_conversion_value is not None else None,
            "onsite_roas": round(self.onsite_roas, 3) if self.onsite_roas is not None else None,
            "new_customer_aov": round(self.new_customer_aov, 2) if self.new_customer_aov is not None else None,
            "new_customer_roas": round(self.new_customer_roas, 3) if self.new_customer_roas is not None else None,
            "blended_roas": round(self.blended_roas, 3) if self.blended_roas is not None else None,
            "new_customer_cpp": round(self.new_customer_cpp, 2) if self.new_customer_cpp is not None else None,
            "currency": self.currency,
        }
