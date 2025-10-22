from __future__ import annotations

import gzip
import json
import os
from datetime import date, datetime, time, timedelta
from io import BytesIO
from typing import Any, Dict, Iterable, Tuple

import boto3
import pandas as pd
from dateutil import tz

from triplewhale_ingestion import build_hourly_table, fetch_hourly_metrics
from triplewhale_ingestion.config import Settings


def _load_secrets() -> None:
    secret_arn = os.getenv("TW_SECRET_ARN")
    if not secret_arn:
        return

    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")
    if not secret_string:
        return

    secret_values = json.loads(secret_string)
    for key, value in secret_values.items():
        if value and key not in os.environ:
            os.environ[key] = value


def _resolve_dates(event: Dict[str, Any], store_timezone: str) -> Tuple[datetime, datetime]:
    payload = event or {}
    if "detail" in payload:
        payload = payload["detail"] or {}

    start_str = payload.get("start_date")
    end_str = payload.get("end_date")

    if start_str and end_str:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    else:
        zone = tz.gettz(store_timezone)
        today_local = datetime.now(zone).date() if zone else date.today()
        start_date = today_local - timedelta(days=1)
        end_date = start_date

    zone = tz.gettz(store_timezone) or tz.UTC
    start_local = datetime.combine(start_date, time(0, 0, 0), tzinfo=zone)
    end_local = datetime.combine(end_date, time(23, 59, 59), tzinfo=zone)
    return start_local, end_local


def _determine_store_timezone(client: "TripleWhaleClient", settings: Settings) -> str:
    """Return the shop's primary timezone, defaulting to UTC if unknown."""
    shop_domain = settings.triple_whale_shop_domain
    if not shop_domain:
        return "UTC"

    # Import lazily to avoid circular imports during module initialisation.
    from triplewhale_ingestion.sql_loader import _detect_shop_timezone

    detected = _detect_shop_timezone(client, shop_domain)
    return detected or "UTC"


def _normalize_bool(value: str) -> bool:
    return str(value).lower() in {"1", "true", "yes", "y"}


def _extract_hour(value: Any) -> int:
    if hasattr(value, "hour"):
        return int(value.hour)
    value_str = str(value)
    try:
        return int(value_str.split(" ")[1].split(":")[0])
    except Exception:
        return int(pd.to_datetime(value).hour)


def _write_dataframe_to_s3(
    df: pd.DataFrame,
    bucket: str,
    prefix: str,
    start_dt: datetime,
    end_dt: datetime,
) -> Dict[str, Any]:
    if df.empty:
        raise ValueError("Hourly dataframe is empty; nothing to write")

    df = df.copy()
    df["local_date"] = pd.to_datetime(df["local_date"]).dt.date
    df["region"] = df["region"].astype(str)

    def _remove_timezone(column: str) -> None:
        if column not in df:
            return

        def _strip(value: object) -> object:
            if value is None:
                return value
            if isinstance(value, pd.Timestamp):
                if value.tz is not None:
                    return value.tz_localize(None)
                return value
            if value is pd.NaT:
                return value
            tzinfo = getattr(value, "tzinfo", None)
            if tzinfo is not None:
                try:
                    return value.replace(tzinfo=None)
                except AttributeError:
                    return value
            return value

        stripped = df[column].apply(_strip)
        df[column] = pd.to_datetime(stripped, errors="coerce")

    for col in ("timestamp_utc", "local_datetime", "central_datetime"):
        _remove_timezone(col)

    output_format = os.getenv("OUTPUT_FORMAT", "csv").lower()
    partition_by_hour = _normalize_bool(os.getenv("PARTITION_BY_HOUR", "false"))

    if partition_by_hour:
        df["local_hour_int"] = df["local_datetime"].apply(_extract_hour)
        group_columns: Iterable[str] = ["local_date", "region", "local_hour_int"]
    else:
        group_columns = ["local_date", "region"]

    s3 = boto3.client("s3")
    written_keys = []

    grouped = df.groupby(group_columns, sort=True)
    for group_key, partition_df in grouped:
        if partition_by_hour:
            local_date, region, hour = group_key
            hour_suffix = f"hour={int(hour):02d}/"
            file_suffix = f"_{region}_hour{int(hour):02d}"
        else:
            local_date, region = group_key
            hour_suffix = ""
            file_suffix = f"_{region}"

        year = local_date.year
        month = local_date.month
        day = local_date.day

        if output_format == "parquet":
            buffer = BytesIO()
            partition_df.to_parquet(buffer, index=False, compression="snappy")
            body = buffer.getvalue()
            content_type = "application/octet-stream"
            content_encoding = None
            extension = "parquet"
        else:
            csv_bytes = partition_df.to_csv(index=False).encode("utf-8")
            body = gzip.compress(csv_bytes)
            content_type = "text/csv"
            content_encoding = "gzip"
            extension = "csv.gz"

        key = (
            f"{prefix}/year={year}/month={month:02d}/day={day:02d}/{hour_suffix}region={region}/"
            f"growth_hourly_{local_date}{file_suffix}.{extension}"
        )

        put_params = {
            "Bucket": bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
        }
        if content_encoding:
            put_params["ContentEncoding"] = content_encoding

        s3.put_object(**put_params)
        written_keys.append(key)

    manifest_key = f"{prefix}/manifests/{datetime.utcnow().isoformat()}Z.json"
    manifest_body = json.dumps(
        {
            "written_at": datetime.utcnow().isoformat() + "Z",
            "row_count": int(df.shape[0]),
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "partitions": written_keys,
            "output_format": output_format,
            "partition_by_hour": partition_by_hour,
        }
    )
    s3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=manifest_body.encode("utf-8"),
        ContentType="application/json",
    )

    return {"files": written_keys, "manifest": manifest_key}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    _load_secrets()

    settings = Settings.from_env()
    from triplewhale_ingestion.triple_whale_client import TripleWhaleClient

    triple_client = TripleWhaleClient(settings)

    store_timezone = _determine_store_timezone(triple_client, settings)

    start_local, end_local = _resolve_dates(event, store_timezone)
    records = fetch_hourly_metrics(
        triple_client,
        settings,
        start_local,
        end_local,
        store_timezone=store_timezone,
    )

    df = build_hourly_table(records)

    requested_start = start_local.date()
    requested_end = end_local.date()
    if "local_date" in df.columns:
        df = df[(df["local_date"] >= requested_start) & (df["local_date"] <= requested_end)]

    output_bucket = os.environ["OUTPUT_BUCKET"]
    prefix = os.environ.get("OUTPUT_PREFIX", "hourly")

    write_info = _write_dataframe_to_s3(df, output_bucket, prefix, start_local, end_local)

    return {
        "status": "success",
        "row_count": int(df.shape[0]),
        "files": write_info["files"],
        "manifest": write_info["manifest"],
        "start_date": str(requested_start),
        "end_date": str(requested_end),
    }
