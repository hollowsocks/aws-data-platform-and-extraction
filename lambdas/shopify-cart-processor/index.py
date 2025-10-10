"""Shopify Cart and Checkout Event Processor"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BRAND = os.environ["BRAND"]
S3_BUCKET = os.environ["S3_BUCKET"]
ABANDONED_CART_TABLE = os.environ.get("ABANDONED_CART_TABLE", f"{BRAND}-abandoned-carts")


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    data = event.get("detail", {})
    event_type = event.get("detail-type")
    event_time = event.get("time")

    if not data:
        logger.warning("No checkout/cart data in event detail")
        return {"statusCode": 400, "body": "No event data"}

    if "checkout" in event_type:
        s3_key = store_checkout_event(data, event_type, event_time)
        if not data.get("completed_at"):
            track_abandoned_checkout(data)
    else:
        s3_key = store_cart_event(data, event_type, event_time)

    logger.info("Stored %s event to s3://%s/%s", event_type, S3_BUCKET, s3_key)

    identifier = data.get("token") or data.get("id")
    return {"statusCode": 200, "body": json.dumps({"record_id": str(identifier)})}


def store_checkout_event(checkout_data: Dict[str, Any], event_type: str, event_time: str) -> str:
    event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00")) if event_time else datetime.now(timezone.utc)
    checkout_token = checkout_data.get("token")

    s3_key = (
        "raw/shopify/checkouts/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"checkout-{checkout_token}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    payload = {
        "event_type": event_type,
        "event_time": event_time,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "data": checkout_data,
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(payload, default=str),
        ContentType="application/json",
    )

    return s3_key


def store_cart_event(cart_data: Dict[str, Any], event_type: str, event_time: str) -> str:
    event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00")) if event_time else datetime.now(timezone.utc)
    cart_id = cart_data.get("id")

    s3_key = (
        "raw/shopify/carts/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"cart-{cart_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    payload = {
        "event_type": event_type,
        "event_time": event_time,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "data": cart_data,
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(payload, default=str),
        ContentType="application/json",
    )

    return s3_key


def track_abandoned_checkout(checkout_data: Dict[str, Any]) -> None:
    table = dynamodb.Table(ABANDONED_CART_TABLE)

    item = {
        "checkout_token": checkout_data.get("token"),
        "customer_email": checkout_data.get("email"),
        "customer_id": str(checkout_data.get("customer", {}).get("id")) if checkout_data.get("customer") else None,
        "created_at": checkout_data.get("created_at"),
        "updated_at": checkout_data.get("updated_at"),
        "abandoned_checkout_url": checkout_data.get("abandoned_checkout_url"),
        "total_price": checkout_data.get("total_price"),
        "currency": checkout_data.get("currency"),
        "line_items": json.dumps(checkout_data.get("line_items", [])),
        "_tracked_at": datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}

    ttl_days = int(os.getenv("ABANDONED_CART_TTL_DAYS", "14"))
    item["ttl"] = int((datetime.now(timezone.utc) + timedelta(days=ttl_days)).timestamp())

    table.put_item(Item=item)
