from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from h_mesh_gateway.config import load_runtime_config


class ConfigTests(unittest.TestCase):
    def write_env(self, body: str) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = temp_dir / "gateway.env"
        env_path.write_text(body, encoding="utf-8")
        return env_path

    def test_load_runtime_config_accepts_valid_gateway_id(self) -> None:
        env_path = self.write_env(
            "\n".join(
                [
                    "SITE_CODE=a",
                    "DEVICE_ROLE=gateway",
                    "GATEWAY_ID=ag01",
                    "MQTT_HOST=127.0.0.1",
                    "MQTT_PORT=1883",
                    "MQTT_TLS_ENABLED=false",
                ]
            )
        )

        config = load_runtime_config(env_path)

        self.assertEqual(config.gateway_id, "ag01")
        self.assertEqual(config.site_code, "a")
        self.assertFalse(config.radio_enabled)
        self.assertEqual(config.mqtt.topic_prefix, "mesh/v1")

    def test_invalid_gateway_role_is_rejected(self) -> None:
        env_path = self.write_env(
            "\n".join(
                [
                    "SITE_CODE=a",
                    "DEVICE_ROLE=radio",
                    "GATEWAY_ID=ag01",
                    "MQTT_TLS_ENABLED=false",
                ]
            )
        )

        with self.assertRaises(ValueError):
            load_runtime_config(env_path)

    def test_invalid_gateway_id_is_rejected(self) -> None:
        env_path = self.write_env(
            "\n".join(
                [
                    "SITE_CODE=a",
                    "DEVICE_ROLE=gateway",
                    "GATEWAY_ID=ar01",
                    "MQTT_TLS_ENABLED=false",
                ]
            )
        )

        with self.assertRaises(ValueError):
            load_runtime_config(env_path)
