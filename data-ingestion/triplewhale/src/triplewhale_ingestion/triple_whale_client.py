from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import requests

from .config import Settings
from .models import HourlyRegionMetrics

logger = logging.getLogger(__name__)


COUNTRY_TO_REGION = {
    "US": "US",
    "CA": "CA",
    "GB": "UK",
    "AU": "AU",
}


class TripleWhaleClient:
    """Wrapper around Triple Whale's public API (Data Out + SQL)."""

    def __init__(self, settings: Settings, session: Optional[requests.Session] = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _base_url(self, path: str) -> str:
        base = self.settings.triple_whale_api_base.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.settings.triple_whale_api_key,
        }

    def _post(self, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(
            self._base_url(path),
            json=json_body,
            headers=self._headers(),
            timeout=self.settings.http_timeout,
        )
        if response.status_code == 403:
            raise PermissionError(
                "Triple Whale API returned 403 (verify shop domain and API key permissions)."
            )
        if not response.ok:
            snippet = response.text[:500]
            raise RuntimeError(
                f"Triple Whale API error {response.status_code} on {path}: {snippet}"
            )
        return response.json()

    # ------------------------------------------------------------------
    # Data Out helpers
    # ------------------------------------------------------------------

    def fetch_summary_metrics(
        self,
        shop_domain: str,
        start_date: datetime,
        end_date: datetime,
        today_hour: int = 24,
    ) -> Dict[str, Any]:
        """Call /summary-page/get-data and return the raw payload."""

        if today_hour < 1 or today_hour > 25:
            raise ValueError("today_hour must be between 1 and 25 inclusive")

        payload = {
            "shopDomain": shop_domain,
            "period": {
                "start": start_date.date().isoformat(),
                "end": end_date.date().isoformat(),
            },
            "todayHour": today_hour,
        }
        return self._post("summary-page/get-data", payload)

    def execute_sql(
        self,
        shop_domain: str,
        query: str,
        start_date: datetime,
        end_date: datetime,
        *,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a custom SQL query via /orcabase/api/sql."""

        payload: Dict[str, Any] = {
            "shopId": shop_domain,
            "query": query,
            "period": {
                "startDate": start_date.date().isoformat(),
                "endDate": end_date.date().isoformat(),
            },
        }
        if currency:
            payload["currency"] = currency
        return self._post("orcabase/api/sql", payload)

    def fetch_hourly_metrics(self, *args, **kwargs):
        raise NotImplementedError(
            "The marketingPerformance GraphQL API is no longer exposed. "
            "Use execute_sql() or fetch_summary_metrics() instead."
        )

    # ------------------------------------------------------------------
    # Legacy GraphQL normalisation helper
    # ------------------------------------------------------------------

    def normalise_marketing_performance(self, data: Dict[str, Any]) -> Iterable[HourlyRegionMetrics]:
        """Translate legacy marketingPerformance payloads into our dataclass."""

        edges = data.get("marketingPerformance", {}).get("edges", []) if data else []
        for edge in edges:
            node = edge.get("node") or {}
            country_code = node.get("countryCode")
            region = COUNTRY_TO_REGION.get(country_code)
            if not region:
                continue

            timestamp_str = node.get("datetime")
            if not timestamp_str:
                continue

            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            metrics = node.get("metrics") or []
            totals = _collapse_metrics(metrics)

            yield HourlyRegionMetrics(
                region=region,
                timestamp_utc=timestamp.astimezone(timezone.utc),
                meta_spend=totals.get("META", 0.0),
                google_spend=totals.get("GOOGLE", 0.0),
                new_customer_orders=int(totals.get("newCustomerOrders", 0)),
                new_customer_sales=float(totals.get("newCustomerSalesUsd", 0.0)),
                total_sales=float(totals.get("totalSalesUsd", 0.0)),
            )


def _collapse_metrics(metrics: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    totals: Dict[str, Any] = {
        "META": 0.0,
        "GOOGLE": 0.0,
        "newCustomerOrders": 0,
        "newCustomerSalesUsd": 0.0,
        "totalSalesUsd": 0.0,
    }
    new_customer_allocated = False
    for metric in metrics:
        source = (metric.get("source") or "").upper()
        spend = float(metric.get("spendUsd", 0.0) or 0.0)
        if source in {"META", "FACEBOOK"}:
            totals["META"] += spend
        elif source in {"GOOGLE", "GOOGLE_ADS"}:
            totals["GOOGLE"] += spend

        if source in {"TOTAL", "ALL", ""} and not new_customer_allocated:
            totals["newCustomerOrders"] = int(metric.get("newCustomerOrders", 0) or 0)
            totals["newCustomerSalesUsd"] = float(metric.get("newCustomerSalesUsd", 0.0) or 0.0)
            totals["totalSalesUsd"] = float(metric.get("totalSalesUsd", 0.0) or 0.0)
            new_customer_allocated = True
    return totals
