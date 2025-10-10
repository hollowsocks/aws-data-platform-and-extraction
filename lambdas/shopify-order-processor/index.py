"""Shopify Order Event Processor"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BRAND = os.environ["BRAND"]
S3_BUCKET = os.environ["S3_BUCKET"]
DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]

TTL_DAYS = int(os.getenv("ORDERS_TTL_DAYS", "30"))
SUBSCRIPTION_SKUS = [sku.lower() for sku in os.getenv(
    "SUBSCRIPTION_SKUS",
    "marstestsupport,marsupgrade90_02,mars_monthly,mars_quarterly_3x,quarterly_mars_03"
).split(",")]


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    """Process Shopify order events delivered by EventBridge."""
    logger.info("Processing event %s", event.get("detail-type"))

    order_data = event.get("detail", {})
    event_type = event.get("detail-type")
    event_time = event.get("time")

    if not order_data:
        logger.warning("No order data in event detail")
        return {"statusCode": 400, "body": "No order data"}

    order_id = str(order_data.get("id"))

    s3_key = store_raw_event(order_data, event_type, event_time)
    logger.info("Stored raw order event to s3://%s/%s", S3_BUCKET, s3_key)

    enriched_order = enrich_order(order_data, event_type)

    if is_recent_order(enriched_order):
        store_in_dynamodb(enriched_order)
        logger.info("Stored order %s in DynamoDB", order_id)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "order_id": order_id,
            "s3_key": s3_key,
            "event_type": event_type,
        }),
    }


def store_raw_event(order_data: Dict[str, Any], event_type: Optional[str], event_time: Optional[str]) -> str:
    """Persist raw event to the immutable S3 bucket."""
    event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00")) if event_time else datetime.now(timezone.utc)
    order_id = order_data.get("id")

    s3_key = (
        "raw/shopify/orders/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"hour={event_dt.strftime('%H')}/"
        f"event-{order_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    payload = {
        "event_type": event_type,
        "event_time": event_time,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "data": order_data,
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(payload, default=str),
        ContentType="application/json",
        Metadata={
            "event-type": (event_type or "unknown"),
            "order-id": str(order_id or "unknown"),
        },
    )

    return s3_key


def enrich_order(order_data: Dict[str, Any], event_type: Optional[str]) -> Dict[str, Any]:
    customer = order_data.get("customer", {})
    shipping = order_data.get("shipping_address", {})
    billing = order_data.get("billing_address", {})

    def _decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        return Decimal(str(value or "0"))

    enriched: Dict[str, Any] = {
        "order_id": str(order_data.get("id")),
        "order_number": str(order_data.get("order_number")) if order_data.get("order_number") is not None else None,
        "created_at": order_data.get("created_at"),
        "updated_at": order_data.get("updated_at"),
        "processed_at": order_data.get("processed_at"),
        "closed_at": order_data.get("closed_at"),
        "customer_id": str(customer.get("id")) if customer.get("id") else None,
        "customer_email": customer.get("email"),
        "customer_first_name": customer.get("first_name"),
        "customer_last_name": customer.get("last_name"),
        "customer_phone": customer.get("phone") or shipping.get("phone"),
        "customer_created_at": customer.get("created_at"),
        "customer_orders_count": customer.get("orders_count"),
        "customer_total_spent": customer.get("total_spent"),
        "customer_tags": customer.get("tags"),
        "customer_accepts_marketing": customer.get("accepts_marketing"),
        "customer_marketing_opt_in_level": customer.get("marketing_opt_in_level"),
        "total_price": _decimal(order_data.get("total_price")),
        "subtotal_price": _decimal(order_data.get("subtotal_price")),
        "total_discounts": _decimal(order_data.get("total_discounts")),
        "total_tax": _decimal(order_data.get("total_tax")),
        "total_shipping": _decimal(order_data.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount")),
        "total_line_items_price": _decimal(order_data.get("total_line_items_price")),
        "currency": order_data.get("currency", "USD"),
        "financial_status": order_data.get("financial_status"),
        "fulfillment_status": order_data.get("fulfillment_status"),
        "cancelled_at": order_data.get("cancelled_at"),
        "cancel_reason": order_data.get("cancel_reason"),
        "confirmed": order_data.get("confirmed"),
        "test": order_data.get("test", False),
        "shipping_city": shipping.get("city"),
        "shipping_state": shipping.get("province"),
        "shipping_zip": shipping.get("zip"),
        "shipping_country": shipping.get("country"),
        "shipping_address_1": shipping.get("address1"),
        "shipping_address_2": shipping.get("address2"),
        "shipping_company": shipping.get("company"),
        "shipping_name": shipping.get("name"),
        "billing_city": billing.get("city"),
        "billing_state": billing.get("province"),
        "billing_zip": billing.get("zip"),
        "billing_country": billing.get("country"),
        "billing_address_1": billing.get("address1"),
        "billing_address_2": billing.get("address2"),
        "billing_company": billing.get("company"),
        "billing_name": billing.get("name"),
        "source_name": order_data.get("source_name"),
        "source_identifier": order_data.get("source_identifier"),
        "source_url": order_data.get("source_url"),
        "referring_site": order_data.get("referring_site"),
        "landing_site": order_data.get("landing_site"),
        "landing_site_ref": order_data.get("landing_site_ref"),
        "checkout_token": order_data.get("checkout_token"),
        "cart_token": order_data.get("cart_token"),
        "discount_codes": json.dumps(order_data.get("discount_codes", [])),
        "discount_applications": json.dumps(order_data.get("discount_applications", [])),
        "tags": order_data.get("tags", ""),
        "note": order_data.get("note"),
        "note_attributes": json.dumps(order_data.get("note_attributes", [])),
        "gateway": order_data.get("gateway"),
        "payment_gateway_names": json.dumps(order_data.get("payment_gateway_names", [])),
        "processing_method": order_data.get("processing_method"),
        "is_subscription": is_subscription_order(order_data),
        "subscription_type": get_subscription_type(order_data),
        "fulfillments": json.dumps(order_data.get("fulfillments", [])),
        "refunds": json.dumps(order_data.get("refunds", [])),
        "line_items": json.dumps(order_data.get("line_items", []), default=str),
        "line_item_count": len(order_data.get("line_items", [])),
        "total_quantity": sum(item.get("quantity", 0) for item in order_data.get("line_items", [])),
        "event_type": event_type,
        "_ingested_at": datetime.now(timezone.utc).isoformat(),
        "_brand": BRAND,
    }

    return {k: v for k, v in enriched.items() if v is not None}


def is_subscription_order(order_data: Dict[str, Any]) -> bool:
    tags = (order_data.get("tags", "") or "").lower()
    if "subscription" in tags or "recurring" in tags:
        return True

    for item in order_data.get("line_items", []):
        sku = (item.get("sku") or "").lower()
        if any(sub_sku in sku for sub_sku in SUBSCRIPTION_SKUS):
            return True

    return False


def get_subscription_type(order_data: Dict[str, Any]) -> Optional[str]:
    if not is_subscription_order(order_data):
        return None

    for item in order_data.get("line_items", []):
        sku = (item.get("sku") or "").lower()
        if "monthly" in sku:
            return "monthly"
        if "quarterly" in sku or "3x" in sku:
            return "quarterly"

    return "monthly"


def is_recent_order(order_data: Dict[str, Any]) -> bool:
    created_at = order_data.get("created_at")
    if not created_at:
        return True

    try:
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid created_at timestamp %s", created_at)
        return True

    return created_dt >= datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)


def store_in_dynamodb(order_data: Dict[str, Any]) -> None:
    table = dynamodb.Table(DYNAMODB_TABLE)

    ttl = int((datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)).timestamp())
    item = {
        **order_data,
        "ttl": ttl,
    }

    table.put_item(Item=json.loads(json.dumps(item, default=str), parse_float=Decimal))

