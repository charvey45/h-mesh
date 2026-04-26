from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from h_mesh_gateway.config import GatewayRuntimeConfig, load_runtime_config
from h_mesh_gateway.service import GatewayService
from h_mesh_gateway.storage import GatewayStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or validate the h-mesh gateway service scaffold."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-config", help="Load and validate a gateway env file."
    )
    validate_parser.add_argument("--env", required=True, help="Path to the env file.")
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the validated runtime config as JSON.",
    )

    run_parser = subparsers.add_parser(
        "run-skeleton",
        help="Initialize the gateway service scaffold without live adapters.",
    )
    run_parser.add_argument("--env", required=True, help="Path to the env file.")
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the startup report as JSON.",
    )

    init_db_parser = subparsers.add_parser(
        "init-db",
        help="Initialize the gateway SQLite schema without starting the service skeleton.",
    )
    init_db_parser.add_argument("--env", required=True, help="Path to the env file.")
    init_db_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the initialized schema report as JSON.",
    )
    return parser


def configure_logging(config: GatewayRuntimeConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def render_payload(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    for key, value in payload.items():
        print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_runtime_config(Path(args.env))

    if args.command == "validate-config":
        render_payload(config.as_dict(), args.json)
        return 0

    if args.command == "init-db":
        configure_logging(config)
        storage = GatewayStorage(config.queue_db_path)
        render_payload(
            {
                "queue_db_path": str(config.queue_db_path),
                "tables": storage.initialize(),
            },
            args.json,
        )
        return 0

    configure_logging(config)
    service = GatewayService(config)
    startup_report = service.run_skeleton()
    render_payload(startup_report, args.json)
    return 0
