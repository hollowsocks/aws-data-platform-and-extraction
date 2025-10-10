"""Recharge Subscription Event Processor"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict
import hashlib
import hmac

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

BRAND = os.environ["BRAND"]
S3_BUCKET = os.environ["S3_BUCKET"]
SUBSCRIPTION_TABLE = os.environ.get("SUBSCRIPTION_TABLE", f"{BRAND}-subscriptions")
CHARGES_TABLE = os.environ.get("CHARGES_TABLE", f"{BRAND}-subscription-charges")
ALERT_TOPIC_ARN = os.environ.get("ALERT_TOPIC_ARN")
WEBHOOK_SECRET = os.environ["RECHARGE_WEBHOOK_SECRET"]


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    logger.debug("Received event: %s", event)

    if not verify_signature(event):
        logger.warning("Invalid Recharge webhook signature")
        return {"statusCode": 401, "body": "Invalid signature"}

    body = json.loads(event.get("body", "{}"))
    event_type = body.get("type")
    payload = body.get("data", {})

    logger.info("Processing Recharge event %s", event_type)

    s3_key = store_raw_event(payload, event_type)
    logger.info("Stored Recharge event to s3://%s/%s", S3_BUCKET, s3_key)

    if event_type and event_type.startswith("subscription/"):
        handle_subscription(payload, event_type)
    elif event_type and event_type.startswith("charge/"):
        handle_charge(payload, event_type)

    if event_type == "subscription/cancelled":
        publish_cancellation_alert(payload)
    if event_type == "charge/failed":
        publish_charge_failure_alert(payload)

    return {"statusCode": 200}


def verify_signature(event: Dict[str, Any]) -> bool:
    signature = event.get("headers", {}).get("x-recharge-hmac-sha256")
    body = event.get("body", "")

    if not signature or not body:
        return False

    computed = hmac.new(WEBHOOK_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, computed)


def store_raw_event(payload: Dict[str, Any], event_type: str) -> str:
    now = datetime.now(timezone.utc)
    prefix = "raw/recharge/other/events/"
    if "subscription" in event_type:
        prefix = "raw/recharge/subscriptions/events/"
    elif "charge" in event_type:
        prefix = "raw/recharge/charges/events/"

    record_id = payload.get("id", "unknown")
    s3_key = f"{prefix}date={now.strftime('%Y-%m-%d')}/" \
             f"hour={now.strftime('%H')}/{event_type.replace('/', '-')}-{record_id}-{now.strftime('%Y%m%d%H%M%S')}.json"

    body = {
        "event_type": event_type,
        "ingested_at": now.isoformat(),
        "data": payload,
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(body, default=str),
        ContentType="application/json",
    )

    return s3_key


def handle_subscription(subscription: Dict[str, Any], event_type: str) -> None:
    table = dynamodb.Table(SUBSCRIPTION_TABLE)

    item = {
        "subscription_id": str(subscription.get("id")),
        "customer_id": str(subscription.get("customer_id")),
        "shopify_customer_id": str(subscription.get("shopify_customer_id")) if subscription.get("shopify_customer_id") else None,
        "status": subscription.get("status"),
        "created_at": subscription.get("created_at"),
        "updated_at": subscription.get("updated_at"),
        "cancelled_at": subscription.get("cancelled_at"),
        "cancellation_reason": subscription.get("cancellation_reason"),
        "cancellation_reason_comments": subscription.get("cancellation_reason_comments"),
        "next_charge_scheduled_at": subscription.get("next_charge_scheduled_at"),
        "order_interval_frequency": subscription.get("order_interval_frequency"),
        "order_interval_unit": subscription.get("order_interval_unit"),
        "product_title": subscription.get("product_title"),
        "price": subscription.get("price"),
        "quantity": subscription.get("quantity"),
        "shopify_product_id": str(subscription.get("shopify_product_id")) if subscription.get("shopify_product_id") else None,
        "shopify_variant_id": str(subscription.get("shopify_variant_id")) if subscription.get("shopify_variant_id") else None,
        "sku": subscription.get("sku"),
        "event_type": event_type,
        "_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)


def handle_charge(charge: Dict[str, Any], event_type: str) -> None:
    table = dynamodb.Table(CHARGES_TABLE)

    item = {
        "charge_id": str(charge.get("id")),
        "subscription_id": str(charge.get("subscription_id")),
        "customer_id": str(charge.get("customer_id")),
        "shopify_order_id": str(charge.get("shopify_order_id")) if charge.get("shopify_order_id") else None,
        "status": charge.get("status"),
        "type": charge.get("type"),
        "scheduled_at": charge.get("scheduled_at"),
        "processed_at": charge.get("processed_at"),
        "total_price": charge.get("total_price"),
        "subtotal_price": charge.get("subtotal_price"),
        "error": charge.get("error"),
        "error_type": charge.get("error_type"),
        "retry_date": charge.get("retry_date"),
        "billing_attempt_count": charge.get("billing_attempt_count", 0),
        "event_type": event_type,
        "_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)


def publish_cancellation_alert(subscription: Dict[str, Any]) -> None:
    if not ALERT_TOPIC_ARN:
        return

    message = (
        "Subscription Cancelled\n"
        f"Subscription ID: {subscription.get('id')}\n"
        f"Customer ID: {subscription.get('customer_id')}\n"
        f"Product: {subscription.get('product_title')}\n"
        f"Reason: {subscription.get('cancellation_reason')}\n"
        f"Comments: {subscription.get('cancellation_reason_comments')}\n"
        f"Cancelled At: {subscription.get('cancelled_at')}\n"
    )

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject="Subscription Cancelled",
        Message=message,
    )


def publish_charge_failure_alert(charge: Dict[str, Any]) -> None:
    if not ALERT_TOPIC_ARN:
        return

    attempt_count = charge.get("billing_attempt_count", 0)
    if attempt_count < 2:
        return

    message = (
        "Subscription Charge Failed\n"
        f"Charge ID: {charge.get('id')}\n"
        f"Subscription ID: {charge.get('subscription_id')}\n"
        f"Customer ID: {charge.get('customer_id')}\n"
        f"Attempts: {attempt_count}\n"
        f"Error: {charge.get('error')} ({charge.get('error_type')})\n"
        f"Retry Date: {charge.get('retry_date')}\n"
        f"Total Price: {charge.get('total_price')}\n"
    )

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"Recharge Payment Failure - Attempt {attempt_count}",
        Message=message,
    )

