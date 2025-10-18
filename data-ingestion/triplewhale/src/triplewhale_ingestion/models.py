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
            "new_customer_aov": round(self.new_customer_aov, 2) if self.new_customer_aov is not None else None,
            "new_customer_roas": round(self.new_customer_roas, 3) if self.new_customer_roas is not None else None,
            "blended_roas": round(self.blended_roas, 3) if self.blended_roas is not None else None,
            "new_customer_cpp": round(self.new_customer_cpp, 2) if self.new_customer_cpp is not None else None,
            "currency": self.currency,
        }
