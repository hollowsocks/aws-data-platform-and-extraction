"""Shopify Bulk Operation Poller"""
import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SHOPIFY_SHOP = os.environ["SHOPIFY_SHOP"]
SHOPIFY_ACCESS_TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]

GRAPHQL_URL = f"https://{SHOPIFY_SHOP}/admin/api/2024-01/graphql.json"


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    status_info = get_bulk_operation_status()
    logger.info("Bulk operation status %s", status_info.get("status"))

    return {
        "statusCode": 200,
        "status": status_info.get("status"),
        "url": status_info.get("url"),
        "error_code": status_info.get("error_code"),
        "object_count": status_info.get("object_count"),
    }


def get_bulk_operation_status() -> Dict[str, Any]:
    query = """
    {
      currentBulkOperation {
        id
        status
        errorCode
        createdAt
        completedAt
        objectCount
        fileSize
        url
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    response = requests.post(GRAPHQL_URL, headers=headers, json={"query": query}, timeout=30)
    response.raise_for_status()

    operation = response.json().get("data", {}).get("currentBulkOperation")
    if not operation:
        return {"status": "NONE"}

    return {
        "status": operation.get("status"),
        "url": operation.get("url"),
        "error_code": operation.get("errorCode"),
        "object_count": operation.get("objectCount"),
        "file_size": operation.get("fileSize"),
    }

