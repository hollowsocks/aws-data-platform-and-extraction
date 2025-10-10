"""Data Quality Monitoring Lambda"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")
cloudwatch = boto3.client("cloudwatch")

BRAND = os.environ["BRAND"]
S3_BUCKET = os.environ["S3_BUCKET"]
ALERT_TOPIC_ARN = os.environ.get("ALERT_TOPIC_ARN")
ORDERS_TABLE = os.environ.get("ORDERS_TABLE", f"{BRAND}-orders-cache")
CHECK_WINDOW_HOURS = int(os.getenv("CHECK_WINDOW_HOURS", "24"))


def handler(_: Dict[str, Any], __: Any) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": [],
    }

    results["checks"].append(check_hourly_data_gaps())
    results["checks"].append(check_order_count_anomaly())
    results["checks"].append(check_dynamodb_health())

    store_quality_results(results)
    publish_metrics(results)

    failures = [check for check in results["checks"] if check["status"] == "FAIL"]
    if failures:
        alert_failures(failures)

    return {"statusCode": 200, "results": results}


def check_hourly_data_gaps() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    missing: List[str] = []

    for hours_ago in range(CHECK_WINDOW_HOURS):
        checkpoint = now - timedelta(hours=hours_ago)
        prefix = (
            "raw/shopify/orders/events/"
            f"date={checkpoint.strftime('%Y-%m-%d')}/"
            f"hour={checkpoint.strftime('%H')}/"
        )

        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix, MaxKeys=1)
        if response.get("KeyCount", 0) == 0:
            missing.append(f"{checkpoint.strftime('%Y-%m-%d %H:00')}Z")

    return {
        "check": "hourly_data_gaps",
        "status": "PASS" if not missing else "FAIL",
        "missing_hours": missing,
        "message": f"Missing {len(missing)} hourly partitions",
    }


def check_order_count_anomaly() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)
    prefix = (
        "raw/shopify/orders/events/"
        f"date={last_hour.strftime('%Y-%m-%d')}/"
        f"hour={last_hour.strftime('%H')}/"
    )

    current = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    current_count = current.get("KeyCount", 0)

    total = 0
    samples = 0
    for days_back in range(1, 8):
        checkpoint = now - timedelta(days=days_back)
        prefix = (
            "raw/shopify/orders/events/"
            f"date={checkpoint.strftime('%Y-%m-%d')}/"
            f"hour={checkpoint.strftime('%H')}/"
        )
        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
        total += response.get("KeyCount", 0)
        samples += 1

    average = total / samples if samples else 0
    threshold = average * 0.5

    status = "PASS" if average == 0 or current_count >= threshold else "FAIL"

    return {
        "check": "order_count_anomaly",
        "status": status,
        "current_count": current_count,
        "average_count": round(average, 2),
        "threshold": round(threshold, 2),
        "message": f"Current {current_count} vs avg {round(average, 2)}",
    }


def check_dynamodb_health() -> Dict[str, Any]:
    table = dynamodb.Table(ORDERS_TABLE)
    try:
        response = table.scan(Select="COUNT", Limit=1000)
        count = response.get("Count", 0)

        description = table.meta.client.describe_table(TableName=ORDERS_TABLE)
        status = description["Table"]["TableStatus"]

        return {
            "check": "dynamodb_health",
            "status": "PASS" if status == "ACTIVE" else "FAIL",
            "item_count": count,
            "table_status": status,
            "message": f"Table {status} ~{count} items",
        }
    except Exception as exc:
        logger.exception("Failed DynamoDB health check")
        return {
            "check": "dynamodb_health",
            "status": "FAIL",
            "message": str(exc),
        }


def store_quality_results(results: Dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    key = (
        "metadata/data_quality/"
        f"date={now.strftime('%Y-%m-%d')}/"
        f"quality-check-{now.strftime('%Y%m%d%H%M%S')}.json"
    )

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(results, default=str),
        ContentType="application/json",
    )


def publish_metrics(results: Dict[str, Any]) -> None:
    metrics = []
    for check in results["checks"]:
        metrics.append({
            "MetricName": f"DataQuality_{check['check']}",
            "Value": 1 if check["status"] == "PASS" else 0,
            "Unit": "Count",
            "Timestamp": datetime.now(timezone.utc),
        })

    if metrics:
        cloudwatch.put_metric_data(Namespace=f"{BRAND}/DataQuality", MetricData=metrics)


def alert_failures(failures: List[Dict[str, Any]]) -> None:
    if not ALERT_TOPIC_ARN:
        return

    message_lines = ["Data Quality Failures Detected:"]
    for failure in failures:
        message_lines.append(f"- {failure['check']}: {failure['message']}")
        if failure.get("missing_hours"):
            message_lines.append(f"  Missing hours: {', '.join(failure['missing_hours'][:5])}")

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"Data Quality Alert ({len(failures)} checks)",
        Message="\n".join(message_lines),
    )

