from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, Tuple

import boto3

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
if not STATE_MACHINE_ARN:
    raise RuntimeError("STATE_MACHINE_ARN environment variable is required")

stepfunctions = boto3.client("stepfunctions")


def _parse_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}

    body = event.get("body")
    if isinstance(body, str) and body:
        try:
            payload.update(json.loads(body))
        except json.JSONDecodeError:
            pass
    elif isinstance(body, dict):
        payload.update(body)

    qs = event.get("queryStringParameters") or {}
    if isinstance(qs, dict):
        payload.setdefault("start_date", qs.get("start_date"))
        payload.setdefault("end_date", qs.get("end_date"))

    return payload


def _resolve_dates(payload: Dict[str, Any]) -> Tuple[str, str]:
    start_str = payload.get("start_date")
    end_str = payload.get("end_date")

    if start_str and end_str:
        return str(start_str), str(end_str)

    yesterday = date.today() - timedelta(days=1)
    iso = yesterday.isoformat()
    return iso, iso


def _start_execution(start_date: str, end_date: str) -> str:
    execution_name = f"refresh-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    response = stepfunctions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=execution_name,
        input=json.dumps({"start_date": start_date, "end_date": end_date}),
    )
    return response["executionArn"]


def _response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    payload = _parse_payload(event)
    start_date, end_date = _resolve_dates(payload)

    try:
        execution_arn = _start_execution(start_date, end_date)
    except Exception as exc:  # pragma: no cover - surface AWS errors
        return _response(500, {"error": str(exc)})

    return _response(
        202,
        {
            "message": "Refresh started",
            "executionArn": execution_arn,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
