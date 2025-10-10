#!/usr/bin/env python3
"""Render ingestion job metadata as a GitHub Actions matrix."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path("ci/ingestion_jobs.json")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_matrix(config: dict, job_filter: str | None) -> list[dict]:
    defaults = config.get("defaults", {})
    jobs = config.get("jobs", {})
    if job_filter and job_filter != "all" and job_filter not in jobs:
        raise KeyError(f"Job '{job_filter}' is not defined in ci/ingestion_jobs.json")

    include: list[dict] = []
    for name, details in jobs.items():
        if job_filter and job_filter != "all" and name != job_filter:
            continue

        include.append(
            {
                "job": name,
                "brand": details.get("brand", defaults.get("brand")),
                "region": details.get("region", defaults.get("region")),
                "account_id": details.get("account_id", defaults.get("account_id")),
                "lambdas": details.get("lambdas", []),
                "stacks": details.get("stacks", []),
            }
        )

    if not include:
        raise ValueError("No ingestion jobs matched the provided filter")

    return include


def main() -> None:
    job_filter = os.getenv("INGESTION_JOB")
    config = load_config()
    matrix = build_matrix(config, job_filter.strip().lower() if job_filter else None)
    json.dump(matrix, sys.stdout)


if __name__ == "__main__":
    main()
