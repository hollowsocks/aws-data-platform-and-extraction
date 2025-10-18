from __future__ import annotations

from collections.abc import Iterable
from typing import Sequence

import pandas as pd
from dateutil import tz

from .models import DailyRegionReport, HourlyRegionMetrics
from .timezones import to_local_date, to_local_datetime


DAILY_REPORT_COLUMNS = [
    "region",
    "local_date",
    "currency",
    "meta_spend",
    "google_spend",
    "total_spend",
    "new_customer_orders",
    "returning_orders",
    "total_orders",
    "new_customer_sales",
    "returning_sales",
    "total_sales",
    "net_sales",
    "gross_sales",
    "gross_product_sales",
    "refund_money",
    "discount_amount",
    "cost_of_goods",
    "shipping_costs",
    "estimated_shipping_costs",
    "handling_fees",
    "payment_gateway_costs",
    "gross_profit",
    "gross_margin",
    "discount_rate",
    "refund_rate",
    "non_tracked_spend",
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "meta_purchases",
    "onsite_purchases",
    "onsite_conversion_value",
    "onsite_roas",
    "new_customer_aov",
    "new_customer_roas",
    "blended_roas",
    "new_customer_cpp",
]


def _records_to_dataframe(records: Iterable[HourlyRegionMetrics]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "region": record.region,
                "timestamp_utc": record.timestamp_utc,
                "meta_spend": record.meta_spend,
                "google_spend": record.google_spend,
                "new_customer_orders": record.new_customer_orders,
                "new_customer_sales": record.new_customer_sales,
                "total_sales": record.total_sales,
                "currency": record.currency,
                "total_orders": record.total_orders,
                "gross_sales": record.gross_sales,
                "gross_product_sales": record.gross_product_sales,
                "refund_money": record.refund_money,
                "discount_amount": record.discount_amount,
                "cost_of_goods": record.cost_of_goods,
                "shipping_costs": record.shipping_costs,
                "estimated_shipping_costs": record.estimated_shipping_costs,
                "handling_fees": record.handling_fees,
                "payment_gateway_costs": record.payment_gateway_costs,
                "non_tracked_spend": record.non_tracked_spend,
                "impressions": record.impressions,
                "clicks": record.clicks,
                "onsite_purchases": record.onsite_purchases,
                "onsite_conversion_value": record.onsite_conversion_value,
                "meta_purchases": record.meta_purchases,
            }
        )
    return pd.DataFrame(rows)


def build_daily_report(records: Sequence[HourlyRegionMetrics]) -> pd.DataFrame:
    """Aggregate hourly metrics into local-day KPIs."""

    if not records:
        return pd.DataFrame(columns=DAILY_REPORT_COLUMNS)

    df = _records_to_dataframe(records)
    df["local_date"] = df.apply(
        lambda row: to_local_date(row["timestamp_utc"], row["region"]), axis=1
    )

    grouped = (
        df.groupby(["region", "local_date"], as_index=False)
        .agg(
            meta_spend=("meta_spend", "sum"),
            google_spend=("google_spend", "sum"),
            new_customer_orders=("new_customer_orders", "sum"),
            new_customer_sales=("new_customer_sales", "sum"),
            total_sales=("total_sales", "sum"),
            total_orders=("total_orders", "sum"),
            gross_sales=("gross_sales", "sum"),
            gross_product_sales=("gross_product_sales", "sum"),
            refund_money=("refund_money", "sum"),
            discount_amount=("discount_amount", "sum"),
            cost_of_goods=("cost_of_goods", "sum"),
            shipping_costs=("shipping_costs", "sum"),
            estimated_shipping_costs=("estimated_shipping_costs", "sum"),
            handling_fees=("handling_fees", "sum"),
            payment_gateway_costs=("payment_gateway_costs", "sum"),
            non_tracked_spend=("non_tracked_spend", "sum"),
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            onsite_purchases=("onsite_purchases", "sum"),
            onsite_conversion_value=("onsite_conversion_value", "sum"),
            meta_purchases=("meta_purchases", "sum"),
            currency=("currency", "first"),
        )
    )

    grouped["total_spend"] = grouped["meta_spend"] + grouped["google_spend"]

    def safe_div(num, den):
        if den is None or pd.isna(den):
            return None
        if float(den) == 0.0:
            return None
        if num is None or pd.isna(num):
            return None
        return float(num) / float(den)

    grouped["returning_orders"] = (grouped["total_orders"] - grouped["new_customer_orders"]).clip(lower=0)
    grouped["returning_sales"] = grouped["total_sales"] - grouped["new_customer_sales"]
    grouped["net_sales"] = grouped["total_sales"] - grouped["refund_money"]
    grouped["gross_profit"] = (
        grouped["total_sales"]
        - grouped["cost_of_goods"]
        - grouped["shipping_costs"]
        - grouped["payment_gateway_costs"]
        - grouped["handling_fees"]
    )

    grouped["new_customer_aov"] = grouped.apply(
        lambda row: safe_div(row["new_customer_sales"], row["new_customer_orders"]), axis=1
    )
    grouped["new_customer_roas"] = grouped.apply(
        lambda row: safe_div(row["new_customer_sales"], row["total_spend"]), axis=1
    )
    grouped["blended_roas"] = grouped.apply(
        lambda row: safe_div(row["total_sales"], row["total_spend"]), axis=1
    )
    grouped["new_customer_cpp"] = grouped.apply(
        lambda row: safe_div(row["total_spend"], row["new_customer_orders"]), axis=1
    )
    grouped["gross_margin"] = grouped.apply(
        lambda row: safe_div(row["gross_profit"], row["total_sales"]), axis=1
    )
    grouped["discount_rate"] = grouped.apply(
        lambda row: safe_div(row["discount_amount"], row["total_sales"]), axis=1
    )
    grouped["refund_rate"] = grouped.apply(
        lambda row: safe_div(row["refund_money"], row["total_sales"]), axis=1
    )
    grouped["ctr"] = grouped.apply(
        lambda row: safe_div(row["clicks"], row["impressions"]), axis=1
    )
    grouped["cpc"] = grouped.apply(
        lambda row: safe_div(row["total_spend"], row["clicks"]), axis=1
    )
    grouped["cpm"] = grouped.apply(
        lambda row: safe_div(row["total_spend"] * 1000, row["impressions"]), axis=1
    )
    grouped["onsite_roas"] = grouped.apply(
        lambda row: safe_div(row["onsite_conversion_value"], row["total_spend"]), axis=1
    )

    grouped = grouped[DAILY_REPORT_COLUMNS]
    return grouped.sort_values(["region", "local_date"]).reset_index(drop=True)


