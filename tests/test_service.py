from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from h_mesh_gateway.config import load_runtime_config
from h_mesh_gateway.service import GatewayService


class ServiceTests(unittest.TestCase):
    def write_env(self, temp_dir: Path) -> Path:
        env_path = temp_dir / "gateway.env"
        env_path.write_text(
            "\n".join(
                [
                    "SITE_CODE=a",
                    "DEVICE_ROLE=gateway",
                    "GATEWAY_ID=ag01",
                    "MQTT_HOST=127.0.0.1",
                    "MQTT_PORT=1883",
                    "MQTT_TLS_ENABLED=false",
                    f"STATE_DIR={temp_dir / 'state'}",
                    f"QUEUE_DB_PATH={temp_dir / 'state' / 'queue.sqlite3'}",
                    "RADIO_ENABLED=false",
                ]
            ),
            encoding="utf-8",
        )
        return env_path

    def test_run_skeleton_creates_runtime_paths(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir)

        config = load_runtime_config(env_path)
        service = GatewayService(config)
        report = service.run_skeleton()

        self.assertTrue((temp_dir / "state").exists())
        self.assertEqual(report["gateway_id"], "ag01")
        self.assertEqual(report["health"]["radio_state"], "missing")
        self.assertEqual(report["health"]["queue_depth"], 1)
        self.assertEqual(
            report["storage_tables"],
            [
                "dedupe_cache",
                "gateway_observations",
                "message_events",
                "outbound_queue",
            ],
        )
        queued_events = service.storage.list_pending_outbound_events()
        self.assertEqual(len(queued_events), 1)
        self.assertEqual(
            json.loads(queued_events[0]["payload_json"]),
            report["health"],
        )

    def test_run_skeleton_can_be_repeated_against_same_queue_database(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir)

        config = load_runtime_config(env_path)

        first_service = GatewayService(config)
        first_report = first_service.run_skeleton()

        second_service = GatewayService(config)
        second_report = second_service.run_skeleton()

        self.assertEqual(first_report["health"]["queue_depth"], 1)
        self.assertEqual(second_report["health"]["queue_depth"], 2)
