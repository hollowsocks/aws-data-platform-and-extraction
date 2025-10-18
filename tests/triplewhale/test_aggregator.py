from datetime import datetime, timezone

from triplewhale_ingestion.aggregator import build_daily_report, build_hourly_table
from triplewhale_ingestion.models import HourlyRegionMetrics


def test_build_daily_report_aggregates_and_computes_kpis():
    records = [
        HourlyRegionMetrics(
            region="UK",
            timestamp_utc=datetime(2024, 10, 13, 10, tzinfo=timezone.utc),
            meta_spend=100.0,
            google_spend=50.0,
            new_customer_orders=10,
            new_customer_sales=1200.0,
            total_sales=2000.0,
        ),
        HourlyRegionMetrics(
            region="UK",
            timestamp_utc=datetime(2024, 10, 13, 20, tzinfo=timezone.utc),
            meta_spend=30.0,
            google_spend=20.0,
            new_customer_orders=5,
            new_customer_sales=600.0,
            total_sales=900.0,
        ),
    ]

    df = build_daily_report(records)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["region"] == "UK"
    assert str(row["local_date"]) == "2024-10-13"
    assert row["meta_spend"] == 130.0
    assert row["google_spend"] == 70.0
    assert row["total_spend"] == 200.0
    assert row["new_customer_orders"] == 15
    assert row["new_customer_sales"] == 1800.0
    assert row["total_sales"] == 2900.0
    assert round(row["new_customer_aov"], 2) == 120.0
    assert round(row["new_customer_roas"], 2) == 9.0
    assert round(row["blended_roas"], 2) == 14.5
    assert round(row["new_customer_cpp"], 2) == 13.33
    assert row["currency"] == "USD"


def test_build_hourly_table_adds_local_time_columns():
    records = [
        HourlyRegionMetrics(
            region="AU",
            timestamp_utc=datetime(2024, 10, 13, 10, tzinfo=timezone.utc),
            meta_spend=10,
            google_spend=5,
            new_customer_orders=1,
            new_customer_sales=100,
            total_sales=150,
        )
    ]

    df = build_hourly_table(records)
    expected_columns = {
        "region",
        "timestamp_utc",
        "meta_spend",
        "google_spend",
        "new_customer_orders",
        "new_customer_sales",
        "total_sales",
        "currency",
        "total_spend",
        "new_customer_cpp",
        "new_customer_aov",
        "new_customer_roas",
        "blended_roas",
        "local_datetime",
        "local_date",
        "local_hour",
        "central_datetime",
        "central_hour",
    }
    assert expected_columns.issubset(df.columns)
    assert df.loc[0, "local_datetime"].tzinfo is not None
    assert df.loc[0, "local_date"].isoformat() == "2024-10-13"
    assert df.loc[0, "local_hour"] == "2024-10-13 21:00"
    assert df.loc[0, "central_datetime"].tzinfo is not None
    assert df.loc[0, "central_hour"].endswith("05:00")
    assert df.loc[0, "currency"] == "USD"
    assert df.loc[0, "total_spend"] == 15
    assert df.loc[0, "new_customer_cpp"] == 15
    assert df.loc[0, "new_customer_aov"] == 100
    assert df.loc[0, "new_customer_roas"] == 100 / 15
    assert df.loc[0, "blended_roas"] == 150 / 15
