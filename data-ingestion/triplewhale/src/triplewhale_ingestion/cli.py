from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .aggregator import build_daily_report, build_hourly_table
from .config import Settings
from .sql_loader import fetch_hourly_metrics
from .triple_whale_client import TripleWhaleClient


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate growth KPIs from Triple Whale")
    parser.add_argument("--start-date", help="ISO date (YYYY-MM-DD) inclusive", dest="start_date")
    parser.add_argument("--end-date", help="ISO date (YYYY-MM-DD) inclusive", dest="end_date")
    parser.add_argument(
        "--output",
        help="Destination file path; use '-' to print CSV to stdout",
        dest="output",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument(
        "--granularity",
        choices=["daily", "hourly"],
        default="daily",
        help="Report granularity (default: daily)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args(argv)


def resolve_dates(settings: Settings, args: argparse.Namespace) -> tuple[datetime, datetime]:
    today = datetime.utcnow().date()
    default_start = settings.default_start_date or today - timedelta(days=1)
    default_end = settings.default_end_date or today - timedelta(days=1)

    start_date = args.start_date or default_start.isoformat()
    end_date = args.end_date or default_end.isoformat()

    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00+00:00")
    end_dt = datetime.fromisoformat(f"{end_date}T23:59:59+00:00")
    if start_dt > end_dt:
        raise ValueError("start-date must be on or before end-date")
    return start_dt, end_dt


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    settings = Settings.from_env()

    if args.debug:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    start_dt, end_dt = resolve_dates(settings, args)

    client = TripleWhaleClient(settings)
    hourly_records = fetch_hourly_metrics(client, settings, start_dt, end_dt)
    requested_start_date = start_dt.date()
    requested_end_date = end_dt.date()

    if args.granularity == "hourly":
        report_df = build_hourly_table(hourly_records)
    else:
        report_df = build_daily_report(hourly_records)

    if "local_date" in report_df.columns:
        report_df = report_df[
            (report_df["local_date"] >= requested_start_date)
            & (report_df["local_date"] <= requested_end_date)
        ]

    if args.output in (None, "-"):
        if args.format == "json":
            print(report_df.to_json(orient="records", indent=2, date_format="iso"))
        else:
            print(report_df.to_csv(index=False))
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "json":
            output_path.write_text(
                report_df.to_json(orient="records", indent=2, date_format="iso"),
                encoding="utf-8",
            )
        else:
            report_df.to_csv(output_path, index=False)


if __name__ == "__main__":  # pragma: no cover
    main()