def to_daily_reports(records: Sequence[HourlyRegionMetrics]) -> list[DailyRegionReport]:
    df = build_daily_report(records)
    reports: list[DailyRegionReport] = []
    for row in df.itertuples(index=False):
        reports.append(
            DailyRegionReport(
                region=row.region,
                local_date=row.local_date,
                meta_spend=row.meta_spend,
                google_spend=row.google_spend,
                total_spend=row.total_spend,
                new_customer_orders=int(row.new_customer_orders),
                new_customer_sales=row.new_customer_sales,
                total_sales=row.total_sales,
                new_customer_aov=row.new_customer_aov,
                new_customer_roas=row.new_customer_roas,
                blended_roas=row.blended_roas,
                new_customer_cpp=row.new_customer_cpp,
                currency=row.currency,
                returning_orders=row.returning_orders,
                returning_sales=row.returning_sales,
                net_sales=row.net_sales,
                gross_sales=row.gross_sales,
                gross_product_sales=row.gross_product_sales,
                refund_money=row.refund_money,
                discount_amount=row.discount_amount,
                cost_of_goods=row.cost_of_goods,
                shipping_costs=row.shipping_costs,
                estimated_shipping_costs=row.estimated_shipping_costs,
                handling_fees=row.handling_fees,
                payment_gateway_costs=row.payment_gateway_costs,
                gross_profit=row.gross_profit,
                gross_margin=row.gross_margin,
                discount_rate=row.discount_rate,
                refund_rate=row.refund_rate,
                non_tracked_spend=row.non_tracked_spend,
                impressions=row.impressions,
                clicks=row.clicks,
                ctr=row.ctr,
                cpc=row.cpc,
                cpm=row.cpm,
                meta_purchases=row.meta_purchases,
                onsite_purchases=row.onsite_purchases,
                onsite_conversion_value=row.onsite_conversion_value,
                onsite_roas=row.onsite_roas,
            )
        )
    return reports


def build_hourly_table(
    records: Sequence[HourlyRegionMetrics], *, include_local_time: bool = True
) -> pd.DataFrame:
    """Return a dataframe of hourly metrics; optionally add local timestamps."""

    df = _records_to_dataframe(records)
    if df.empty:
        return df

    df["total_spend"] = df["meta_spend"] + df["google_spend"]

    orders = df["new_customer_orders"].replace(0, pd.NA)
    spend = df["total_spend"].replace(0, pd.NA)

    df["new_customer_cpp"] = df["total_spend"] / orders
    df["new_customer_aov"] = df["new_customer_sales"] / orders
    df["new_customer_roas"] = df["new_customer_sales"] / spend
    df["blended_roas"] = df["total_sales"] / spend

    df["returning_orders"] = (df["total_orders"] - df["new_customer_orders"]).clip(lower=0)
    df["returning_sales"] = df["total_sales"] - df["new_customer_sales"]
    df["net_sales"] = df["total_sales"] - df["refund_money"]
    df["gross_profit"] = (
        df["total_sales"]
        - df["cost_of_goods"]
        - df["shipping_costs"]
        - df["payment_gateway_costs"]
        - df["handling_fees"]
    )
    df["gross_margin"] = df["gross_profit"] / df["total_sales"].replace(0, pd.NA)
    df["discount_rate"] = df["discount_amount"] / df["total_sales"].replace(0, pd.NA)
    df["refund_rate"] = df["refund_money"] / df["total_sales"].replace(0, pd.NA)
    df["ctr"] = df["clicks"] / df["impressions"].replace(0, pd.NA)
    df["cpc"] = df["total_spend"] / df["clicks"].replace(0, pd.NA)
    df["cpm"] = (df["total_spend"] * 1000) / df["impressions"].replace(0, pd.NA)
    df["onsite_roas"] = df["onsite_conversion_value"] / spend

    if include_local_time:
        local_datetimes = [
            to_local_datetime(ts, region)
            for ts, region in zip(df["timestamp_utc"], df["region"], strict=True)
        ]
        df["local_datetime"] = local_datetimes
        df["local_date"] = [dt.date() for dt in local_datetimes]
        df["local_hour"] = [dt.strftime("%Y-%m-%d %H:00") for dt in local_datetimes]

        central_zone = tz.gettz("America/Chicago")
        central_datetimes = [dt.astimezone(central_zone) for dt in local_datetimes]
        df["central_datetime"] = central_datetimes
        df["central_hour"] = [dt.strftime("%Y-%m-%d %H:00") for dt in central_datetimes]

    return df.sort_values(["region", "timestamp_utc"]).reset_index(drop=True)
