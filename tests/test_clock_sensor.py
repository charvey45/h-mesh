from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from h_mesh_gateway.adapters import InMemoryBrokerAdapter
from h_mesh_gateway.clock_sensor import build_clock_sensor_payload, run_clock_sensor
from h_mesh_gateway.config import GatewayRuntimeConfig, MqttRuntimeConfig
from h_mesh_gateway.service import GatewayService


class ClockSensorTests(unittest.TestCase):
    def make_service(self) -> GatewayService:
        temp_dir = Path(tempfile.mkdtemp())
        config = GatewayRuntimeConfig(
            env_file=temp_dir / "test.env",
            site_code="a",
            gateway_id="ag01",
            device_role="gateway",
            log_level="INFO",
            log_file_path=None,
            state_dir=temp_dir / "state",
            queue_db_path=temp_dir / "state" / "ag01-queue.sqlite3",
            policy_file=None,
            radio_enabled=False,
            serial_port=None,
            mqtt=MqttRuntimeConfig(
                host="127.0.0.1",
                port=1883,
                username="",
                password="",
                tls_enabled=False,
                topic_prefix="mesh/v1",
            ),
        )
        return GatewayService(config)

    def test_build_clock_sensor_payload_uses_expected_shape(self) -> None:
        payload = build_clock_sensor_payload(
            source="as01",
            site_code="a",
            captured_at=datetime(2026, 4, 26, 19, 5, 9, tzinfo=timezone.utc),
        )

        self.assertEqual(payload["msg_type"], "sensor_report")
        self.assertEqual(payload["source"], "as01")
        self.assertEqual(payload["channel"], "sensor")
        self.assertEqual(payload["payload"]["sensor_set"], "clock")
        self.assertEqual(payload["payload"]["metrics"][1]["name"], "minute_of_day")
        self.assertEqual(payload["payload"]["metrics"][1]["value"], 1145)

    def test_run_clock_sensor_persists_sensor_reports(self) -> None:
        service = self.make_service()
        broker = InMemoryBrokerAdapter()
        timestamps = iter(
            [
                datetime(2026, 4, 26, 19, 5, 9, tzinfo=timezone.utc),
                datetime(2026, 4, 26, 19, 5, 14, tzinfo=timezone.utc),
            ]
        )

        report = run_clock_sensor(
            service=service,
            broker=broker,
            source="as01",
            count=2,
            interval_seconds=0.0,
            now_provider=lambda: next(timestamps),
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["emitted_count"], 2)
        rows = service.storage.list_recent_message_events(
            channels=("sensor",),
            msg_types=("sensor_report",),
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source"], "as01")
        self.assertEqual(len(broker.published_messages), 6)
