from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta
from itertools import chain
from typing import Dict, Iterable, List, Optional, Tuple

import json

from dateutil import tz

from .config import Settings
from .models import HourlyRegionMetrics
from .timezones import REGION_TIMEZONES
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

SEARCH_SHARE_FIELDS = [
    "search_impression_share",
    "search_top_impression_share",
    "search_absolute_top_impression_share",
    "search_budget_lost_top_impression_share",
    "search_budget_lost_absolute_top_impression_share",
    "search_rank_lost_top_impression_share",
    "search_rank_lost_impression_share",
]

SEARCH_IMPRESSIONS_FIELDS = [
    "search_top_impressions",
    "search_absolute_top_impressions",
    "search_budget_lost_top_impressions",
    "search_budget_lost_absolute_top_impressions",
    "search_rank_lost_top_impressions",
    "search_rank_lost_impressions",
]

AI_PACING_FIELDS = [
    "campaign_ai_recommendation",
    "campaign_ai_roas_pacing",
    "adset_ai_recommendation",
    "adset_ai_roas_pacing",
    "ad_ai_recommendation",
    "ad_ai_roas_pacing",
    "channel_ai_recommendation",
    "channel_ai_roas_pacing",
]


def _make_bucket() -> Dict[str, float | str]:
    bucket: Dict[str, float | str] = {
        "meta_spend": 0.0,
        "google_spend": 0.0,
        "new_customer_orders": 0.0,
        "new_customer_sales": 0.0,
        "total_sales": 0.0,
        "total_orders": 0.0,
        "gross_sales": 0.0,
        "gross_product_sales": 0.0,
        "refund_money": 0.0,
        "discount_amount": 0.0,
        "cost_of_goods": 0.0,
        "shipping_costs": 0.0,
        "estimated_shipping_costs": 0.0,
        "handling_fees": 0.0,
        "payment_gateway_costs": 0.0,
        "non_tracked_spend": 0.0,
        "impressions": 0.0,
        "clicks": 0.0,
        "onsite_purchases": 0.0,
        "onsite_conversion_value": 0.0,
        "meta_purchases": 0.0,
        "currency": "USD",
    }

    for field in SEARCH_SHARE_FIELDS:
        bucket[f"{field}_weighted"] = 0.0

    for field in SEARCH_IMPRESSIONS_FIELDS:
        bucket[field] = 0.0

    for field in AI_PACING_FIELDS:
        bucket[field] = ""

    return bucket


