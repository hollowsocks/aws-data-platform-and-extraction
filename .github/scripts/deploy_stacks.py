#!/usr/bin/env python3
"""Deploy CloudFormation stacks for an ingestion job."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def load_parameter_file(path: Path) -> tuple[dict, dict]:
    if not path.exists():
        return {}, {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    parameters = data.get("Parameters", {})
    tags = data.get("Tags", {})
    return parameters, tags


def run_deploy(command: list[str]) -> None:
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)


def main() -> None:
    stacks_raw = os.getenv("STACKS")
    if not stacks_raw:
        raise SystemExit("STACKS environment variable is required")

    stacks = json.loads(stacks_raw)
    brand = os.environ["BRAND"]
    job = os.environ["JOB"]
    environment = os.environ.get("ENVIRONMENT", "prod")
    region = os.environ.get("REGION") or os.environ.get("AWS_DEFAULT_REGION")

    for stack in stacks:
        stack_name = stack.get("stack_name") or f"{brand}-{environment}-{job}-{stack['name']}"
        template = stack["template"]
        template_path = Path(template)
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template}")

        capabilities = stack.get("capabilities", [])
        parameter_path = Path("ci") / "environments" / environment / job / f"{stack['name']}.json"
        parameters, tags = load_parameter_file(parameter_path)

        cmd: list[str] = [
            "aws",
            "cloudformation",
            "deploy",
            "--template-file",
            str(template_path),
            "--stack-name",
            stack_name,
        ]

        if region:
            cmd.extend(["--region", region])

        if capabilities:
            cmd.extend(["--capabilities", " ".join(capabilities)])

        if parameters:
            overrides = [f"{key}={value}" for key, value in parameters.items()]
            cmd.extend(["--parameter-overrides", *overrides])

        if tags:
            tag_args = [f"{key}={value}" for key, value in tags.items()]
            cmd.extend(["--tags", *tag_args])

        run_deploy(cmd)


if __name__ == "__main__":
    main()
