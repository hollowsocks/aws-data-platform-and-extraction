from __future__ import annotations

from collections.abc import Iterable
from typing import Sequence

import pandas as pd
from dateutil import tz

from .models import DailyRegionReport, HourlyRegionMetrics
from .timezones import to_local_date, to_local_datetime


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
            }
        )
    return pd.DataFrame(rows)


def build_daily_report(records: Sequence[HourlyRegionMetrics]) -> pd.DataFrame:
    """Aggregate hourly metrics into local-day KPIs."""

    if not records:
        return pd.DataFrame(
            columns=[
                "region",
                "local_date",
                "meta_spend",
                "google_spend",
                "total_spend",
                "new_customer_orders",
                "new_customer_sales",
                "total_sales",
                "new_customer_aov",
                "new_customer_roas",
                "blended_roas",
                "new_customer_cpp",
            ]
        )

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

    # Order columns for readability
    ordered_cols = [
        "region",
        "local_date",
        "currency",
        "meta_spend",
        "google_spend",
        "total_spend",
        "new_customer_orders",
        "new_customer_sales",
        "total_sales",
        "new_customer_aov",
        "new_customer_roas",
        "blended_roas",
        "new_customer_cpp",
    ]
    grouped = grouped[ordered_cols]
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
