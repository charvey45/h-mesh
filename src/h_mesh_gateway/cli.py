from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from h_mesh_gateway.adapters import FileRadioAdapter, PahoMqttBrokerAdapter
from h_mesh_gateway.config import GatewayRuntimeConfig, load_runtime_config
from h_mesh_gateway.health import RadioState
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

    simulate_rf_parser = subparsers.add_parser(
        "simulate-rf-to-mqtt",
        help="Read a fixture as simulated RF input and publish it through the gateway MQTT adapter.",
    )
    simulate_rf_parser.add_argument("--env", required=True, help="Path to the env file.")
    simulate_rf_parser.add_argument(
        "--payload-file",
        required=True,
        help="Path to the JSON fixture that represents a radio-observed message.",
    )
    simulate_rf_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the publish report as JSON.",
    )

    simulate_mqtt_parser = subparsers.add_parser(
        "simulate-mqtt-to-radio",
        help="Consume one MQTT message and emit it through the simulated radio adapter.",
    )
    simulate_mqtt_parser.add_argument("--env", required=True, help="Path to the env file.")
    simulate_mqtt_parser.add_argument("--topic", required=True, help="MQTT topic to consume.")
    simulate_mqtt_parser.add_argument(
        "--radio-output",
        required=True,
        help="Path where the simulated radio emission JSON should be written.",
    )
    simulate_mqtt_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Maximum time to wait for one MQTT message.",
    )
    simulate_mqtt_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the emit report as JSON.",
    )

    publish_health_parser = subparsers.add_parser(
        "publish-health",
        help="Publish a gateway health snapshot on the documented gateway state topic.",
    )
    publish_health_parser.add_argument("--env", required=True, help="Path to the env file.")
    publish_health_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the health publish report as JSON.",
    )

    observe_topic_parser = subparsers.add_parser(
        "observe-topic",
        help="Observe one or more MQTT messages on a topic and print them as JSON.",
    )
    observe_topic_parser.add_argument("--env", required=True, help="Path to the env file.")
    observe_topic_parser.add_argument("--topic", required=True, help="MQTT topic filter to observe.")
    observe_topic_parser.add_argument(
        "--max-messages",
        type=int,
        default=1,
        help="Maximum number of messages to capture before exiting.",
    )
    observe_topic_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Maximum time to wait for the requested messages.",
    )
    observe_topic_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the observed messages as JSON.",
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


def build_broker_adapter(config: GatewayRuntimeConfig, *, client_suffix: str) -> PahoMqttBrokerAdapter:
    return PahoMqttBrokerAdapter(
        host=config.mqtt.host,
        port=config.mqtt.port,
        client_id=f"{config.gateway_id}-{client_suffix}",
        username=config.mqtt.username,
        password=config.mqtt.password,
        tls_enabled=config.mqtt.tls_enabled,
    )


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

    if args.command == "simulate-rf-to-mqtt":
        configure_logging(config)
        service = GatewayService(config)
        payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
        report = service.simulate_rf_to_mqtt(
            payload,
            broker=build_broker_adapter(config, client_suffix="rf-publisher"),
        )
        render_payload(report, args.json)
        return 0

    if args.command == "simulate-mqtt-to-radio":
        configure_logging(config)
        service = GatewayService(config)
        report = service.simulate_mqtt_to_radio(
            topic=args.topic,
            broker=build_broker_adapter(config, client_suffix="mqtt-subscriber"),
            radio=FileRadioAdapter(
                output_path=Path(args.radio_output),
                state=RadioState.HEALTHY if config.radio_enabled else RadioState.MISSING,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        render_payload(report, args.json)
        return 0

    if args.command == "publish-health":
        configure_logging(config)
        service = GatewayService(config)
        report = service.publish_health_snapshot(
            build_broker_adapter(config, client_suffix="health-publisher"),
            radio_state=RadioState.HEALTHY if config.radio_enabled else RadioState.MISSING,
        )
        render_payload(report, args.json)
        return 0

    if args.command == "observe-topic":
        configure_logging(config)
        broker = build_broker_adapter(config, client_suffix="topic-observer")
        messages = broker.receive_many(
            args.topic,
            max_messages=args.max_messages,
            timeout_seconds=args.timeout_seconds,
        )
        payload = {
            "topic": args.topic,
            "message_count": len(messages),
            "messages": [
                {
                    "topic": message.topic,
                    "payload": json.loads(message.payload_json),
                }
                for message in messages
            ],
        }
        render_payload(payload, args.json)
        return 0

    configure_logging(config)
    service = GatewayService(config)
    startup_report = service.run_skeleton()
    render_payload(startup_report, args.json)
    return 0
