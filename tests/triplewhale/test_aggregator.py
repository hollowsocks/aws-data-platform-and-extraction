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
            total_orders=12,
            new_customer_sales=1200.0,
            total_sales=2000.0,
            gross_sales=2050.0,
            gross_product_sales=1500.0,
            refund_money=100.0,
            discount_amount=50.0,
            cost_of_goods=500.0,
            shipping_costs=100.0,
            estimated_shipping_costs=90.0,
            handling_fees=10.0,
            payment_gateway_costs=20.0,
            non_tracked_spend=15.0,
            impressions=1000.0,
            clicks=100.0,
            onsite_purchases=5.0,
            onsite_conversion_value=500.0,
            meta_purchases=3.0,
        ),
        HourlyRegionMetrics(
            region="UK",
            timestamp_utc=datetime(2024, 10, 13, 20, tzinfo=timezone.utc),
            meta_spend=30.0,
            google_spend=20.0,
            new_customer_orders=5,
            total_orders=7,
            new_customer_sales=600.0,
            total_sales=900.0,
            gross_sales=950.0,
            gross_product_sales=1000.0,
            refund_money=20.0,
            discount_amount=15.0,
            cost_of_goods=200.0,
            shipping_costs=50.0,
            estimated_shipping_costs=30.0,
            handling_fees=5.0,
            payment_gateway_costs=8.0,
            non_tracked_spend=5.0,
            impressions=400.0,
            clicks=40.0,
            onsite_purchases=2.0,
            onsite_conversion_value=150.0,
            meta_purchases=1.0,
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
    assert round(row["returning_orders"], 2) == 4.0
    assert round(row["returning_sales"], 2) == 1100.0
    assert round(row["net_sales"], 2) == 2780.0
    assert round(row["gross_profit"], 2) == 2007.0
    assert round(row["gross_margin"], 3) == round(2007 / 2900, 3)
    assert round(row["discount_rate"], 3) == round(65 / 2900, 3)
    assert round(row["refund_rate"], 3) == round(120 / 2900, 3)
    assert round(row["non_tracked_spend"], 2) == 20.0
    assert round(row["impressions"], 2) == 1400.0
    assert round(row["clicks"], 2) == 140.0
    assert round(row["ctr"], 3) == 0.1
    assert round(row["cpc"], 3) == round(200 / 140, 3)
    assert round(row["cpm"], 2) == round((200 * 1000) / 1400, 2)
    assert round(row["onsite_roas"], 2) == round(650 / 200, 2)
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
            total_orders=2,
            refund_money=10,
            discount_amount=5,
            cost_of_goods=40,
            shipping_costs=8,
            handling_fees=2,
            payment_gateway_costs=3,
            impressions=200.0,
            clicks=20.0,
            onsite_conversion_value=60.0,
            onsite_purchases=2.0,
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
        "returning_orders",
        "returning_sales",
        "net_sales",
        "gross_profit",
        "gross_margin",
        "discount_rate",
        "refund_rate",
        "impressions",
        "clicks",
        "ctr",
        "cpc",
        "cpm",
        "onsite_conversion_value",
        "onsite_roas",
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
    assert df.loc[0, "returning_orders"] == 1
    assert df.loc[0, "returning_sales"] == 50
    assert df.loc[0, "net_sales"] == 140
    assert round(df.loc[0, "gross_profit"], 2) == 97.0
    assert round(df.loc[0, "gross_margin"], 3) == round(97.0 / 150.0, 3)
    assert round(df.loc[0, "discount_rate"], 3) == round(5 / 150, 3)
    assert round(df.loc[0, "refund_rate"], 3) == round(10 / 150, 3)
    assert round(df.loc[0, "ctr"], 3) == 0.1
    assert round(df.loc[0, "cpc"], 3) == round(15 / 20, 3)
    assert round(df.loc[0, "cpm"], 2) == round((15 * 1000) / 200, 2)
    assert df.loc[0, "onsite_roas"] == 60 / 15
