"""Shopify Product Event Processor"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

S3_BUCKET = os.environ["S3_BUCKET"]


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    product_data, metadata, event_type, event_time = extract_shopify_payload(event)
    logger.info("Processing product event %s", event_type)

    if not product_data:
        logger.warning("No product data in event detail")
        return {"statusCode": 400, "body": "No product data"}

    product_id = str(product_data.get("id"))

    s3_key = store_raw_product_event(product_data, metadata, event_type, event_time)
    logger.info("Stored product event to s3://%s/%s", S3_BUCKET, s3_key)

    return {"statusCode": 200, "body": json.dumps({"product_id": product_id})}


def store_raw_product_event(
    product_data: Dict[str, Any],
    metadata: Dict[str, Any],
    event_type: Optional[str],
    event_time: Optional[str],
) -> str:
    event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00")) if event_time else datetime.now(timezone.utc)
    product_id = product_data.get("id")

    s3_key = (
        "raw/shopify/products/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"hour={event_dt.strftime('%H')}/"
        f"product-{product_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    payload = {
        "event_type": event_type,
        "event_time": event_time,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "data": product_data,
        "metadata": metadata,
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(payload, default=str),
        ContentType="application/json",
    )

    return s3_key


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