def fetch_hourly_metrics(
    client: TripleWhaleClient,
    settings: Settings,
    store_start_local: datetime,
    store_end_local: datetime,
    *,
    store_timezone: Optional[str] = None,
) -> List[HourlyRegionMetrics]:
    if not settings.triple_whale_shop_domain:
        raise RuntimeError("TRIPLE_WHALE_SHOP_DOMAIN (or SHOPIFY_DOMAIN) must be set to run the pipeline.")

    if store_start_local.tzinfo is None or store_end_local.tzinfo is None:
        raise ValueError("store_start_local and store_end_local must be timezone-aware datetimes.")

    shop_timezone = store_timezone or _detect_shop_timezone(client, settings.triple_whale_shop_domain)
    store_zone = tz.gettz(shop_timezone) or tz.UTC
    store_start_local = store_start_local.astimezone(store_zone)
    store_end_local = store_end_local.astimezone(store_zone)
    if store_start_local > store_end_local:
        raise ValueError("store_start_local must be on or before store_end_local.")

    fetch_start_utc, fetch_end_utc = _expand_fetch_window(store_start_local, store_end_local)
    account_region_map = (settings.triple_whale_account_region_map or {})

    order_rows = _fetch_orders_hourly(
        client,
        settings.triple_whale_shop_domain,
        fetch_start_utc,
        fetch_end_utc,
    )

    fb_ads_rows = _fetch_ads_hourly(
        client,
        settings.triple_whale_shop_domain,
        fetch_start_utc,
        fetch_end_utc,
        "facebook-ads",
    )
    google_ads_rows = _fetch_ads_hourly(
        client,
        settings.triple_whale_shop_domain,
        fetch_start_utc,
        fetch_end_utc,
        "google-ads",
    )

    # Combine both channels into a single iterable
    ads_rows = chain(fb_ads_rows, google_ads_rows)

    buckets: Dict[Tuple[str, datetime], Dict[str, float | str]] = defaultdict(_make_bucket)

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
        bucket["total_orders"] += float(row.get("total_orders", 0.0) or 0.0)
        bucket["gross_sales"] += float(row.get("gross_sales", 0.0) or 0.0)
        bucket["gross_product_sales"] += float(row.get("gross_product_sales", 0.0) or 0.0)
        bucket["refund_money"] += float(row.get("refund_money", 0.0) or 0.0)
        bucket["discount_amount"] += float(row.get("discount_amount", 0.0) or 0.0)
        bucket["cost_of_goods"] += float(row.get("cost_of_goods", 0.0) or 0.0)
        bucket["shipping_costs"] += float(row.get("shipping_costs", 0.0) or 0.0)
        bucket["estimated_shipping_costs"] += float(row.get("estimated_shipping_costs", 0.0) or 0.0)
        bucket["handling_fees"] += float(row.get("handling_fees", 0.0) or 0.0)
        bucket["payment_gateway_costs"] += float(row.get("payment_gateway_costs", 0.0) or 0.0)
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

        bucket["non_tracked_spend"] += float(row.get("non_tracked_spend", 0.0) or 0.0)

        impressions = float(row.get("impressions", 0.0) or 0.0)
        bucket["impressions"] += impressions
        clicks = float(row.get("clicks", 0.0) or 0.0)
        bucket["clicks"] += clicks
        bucket["onsite_purchases"] += float(row.get("onsite_purchases", 0.0) or 0.0)
        bucket["onsite_conversion_value"] += float(row.get("onsite_conversion_value", 0.0) or 0.0)
        bucket["meta_purchases"] += float(row.get("meta_purchases", 0.0) or 0.0)

        if not bucket.get("currency") and row.get("currency"):
            bucket["currency"] = row["currency"]

        for field in SEARCH_SHARE_FIELDS:
            value = float(row.get(field, 0.0) or 0.0)
            bucket[f"{field}_weighted"] += value * impressions

        for field in SEARCH_IMPRESSIONS_FIELDS:
            bucket[field] += float(row.get(field, 0.0) or 0.0)

        for field in AI_PACING_FIELDS:
            value = row.get(field)
            if value and not bucket.get(field):
                bucket[field] = value if isinstance(value, str) else json.dumps(value)

    records: List[HourlyRegionMetrics] = []
    for (region, timestamp), values in sorted(buckets.items(), key=lambda item: (item[0][0], item[0][1])):
        impressions = float(values["impressions"])

        def share_value(field: str) -> float:
            weighted = float(values.get(f"{field}_weighted", 0.0))
            if impressions <= 0:
                return 0.0
            return weighted / impressions

        records.append(
            HourlyRegionMetrics(
                region=region,
                timestamp_utc=timestamp,
                meta_spend=float(values["meta_spend"]),
                google_spend=float(values["google_spend"]),
                new_customer_orders=int(round(float(values["new_customer_orders"]))),
                new_customer_sales=float(values["new_customer_sales"]),
                total_sales=float(values["total_sales"]),
                total_orders=float(values["total_orders"]),
                gross_sales=float(values["gross_sales"]),
                gross_product_sales=float(values["gross_product_sales"]),
                refund_money=float(values["refund_money"]),
                discount_amount=float(values["discount_amount"]),
                cost_of_goods=float(values["cost_of_goods"]),
                shipping_costs=float(values["shipping_costs"]),
                estimated_shipping_costs=float(values["estimated_shipping_costs"]),
                handling_fees=float(values["handling_fees"]),
                payment_gateway_costs=float(values["payment_gateway_costs"]),
                non_tracked_spend=float(values["non_tracked_spend"]),
                impressions=impressions,
                clicks=float(values["clicks"]),
                onsite_purchases=float(values["onsite_purchases"]),
                onsite_conversion_value=float(values["onsite_conversion_value"]),
                meta_purchases=float(values["meta_purchases"]),
                search_impression_share=share_value("search_impression_share"),
                search_top_impression_share=share_value("search_top_impression_share"),
                search_absolute_top_impression_share=share_value("search_absolute_top_impression_share"),
                search_budget_lost_top_impression_share=share_value("search_budget_lost_top_impression_share"),
                search_budget_lost_absolute_top_impression_share=share_value("search_budget_lost_absolute_top_impression_share"),
                search_rank_lost_top_impression_share=share_value("search_rank_lost_top_impression_share"),
                search_rank_lost_impression_share=share_value("search_rank_lost_impression_share"),
                search_top_impressions=float(values["search_top_impressions"]),
                search_absolute_top_impressions=float(values["search_absolute_top_impressions"]),
                search_budget_lost_top_impressions=float(values["search_budget_lost_top_impressions"]),
                search_budget_lost_absolute_top_impressions=float(values["search_budget_lost_absolute_top_impressions"]),
                search_rank_lost_top_impressions=float(values["search_rank_lost_top_impressions"]),
                search_rank_lost_impressions=float(values["search_rank_lost_impressions"]),
                campaign_ai_recommendation=str(values["campaign_ai_recommendation"]),
                campaign_ai_roas_pacing=str(values["campaign_ai_roas_pacing"]),
                adset_ai_recommendation=str(values["adset_ai_recommendation"]),
                adset_ai_roas_pacing=str(values["adset_ai_roas_pacing"]),
                ad_ai_recommendation=str(values["ad_ai_recommendation"]),
                ad_ai_roas_pacing=str(values["ad_ai_roas_pacing"]),
                channel_ai_recommendation=str(values["channel_ai_recommendation"]),
                channel_ai_roas_pacing=str(values["channel_ai_roas_pacing"]),
                currency=str(values.get("currency", "USD")),
            )
        )

    return records

