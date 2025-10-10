"""Stripe Payment Event Processor"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
import stripe

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

BRAND = os.environ["BRAND"]
S3_BUCKET = os.environ["S3_BUCKET"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
ALERT_TOPIC_ARN = os.environ.get("ALERT_TOPIC_ARN")
PAYMENT_ATTEMPTS_TABLE = os.environ.get("PAYMENT_ATTEMPTS_TABLE", f"{BRAND}-payment-attempts")
INVOICE_PAYMENTS_TABLE = os.environ.get("INVOICE_PAYMENTS_TABLE", f"{BRAND}-invoice-payments")
DISPUTES_TABLE = os.environ.get("DISPUTES_TABLE", f"{BRAND}-disputes")

stripe.api_key = os.environ["STRIPE_API_KEY"]


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    signature = event.get("headers", {}).get("stripe-signature")
    body = event.get("body", "")

    try:
        stripe_event = stripe.Webhook.construct_event(body, signature, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        logger.warning("Invalid Stripe webhook payload")
        return {"statusCode": 400}
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        return {"statusCode": 401}

    event_type = stripe_event["type"]
    payload = stripe_event["data"]["object"]

    logger.info("Processing Stripe event %s", event_type)

    s3_key = store_raw_event(stripe_event, event_type)
    logger.debug("Stored Stripe event in %s", s3_key)

    if "charge" in event_type and "dispute" not in event_type:
        handle_charge(payload, event_type)
    elif "payment_intent" in event_type:
        handle_payment_intent(payload, event_type)
    elif "invoice" in event_type:
        handle_invoice(payload, event_type)
    elif "dispute" in event_type:
        handle_dispute(payload, event_type)

    return {"statusCode": 200}


def store_raw_event(stripe_event: Dict[str, Any], event_type: str) -> str:
    now = datetime.now(timezone.utc)

    if "charge" in event_type and "dispute" not in event_type:
        prefix = "raw/stripe/charges/events/"
    elif "payment_intent" in event_type:
        prefix = "raw/stripe/payment_intents/events/"
    elif "invoice" in event_type:
        prefix = "raw/stripe/invoices/events/"
    elif "dispute" in event_type:
        prefix = "raw/stripe/disputes/events/"
    else:
        prefix = "raw/stripe/other/events/"

    event_id = stripe_event.get("id", "unknown")
    s3_key = f"{prefix}date={now.strftime('%Y-%m-%d')}/hour={now.strftime('%H')}/" \
             f"{event_type.replace('.', '-')}-{event_id}-{now.strftime('%Y%m%d%H%M%S')}.json"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(stripe_event, default=str),
        ContentType="application/json",
    )

    return s3_key


def handle_charge(charge: Dict[str, Any], event_type: str) -> None:
    table = dynamodb.Table(PAYMENT_ATTEMPTS_TABLE)

    item = {
        "charge_id": charge["id"],
        "customer_id": charge.get("customer"),
        "amount": charge["amount"] / 100,
        "currency": charge["currency"].upper(),
        "status": charge["status"],
        "paid": charge.get("paid"),
        "failure_code": charge.get("failure_code"),
        "failure_message": charge.get("failure_message"),
        "payment_method": charge.get("payment_method"),
        "created": datetime.fromtimestamp(charge["created"], tz=timezone.utc).isoformat(),
        "event_type": event_type,
        "_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    metadata = charge.get("metadata", {})
    if metadata:
        item["shopify_order_id"] = metadata.get("order_id")
        item["shopify_customer_id"] = metadata.get("customer_id")

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)

    if event_type == "charge.failed" and charge["amount"] > 10000:
        publish_high_value_failure(charge)


def handle_payment_intent(payment_intent: Dict[str, Any], event_type: str) -> None:
    logger.debug("Payment intent %s status %s", payment_intent["id"], payment_intent["status"])


def handle_invoice(invoice: Dict[str, Any], event_type: str) -> None:
    table = dynamodb.Table(INVOICE_PAYMENTS_TABLE)

    item = {
        "invoice_id": invoice["id"],
        "subscription_id": invoice.get("subscription"),
        "customer_id": invoice.get("customer"),
        "amount_due": invoice["amount_due"] / 100,
        "amount_paid": invoice.get("amount_paid", 0) / 100,
        "amount_remaining": invoice.get("amount_remaining", 0) / 100,
        "currency": invoice["currency"].upper(),
        "status": invoice.get("status"),
        "attempt_count": invoice.get("attempt_count", 0),
        "next_payment_attempt": datetime.fromtimestamp(invoice["next_payment_attempt"], tz=timezone.utc).isoformat() if invoice.get("next_payment_attempt") else None,
        "created": datetime.fromtimestamp(invoice["created"], tz=timezone.utc).isoformat(),
        "event_type": event_type,
        "_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)


def handle_dispute(dispute: Dict[str, Any], event_type: str) -> None:
    table = dynamodb.Table(DISPUTES_TABLE)

    item = {
        "dispute_id": dispute["id"],
        "charge_id": dispute.get("charge"),
        "amount": dispute["amount"] / 100,
        "currency": dispute["currency"].upper(),
        "reason": dispute.get("reason"),
        "status": dispute.get("status"),
        "created": datetime.fromtimestamp(dispute["created"], tz=timezone.utc).isoformat(),
        "event_type": event_type,
        "_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)

    publish_dispute_alert(dispute, event_type)


def publish_high_value_failure(charge: Dict[str, Any]) -> None:
    if not ALERT_TOPIC_ARN:
        return

    message = (
        "High-Value Payment Failure\n"
        f"Charge ID: {charge['id']}\n"
        f"Amount: ${charge['amount'] / 100:.2f} {charge['currency'].upper()}\n"
        f"Customer: {charge.get('customer')}\n"
        f"Failure: {charge.get('failure_code')} - {charge.get('failure_message')}\n"
    )

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"High-Value Payment Failure ${charge['amount'] / 100:.2f}",
        Message=message,
    )


def publish_dispute_alert(dispute: Dict[str, Any], event_type: str) -> None:
    if not ALERT_TOPIC_ARN:
        return

    message = (
        "Stripe Dispute Alert\n"
        f"Dispute ID: {dispute['id']}\n"
        f"Charge ID: {dispute.get('charge')}\n"
        f"Amount: ${dispute['amount'] / 100:.2f} {dispute['currency'].upper()}\n"
        f"Reason: {dispute.get('reason')}\n"
        f"Status: {dispute.get('status')}\n"
        f"Event: {event_type}\n"
    )

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"Stripe Dispute ${dispute['amount'] / 100:.2f}",
        Message=message,
    )

