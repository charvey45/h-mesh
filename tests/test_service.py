from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from h_mesh_gateway.config import load_runtime_config
from h_mesh_gateway.service import GatewayService


class ServiceTests(unittest.TestCase):
    def test_run_skeleton_creates_runtime_paths(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
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

        config = load_runtime_config(env_path)
        service = GatewayService(config)
        report = service.run_skeleton()

        self.assertTrue((temp_dir / "state").exists())
        self.assertEqual(report["gateway_id"], "ag01")
        self.assertEqual(report["health"]["radio_state"], "missing")
