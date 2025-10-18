#!/usr/bin/env python3
"""Kick off Shopify bulk backfill executions in Step Functions."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess

DEFAULT_STATE_MACHINE = "arn:aws:states:us-east-1:631046354185:stateMachine:marsmen-shopify-bulk-orders"
DEFAULT_PROFILE = os.environ.get("AWS_PROFILE", "marsmen-direct")


def run_execution(state_machine: str, name: str, payload: dict, profile: str) -> None:
    cmd = [
        "aws",
        "stepfunctions",
        "start-execution",
        "--state-machine-arn",
        state_machine,
        "--name",
        name,
        "--input",
        json.dumps(payload),
        "--profile",
        profile,
    ]
    subprocess.run(cmd, check=True)


def iter_windows(start: dt.datetime, end: dt.datetime, window_days: int):
    start = start.replace(tzinfo=dt.timezone.utc)
    end = end.replace(tzinfo=dt.timezone.utc)
    idx = 0
    current = start
    while current < end:
        next_dt = min(current + dt.timedelta(days=window_days), end)
        yield idx, current, next_dt
        idx += 1
        current = next_dt


def main():
    parser = argparse.ArgumentParser(description="Run Shopify bulk backfill in windows")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--window", type=int, default=7, help="Window size in days")
    parser.add_argument("--state-machine", default=DEFAULT_STATE_MACHINE, help="State machine ARN")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="AWS profile")
    parser.add_argument("--prefix", default="backfill", help="Execution name prefix")
    args = parser.parse_args()

    start_dt = dt.datetime.strptime(args.start, "%Y-%m-%d")
    # Treat the end date as inclusive for the requested window
    end_dt = dt.datetime.strptime(args.end, "%Y-%m-%d") + dt.timedelta(days=1)

    for idx, window_start, window_end in iter_windows(start_dt, end_dt, args.window):
        name = f"{args.prefix}-{window_start.strftime('%Y%m%d')}-{window_end.strftime('%Y%m%d')}"
        payload = {
            "export_type": "orders",
            "start_date": window_start.isoformat().replace("+00:00", "Z"),
            "end_date": window_end.isoformat().replace("+00:00", "Z"),
        }
        print(f"Starting execution {name} for {payload['start_date']} -> {payload['end_date']}")
        run_execution(args.state_machine, name, payload, args.profile)


if __name__ == "__main__":
    main()
