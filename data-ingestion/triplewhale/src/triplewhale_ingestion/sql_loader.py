from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from dateutil import tz

from .config import Settings
from .models import HourlyRegionMetrics
from .triple_whale_client import TripleWhaleClient

COUNTRY_TO_REGION = {
    "US": "US",
    "CA": "CA",
    "GB": "UK",
    "UK": "UK",
    "AU": "AU",
}

REGION_TOKEN_SETS: Dict[str, set[str]] = {
    "AU": {"AU", "AUS", "AUSTRALIA"},
    "UK": {"UK", "GB", "UNITEDKINGDOM"},
    "CA": {"CA", "CAN", "CANADA"},
    "US": {"US", "USA", "UNITEDSTATES"},
}

SUPPORTED_CHANNELS = {"facebook-ads", "google-ads"}


def fetch_hourly_metrics(
    client: TripleWhaleClient,
    settings: Settings,
    start_date: datetime,
    end_date: datetime,
) -> List[HourlyRegionMetrics]:
    if not settings.triple_whale_shop_domain:
        raise RuntimeError("TRIPLE_WHALE_SHOP_DOMAIN (or SHOPIFY_DOMAIN) must be set to run the pipeline.")

    shop_timezone = _detect_shop_timezone(client, settings.triple_whale_shop_domain)
    store_zone = tz.gettz(shop_timezone) or tz.UTC
    account_region_map = (settings.triple_whale_account_region_map or {})

    buffer_start = start_date - timedelta(days=1)
    buffer_end = end_date + timedelta(days=1)

    order_rows = _fetch_orders_hourly(client, settings.triple_whale_shop_domain, buffer_start, buffer_end)
    ads_rows = _fetch_ads_hourly(client, settings.triple_whale_shop_domain, buffer_start, buffer_end)

    buckets: Dict[Tuple[str, datetime], Dict[str, float]] = defaultdict(lambda: {
        "meta_spend": 0.0,
        "google_spend": 0.0,
        "new_customer_orders": 0.0,
        "new_customer_sales": 0.0,
        "total_sales": 0.0,
        "currency": "USD",
    })

    for row in order_rows:
        region = _region_from_country(row.get("shipping_country_code"))
        if not region:
            continue

        timestamp = _hour_to_utc(row.get("order_hour"), store_zone)
        key = (region, timestamp)
        bucket = buckets[key]
        bucket["total_sales"] += float(row.get("total_sales", 0.0) or 0.0)
        bucket["new_customer_sales"] += float(row.get("new_customer_sales", 0.0) or 0.0)
        bucket["new_customer_orders"] += float(row.get("new_customer_orders", 0.0) or 0.0)
        currency = row.get("currency") or bucket.get("currency")
        if currency:
            bucket["currency"] = currency

    for row in ads_rows:
        channel = (row.get("channel") or "").lower()
        if channel not in SUPPORTED_CHANNELS:
            continue

        region = _region_from_ad_row(row, account_region_map)
        if not region:
            continue

        timestamp = _hour_to_utc(row.get("spend_hour"), store_zone)
        key = (region, timestamp)
        bucket = buckets[key]

        spend_value = float(row.get("spend", 0.0) or 0.0)
        if channel == "facebook-ads":
            bucket["meta_spend"] += spend_value
        elif channel == "google-ads":
            bucket["google_spend"] += spend_value

        if not bucket.get("currency") and row.get("currency"):
            bucket["currency"] = row["currency"]

    records: List[HourlyRegionMetrics] = []
    for (region, timestamp), values in sorted(buckets.items(), key=lambda item: (item[0][0], item[0][1])):
        records.append(
            HourlyRegionMetrics(
                region=region,
                timestamp_utc=timestamp,
                meta_spend=values["meta_spend"],
                google_spend=values["google_spend"],
                new_customer_orders=int(round(values["new_customer_orders"])),
                new_customer_sales=values["new_customer_sales"],
                total_sales=values["total_sales"],
                currency=values.get("currency", "USD"),
            )
        )

    return records


def _fetch_orders_hourly(
    client: TripleWhaleClient,
    shop_domain: str,
    start_date: datetime,
    end_date: datetime,
) -> Iterable[Dict[str, object]]:
    query = """
    SELECT
      toStartOfHour(created_at) AS order_hour,
      shipping_country_code,
      anyHeavy(currency) AS currency,
      sum(order_revenue) AS total_sales,
      sumIf(order_revenue, is_new_customer) AS new_customer_sales,
      sumIf(orders_quantity, is_new_customer) AS new_customer_orders
    FROM orders_table
    WHERE event_date BETWEEN @startDate AND @endDate
      AND shipping_country_code IN ('US','CA','GB','UK','AU')
    GROUP BY order_hour, shipping_country_code
    """
    return client.execute_sql(shop_domain, query, start_date, end_date)


def _fetch_ads_hourly(
    client: TripleWhaleClient,
    shop_domain: str,
    start_date: datetime,
    end_date: datetime,
) -> Iterable[Dict[str, object]]:
    query = """
    SELECT
      toStartOfHour(toDateTime(event_date) + toIntervalHour(event_hour)) AS spend_hour,
      channel,
      account_id,
      campaign_name,
      adset_name,
      anyHeavy(currency) AS currency,
      sum(spend) AS spend
    FROM ads_table
    WHERE event_date BETWEEN @startDate AND @endDate
      AND channel IN ('facebook-ads','google-ads')
    GROUP BY spend_hour, channel, account_id, campaign_name, adset_name
    """
    return client.execute_sql(shop_domain, query, start_date, end_date)


def _detect_shop_timezone(client: TripleWhaleClient, shop_domain: str) -> str:
    now = datetime.utcnow()
    fallback_start = now - timedelta(days=30)
    rows = client.execute_sql(
        shop_domain,
        "SELECT shop_timezone FROM orders_table WHERE shop_timezone != '' LIMIT 1",
        fallback_start,
        now,
    )
    if rows and rows[0].get("shop_timezone"):
        return rows[0]["shop_timezone"]
    return "UTC"


def _hour_to_utc(raw_value: object, store_zone: tz.tzinfo) -> datetime:
    if isinstance(raw_value, datetime):
        dt = raw_value
    else:
        dt = datetime.fromisoformat(str(raw_value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=store_zone)
    else:
        dt = dt.astimezone(store_zone)
    return dt.astimezone(tz.UTC)


def _region_from_country(country_code: Optional[str]) -> Optional[str]:
    if not country_code:
        return None
    return COUNTRY_TO_REGION.get(country_code.upper())


def _region_from_ad_row(row: Dict[str, object], account_map: Dict[str, str]) -> Optional[str]:
    account_id = row.get("account_id")
    if isinstance(account_id, str):
        region = account_map.get(account_id)
        if region:
            return region

    text_parts = [row.get("campaign_name"), row.get("adset_name"), row.get("ad_name")]
    tokens = _tokenize_ad_text(text_parts)

    for region_code in ("AU", "UK", "CA", "US"):
        if tokens & REGION_TOKEN_SETS[region_code]:
            return region_code if region_code != "GB" else "UK"

    return "US"


def _tokenize_ad_text(parts: Iterable[Optional[str]]) -> set[str]:
    combined = " ".join(str(part) for part in parts if part)
    normalized = "".join(ch if ch.isalnum() else " " for ch in combined.upper())
    return set(token for token in normalized.split() if token)


__all__ = ["fetch_hourly_metrics"]
