"""Shopify Customer Event Processor"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BRAND = os.environ["BRAND"]
S3_BUCKET = os.environ["S3_BUCKET"]
CUSTOMER_TABLE = os.environ.get("CUSTOMER_TABLE", f"{BRAND}-customers-cache")


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    customer_data, metadata, event_type, event_time = extract_shopify_payload(event)
    logger.info("Processing customer event %s", event_type)

    if not customer_data:
        logger.warning("No customer data in event detail")
        return {"statusCode": 400, "body": "No customer data"}

    customer_id = str(customer_data.get("id"))

    s3_key = store_raw_customer_event(customer_data, metadata, event_type, event_time)
    logger.info("Stored customer event to s3://%s/%s", S3_BUCKET, s3_key)

    if event_type in {"customers/create", "customers/update"}:
        upsert_customer(customer_data)
    elif event_type == "customers/delete":
        delete_customer(customer_id)
    else:
        logger.debug("No mutation performed for event type %s", event_type)

    return {"statusCode": 200, "body": json.dumps({"customer_id": customer_id})}


def store_raw_customer_event(
    customer_data: Dict[str, Any],
    metadata: Dict[str, Any],
    event_type: Optional[str],
    event_time: Optional[str],
) -> str:
    event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00")) if event_time else datetime.now(timezone.utc)
    customer_id = customer_data.get("id")

    s3_key = (
        "raw/shopify/customers/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"hour={event_dt.strftime('%H')}/"
        f"customer-{customer_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    payload = {
        "event_type": event_type,
        "event_time": event_time,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "data": customer_data,
        "metadata": metadata,
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(payload, default=str),
        ContentType="application/json",
    )

    return s3_key


def upsert_customer(customer_data: Dict[str, Any]) -> None:
    table = dynamodb.Table(CUSTOMER_TABLE)

    item = {
        "customer_id": str(customer_data.get("id")),
        "email": customer_data.get("email"),
        "first_name": customer_data.get("first_name"),
        "last_name": customer_data.get("last_name"),
        "phone": customer_data.get("phone"),
        "created_at": customer_data.get("created_at"),
        "updated_at": customer_data.get("updated_at"),
        "orders_count": customer_data.get("orders_count", 0),
        "total_spent": customer_data.get("total_spent", "0"),
        "tags": customer_data.get("tags", ""),
        "accepts_marketing": customer_data.get("accepts_marketing", False),
        "marketing_opt_in_level": customer_data.get("marketing_opt_in_level"),
        "state": customer_data.get("state"),
        "_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)


def delete_customer(customer_id: str) -> None:
    table = dynamodb.Table(CUSTOMER_TABLE)
    table.delete_item(Key={"customer_id": customer_id})


def extract_shopify_payload(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str], Optional[str]]:
    detail = event.get("detail", {}) or {}
    if isinstance(detail, dict) and "payload" in detail:
        payload = detail.get("payload") or {}
        metadata = detail.get("metadata") or {}
    else:
        payload = detail
        metadata = {}

    topic = metadata.get("X-Shopify-Topic") or event.get("detail-type")
    event_time = metadata.get("X-Shopify-Triggered-At") or event.get("time")

    return payload, metadata, topic, event_time
