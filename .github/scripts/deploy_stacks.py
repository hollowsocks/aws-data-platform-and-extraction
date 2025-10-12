#!/usr/bin/env python3
"""Deploy CloudFormation stacks for an ingestion job."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


TERMINAL_FAILURE_STATES = {
    "ROLLBACK_COMPLETE",
    "ROLLBACK_FAILED",
    "UPDATE_ROLLBACK_FAILED",
    "UPDATE_ROLLBACK_COMPLETE",
    "IMPORT_ROLLBACK_FAILED",
    "IMPORT_ROLLBACK_COMPLETE",
    "CREATE_FAILED",
    "DELETE_FAILED",
}


def load_parameter_file(path: Path) -> tuple[dict, dict]:
    if not path.exists():
        return {}, {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    parameters = data.get("Parameters", {})
    tags = data.get("Tags", {})
    return parameters, tags


def run(command: list[str], *, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    print("Running:", " ".join(command))
    return subprocess.run(
        command,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def get_stack_status(stack_name: str, region: str | None) -> str | None:
    command = [
        "aws",
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        stack_name,
        "--query",
        "Stacks[0].StackStatus",
        "--output",
        "text",
    ]
    if region:
        command.extend(["--region", region])

    result = run(command, check=False, capture_output=True)
    if result.returncode != 0:
        message = (result.stderr or "").strip()
        if "does not exist" in message:
            return None
        raise RuntimeError(f"Failed to describe stack {stack_name}: {message}")

    status = (result.stdout or "").strip()
    if status in {"None", ""}:
        return None
    return status


def delete_stack(stack_name: str, region: str | None) -> None:
    command = ["aws", "cloudformation", "delete-stack", "--stack-name", stack_name]
    if region:
        command.extend(["--region", region])
    run(command)

    wait_cmd = [
        "aws",
        "cloudformation",
        "wait",
        "stack-delete-complete",
        "--stack-name",
        stack_name,
    ]
    if region:
        wait_cmd.extend(["--region", region])
    run(wait_cmd)


def ensure_stack_ready(stack_name: str, region: str | None) -> str | None:
    status = get_stack_status(stack_name, region)
    if status is None:
        return None

    if status in TERMINAL_FAILURE_STATES:
        print(
            f"Stack {stack_name} is in status {status}; deleting before redeploy to clear the failed state.",
            file=sys.stderr,
        )
        delete_stack(stack_name, region)
        return None

    if status.endswith("_IN_PROGRESS"):
        raise SystemExit(
            f"Stack {stack_name} is currently {status}. Wait for the operation to finish before redeploying."
        )

    # For all other healthy states (CREATE_COMPLETE, UPDATE_COMPLETE, etc.) we let 'deploy' perform an update.
    return status


def delete_partner_event_bus(name: str, region: str | None) -> None:
    describe_cmd = ["aws", "events", "describe-event-bus", "--name", name]
    if region:
        describe_cmd.extend(["--region", region])

    result = run(describe_cmd, check=False, capture_output=True)
    if result.returncode != 0:
        return

    print(f"Deleting existing partner event bus {name} prior to stack deployment.", file=sys.stderr)

    delete_cmd = ["aws", "events", "delete-event-bus", "--name", name]
    if region:
        delete_cmd.extend(["--region", region])
    run(delete_cmd)


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

        existing_status = ensure_stack_ready(stack_name, region)

        capabilities = stack.get("capabilities", [])
        parameter_path = Path("ci") / "environments" / environment / job / f"{stack['name']}.json"
        parameters, tags = load_parameter_file(parameter_path)

        partner_source_name = parameters.get("PartnerEventSourceName")
        if (
            stack.get("name") == "eventbridge"
            and partner_source_name
            and existing_status is None
        ):
            delete_partner_event_bus(partner_source_name, region)

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

        run(cmd)


if __name__ == "__main__":
    main()
