"""Integration tests for Shopify ingestion pipeline"""
import json
import os
import time
from datetime import datetime, timezone

import boto3
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="Integration test requires provisioned AWS resources",
)

BRAND = "marsmen"
ACCOUNT_ID = "631046354185"
REGION = "us-east-1"

lambda_client = boto3.client("lambda", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)

S3_BUCKET = f"{BRAND}-data-lake-{ACCOUNT_ID}"
DYNAMODB_TABLE = f"{BRAND}-orders-cache"
ORDER_PROCESSOR_FUNCTION = f"{BRAND}-shopify-order-processor"


def test_event_processing():
    mock_event = {
        "version": "0",
        "id": "test-event-123",
        "detail-type": "orders/create",
        "source": "aws.partner/shopify.com",
        "time": datetime.now(timezone.utc).isoformat(),
        "region": REGION,
        "detail": {
            "id": 9999999999999,
            "email": "test@example.com",
            "created_at": "2025-10-03T12:00:00-04:00",
            "updated_at": "2025-10-03T12:00:00-04:00",
            "number": 12345,
            "order_number": 12345,
            "total_price": "99.99",
            "subtotal_price": "89.99",
            "total_tax": "10.00",
            "currency": "USD",
            "financial_status": "paid",
            "fulfillment_status": None,
            "tags": "subscription, monthly",
            "customer": {
                "id": 8888888888888,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "Customer",
            },
            "shipping_address": {
                "city": "New York",
                "province": "NY",
                "zip": "10001",
                "country": "US",
            },
            "line_items": [
                {
                    "id": 7777777777777,
                    "sku": "MARS_Monthly",
                    "quantity": 1,
                }
            ],
        },
    }

    response = lambda_client.invoke(
        FunctionName=ORDER_PROCESSOR_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(mock_event).encode("utf-8"),
    )

    result = json.loads(response["Payload"].read())
    assert result["statusCode"] == 200

    time.sleep(2)

    today = datetime.now(timezone.utc)
    prefix = f"raw/shopify/orders/events/date={today.strftime('%Y-%m-%d')}/"

    s3_response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    assert "Contents" in s3_response

    table = dynamodb.Table(DYNAMODB_TABLE)
    db_response = table.get_item(
        Key={
            "order_id": "9999999999999",
            "created_at": mock_event["detail"]["created_at"],
        }
    )
    assert "Item" in db_response


if __name__ == "__main__":
    test_event_processing()
