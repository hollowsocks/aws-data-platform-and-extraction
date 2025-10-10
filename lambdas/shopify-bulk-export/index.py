"""Shopify Bulk Operations Export Lambda"""
import json
import logging
import os
from typing import Any, Dict, Optional

import boto3
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

stepfunctions = boto3.client("stepfunctions")

SHOPIFY_SHOP = os.environ["SHOPIFY_SHOP"]
SHOPIFY_ACCESS_TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]
S3_BUCKET = os.environ["S3_BUCKET"]
ENVIRONMENT = os.environ["ENVIRONMENT"]

GRAPHQL_URL = f"https://{SHOPIFY_SHOP}/admin/api/2024-01/graphql.json"


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    export_type = event.get("export_type", "orders")
    start_date = event.get("start_date")
    end_date = event.get("end_date")

    query = build_bulk_query(export_type, start_date, end_date)
    operation_id = submit_bulk_operation(query)

    logger.info("Submitted Shopify bulk operation %s", operation_id)

    return {
        "statusCode": 200,
        "operation_id": operation_id,
        "export_type": export_type,
        "start_date": start_date,
        "end_date": end_date,
    }


def build_bulk_query(export_type: str, start_date: Optional[str], end_date: Optional[str]) -> str:
    if export_type != "orders":
        raise ValueError(f"Unsupported export type: {export_type}")

    filters = []
    if start_date:
        filters.append(f"created_at:>={start_date}")
    if end_date:
        filters.append(f"created_at:<={end_date}")

    query_filter = " AND ".join(filters)

    query = f"""
    mutation {{
      bulkOperationRunQuery(
        query: \"\"\"
        {{
          orders(query: \"{query_filter}\") {{
            edges {{
              node {{
                id
                name
                email
                createdAt
                updatedAt
                cancelledAt
                cancelReason
                totalPriceSet {{ shopMoney {{ amount currencyCode }} }}
                subtotalPriceSet {{ shopMoney {{ amount currencyCode }} }}
                totalDiscountsSet {{ shopMoney {{ amount currencyCode }} }}
                totalTaxSet {{ shopMoney {{ amount currencyCode }} }}
                financialStatus
                fulfillmentStatus
                tags
                note
                customer {{
                  id
                  email
                  firstName
                  lastName
                  phone
                  tags
                }}
                shippingAddress {{
                  city
                  province
                  zip
                  country
                  phone
                }}
                billingAddress {{
                  city
                  province
                  zip
                  country
                }}
                lineItems {{
                  edges {{
                    node {{
                      id
                      name
                      quantity
                      sku
                      variant {{ id title }}
                      originalUnitPriceSet {{ shopMoney {{ amount currencyCode }} }}
                    }}
                  }}
                }}
                fulfillments {{
                  id
                  status
                  createdAt
                  updatedAt
                  trackingInfo {{ number url company }}
                }}
              }}
            }}
          }}
        }}
        \"\"\"
      ) {{
        bulkOperation {{
          id
          status
        }}
        userErrors {{
          field
          message
        }}
      }}
    }}
    """

    return query.strip()


def submit_bulk_operation(query: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    response = requests.post(GRAPHQL_URL, headers=headers, json={"query": query}, timeout=30)
    response.raise_for_status()

    result = response.json()
    if "errors" in result:
        raise RuntimeError(f"GraphQL errors: {result['errors']}")

    data = result.get("data", {}).get("bulkOperationRunQuery", {})
    if data.get("userErrors"):
        raise RuntimeError(f"User errors: {data['userErrors']}")

    operation = data.get("bulkOperation", {})
    operation_id = operation.get("id")
    if not operation_id:
        raise RuntimeError(f"No operation ID returned: {result}")

    return operation_id