def _expand_fetch_window(
    store_start_local: datetime,
    store_end_local: datetime,
) -> Tuple[datetime, datetime]:
    """Expand the UTC fetch window to cover all regional local days."""
    fetch_start = store_start_local.astimezone(tz.UTC)
    fetch_end = store_end_local.astimezone(tz.UTC)

    for config in REGION_TIMEZONES.values():
        region_zone = config.zone
        region_start_local = store_start_local.astimezone(region_zone)
        region_day_start = datetime.combine(region_start_local.date(), time(0, 0, 0), tzinfo=region_zone)
        region_day_end = region_day_start + timedelta(days=1) - timedelta(seconds=1)

        fetch_start = min(fetch_start, region_day_start.astimezone(tz.UTC))
        fetch_end = max(fetch_end, region_day_end.astimezone(tz.UTC))

    return fetch_start, fetch_end


def _fetch_orders_hourly(
    client: TripleWhaleClient,
    shop_domain: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> Iterable[Dict[str, object]]:
    start_iso = window_start_utc.strftime("%Y-%m-%d %H:%M:%S")
    end_iso = window_end_utc.strftime("%Y-%m-%d %H:%M:%S")

    query = """
    SELECT
      toStartOfHour(created_at) AS order_hour,
      shipping_country_code,
      anyHeavy(currency) AS currency,
      sum(order_revenue) AS total_sales,
      sumIf(order_revenue, is_new_customer) AS new_customer_sales,
      sumIf(orders_quantity, is_new_customer) AS new_customer_orders,
      sum(orders_quantity) AS total_orders,
      sum(gross_sales) AS gross_sales,
      sum(gross_product_sales) AS gross_product_sales,
      sum(refund_money) AS refund_money,
      sum(discount_amount) AS discount_amount,
      sum(cost_of_goods) AS cost_of_goods,
      sum(shipping_costs) AS shipping_costs,
      sum(estimated_shipping_costs) AS estimated_shipping_costs,
      sum(handling_fees) AS handling_fees,
      sum(payment_gateway_costs) AS payment_gateway_costs
    FROM orders_table
    WHERE toDateTime(created_at) >= toDateTime('{start}')
      AND toDateTime(created_at) <= toDateTime('{end}')
      AND shipping_country_code IN ('US','CA','GB','UK','AU')
    GROUP BY order_hour, shipping_country_code
    """.format(start=start_iso, end=end_iso)
    return client.execute_sql(shop_domain, query, window_start_utc, window_end_utc)


def _fetch_ads_hourly(
    client: TripleWhaleClient,
    shop_domain: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
    channel: str,
) -> Iterable[Dict[str, object]]:
    start_iso = window_start_utc.strftime("%Y-%m-%d %H:%M:%S")
    end_iso = window_end_utc.strftime("%Y-%m-%d %H:%M:%S")

    query = """
    SELECT
      toStartOfHour(toDateTime(event_date) + toIntervalHour(toUInt32(event_hour))) AS spend_hour,
      channel,
      account_id,
      campaign_name,
      adset_name,
      anyHeavy(currency) AS currency,
      sum(spend) AS spend,
      sum(non_tracked_spend) AS non_tracked_spend,
      sum(impressions) AS impressions,
      sum(clicks) AS clicks,
      sum(onsite_purchases) AS onsite_purchases,
      sum(onsite_conversion_value) AS onsite_conversion_value,
      sum(meta_purchases) AS meta_purchases,
      avg(search_impression_share) AS search_impression_share,
      avg(search_top_impression_share) AS search_top_impression_share,
      avg(search_absolute_top_impression_share) AS search_absolute_top_impression_share,
      avg(search_budget_lost_top_impression_share) AS search_budget_lost_top_impression_share,
      avg(search_budget_lost_absolute_top_impression_share) AS search_budget_lost_absolute_top_impression_share,
      avg(search_rank_lost_top_impression_share) AS search_rank_lost_top_impression_share,
      avg(search_rank_lost_impression_share) AS search_rank_lost_impression_share,
      sum(search_top_impressions) AS search_top_impressions,
      sum(search_absolute_top_impressions) AS search_absolute_top_impressions,
      sum(search_budget_lost_top_impressions) AS search_budget_lost_top_impressions,
      sum(search_budget_lost_absolute_top_impressions) AS search_budget_lost_absolute_top_impressions,
      sum(search_rank_lost_top_impressions) AS search_rank_lost_top_impressions,
      sum(search_rank_lost_impressions) AS search_rank_lost_impressions,
      anyHeavy(toJSONString(campaign_ai_recommendation)) AS campaign_ai_recommendation,
      anyHeavy(toJSONString(campaign_ai_roas_pacing)) AS campaign_ai_roas_pacing,
      anyHeavy(toJSONString(adset_ai_recommendation)) AS adset_ai_recommendation,
      anyHeavy(toJSONString(adset_ai_roas_pacing)) AS adset_ai_roas_pacing,
      anyHeavy(toJSONString(ad_ai_recommendation)) AS ad_ai_recommendation,
      anyHeavy(toJSONString(ad_ai_roas_pacing)) AS ad_ai_roas_pacing,
      anyHeavy(toJSONString(channel_ai_recommendation)) AS channel_ai_recommendation,
      anyHeavy(toJSONString(channel_ai_roas_pacing)) AS channel_ai_roas_pacing
    FROM ads_table
    WHERE channel = '{channel}'
      AND toDateTime(event_date) + toIntervalHour(toUInt32(event_hour)) >= toDateTime('{start}')
      AND toDateTime(event_date) + toIntervalHour(toUInt32(event_hour)) <= toDateTime('{end}')
      AND campaign_status = 'ACTIVE'
      AND adset_status = 'ACTIVE'
      AND ad_status = 'ACTIVE'
    GROUP BY spend_hour, channel, account_id, campaign_name, adset_name
    """.format(channel=channel, start=start_iso, end=end_iso)
    return client.execute_sql(shop_domain, query, window_start_utc, window_end_utc)


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
