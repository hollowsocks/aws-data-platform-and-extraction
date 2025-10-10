"""Shopify Bulk Operation Downloader"""
import gzip
import json
import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

S3_BUCKET = os.environ["S3_BUCKET"]
BRAND = os.environ["BRAND"]


def handler(event: Dict[str, Any], _: Any) -> Dict[str, Any]:
    download_url = event["url"]
    export_type = event.get("export_type", "orders")

    logger.info("Downloading bulk %s data", export_type)

    raw_data = download_file(download_url)
    records = parse_jsonl(raw_data)
    logger.info("Parsed %d records", len(records))

    parquet_buffer = convert_to_parquet(records)
    s3_key = upload_to_s3(parquet_buffer, export_type)

    return {
        "statusCode": 200,
        "s3_key": s3_key,
        "record_count": len(records),
        "export_type": export_type,
    }


def download_file(url: str) -> bytes:
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    content = response.content

    try:
        return gzip.decompress(content)
    except OSError:
        return content


def parse_jsonl(data: bytes) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse line: %s", exc)
    return records


def convert_to_parquet(records: List[Dict[str, Any]]) -> BytesIO:
    if not records:
        raise ValueError("No records to convert")

    table = pa.Table.from_pylist([flatten_record(record) for record in records])
    buffer = BytesIO()
    pq.write_table(table, buffer, compression="snappy")
    buffer.seek(0)
    return buffer


def flatten_record(record: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}_{sub_key}"] = sub_value
        elif isinstance(value, list):
            flat[key] = json.dumps(value)
        else:
            flat[key] = value
    return flat


def upload_to_s3(buffer: BytesIO, export_type: str) -> str:
    now = datetime.now(timezone.utc)
    s3_key = (
        f"raw/shopify/{export_type}/snapshots/"
        f"date={now.strftime('%Y-%m-%d')}/"
        f"{export_type}_{now.strftime('%Y%m%d_%H%M%S')}.parquet"
    )

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=buffer.getvalue(),
        ContentType="application/octet-stream",
        Metadata={
            "export-type": export_type,
            "exported-at": now.isoformat(),
            "brand": BRAND,
        },
    )

    return s3_key

