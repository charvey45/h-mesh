from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from h_mesh_gateway.adapters import InMemoryBrokerAdapter
from h_mesh_gateway.cli import build_observe_topic_payload, main
from h_mesh_gateway.interfaces import BrokerMessage


class ObserveTopicCliTests(unittest.TestCase):
    def write_env(self, temp_dir: Path, *, site_code: str = "a", gateway_id: str = "ag01") -> Path:
        env_path = temp_dir / f"{gateway_id}.env"
        env_path.write_text(
            "\n".join(
                [
                    f"SITE_CODE={site_code}",
                    "DEVICE_ROLE=gateway",
                    f"GATEWAY_ID={gateway_id}",
                    "MQTT_HOST=127.0.0.1",
                    "MQTT_PORT=1883",
                    "MQTT_TLS_ENABLED=false",
                    f"STATE_DIR={temp_dir / 'state'}",
                    f"QUEUE_DB_PATH={temp_dir / 'state' / f'{gateway_id}.sqlite3'}",
                    "RADIO_ENABLED=false",
                    "SERIAL_PORT=",
                ]
            ),
            encoding="utf-8",
        )
        return env_path

    def test_build_observe_topic_payload_marks_timeout_when_count_is_short(self) -> None:
        payload = build_observe_topic_payload(
            "mesh/v1/site-a/gateway/ag01/state",
            [
                BrokerMessage(
                    topic="mesh/v1/site-a/gateway/ag01/state",
                    payload_json=json.dumps({"queue_depth": 1}, sort_keys=True),
                )
            ],
            expected_message_count=2,
        )

        self.assertEqual(payload["status"], "timeout")
        self.assertEqual(payload["expected_message_count"], 2)
        self.assertEqual(payload["message_count"], 1)

    def test_observe_topic_returns_non_zero_when_expected_messages_are_missing(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir)
        broker = InMemoryBrokerAdapter()
        broker.publish(
            "mesh/v1/site-a/gateway/ag01/state",
            json.dumps({"queue_depth": 1}, sort_keys=True),
        )

        stdout = io.StringIO()
        with patch("h_mesh_gateway.cli.build_broker_adapter", return_value=broker):
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "observe-topic",
                        "--env",
                        str(env_path),
                        "--topic",
                        "mesh/v1/site-a/gateway/ag01/state",
                        "--max-messages",
                        "2",
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 1)
        observed = json.loads(stdout.getvalue())
        self.assertEqual(observed["status"], "timeout")
        self.assertEqual(observed["message_count"], 1)

    def test_observe_topic_can_allow_partial_results(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir)
        broker = InMemoryBrokerAdapter()
        broker.publish(
            "mesh/v1/site-a/gateway/ag01/state",
            json.dumps({"queue_depth": 1}, sort_keys=True),
        )

        stdout = io.StringIO()
        with patch("h_mesh_gateway.cli.build_broker_adapter", return_value=broker):
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "observe-topic",
                        "--env",
                        str(env_path),
                        "--topic",
                        "mesh/v1/site-a/gateway/ag01/state",
                        "--max-messages",
                        "2",
                        "--allow-partial",
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        observed = json.loads(stdout.getvalue())
        self.assertEqual(observed["status"], "timeout")
        self.assertEqual(observed["message_count"], 1)

    def test_run_clock_sensor_emits_sensor_report_output(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir)
        broker = InMemoryBrokerAdapter()

        stdout = io.StringIO()
        with patch("h_mesh_gateway.cli.build_broker_adapter", return_value=broker):
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "run-clock-sensor",
                        "--env",
                        str(env_path),
                        "--source",
                        "as01",
                        "--count",
                        "1",
                        "--interval-seconds",
                        "0",
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        observed = json.loads(stdout.getvalue())
        self.assertEqual(observed["status"], "complete")
        self.assertEqual(observed["source"], "as01")
        self.assertEqual(observed["emitted_count"], 1)
