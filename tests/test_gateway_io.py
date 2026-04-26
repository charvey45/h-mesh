from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from h_mesh_gateway.adapters import InMemoryBrokerAdapter, InMemoryRadioAdapter
from h_mesh_gateway.health import BrokerState, RadioState
from h_mesh_gateway.config import load_runtime_config
from h_mesh_gateway.service import GatewayService


OPS_FIXTURE = {
    "schema_version": 1,
    "msg_type": "ops_broadcast",
    "msg_id": "ops-test-0001",
    "source": "ar01",
    "source_site": "a",
    "target": None,
    "target_scope": "site-b-ops",
    "channel": "ops",
    "observed_by": "ag01",
    "captured_at": "2026-04-26T10:00:00+00:00",
    "expires_at": "2030-04-26T10:15:00+00:00",
    "correlation_id": None,
    "priority": "normal",
    "flags": [],
    "payload": {"text": "integration harness message"},
}


class GatewayIoTests(unittest.TestCase):
    def write_env(self, temp_dir: Path, *, site_code: str, gateway_id: str, radio_enabled: bool) -> Path:
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
                    f"RADIO_ENABLED={'true' if radio_enabled else 'false'}",
                    "SERIAL_PORT=sim://radio" if radio_enabled else "SERIAL_PORT=",
                ]
            ),
            encoding="utf-8",
        )
        return env_path

    def test_simulated_rf_to_mqtt_publishes_via_broker_adapter(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir, site_code="a", gateway_id="ag01", radio_enabled=False)
        config = load_runtime_config(env_path)
        service = GatewayService(config)
        broker = InMemoryBrokerAdapter()

        report = service.simulate_rf_to_mqtt(OPS_FIXTURE, broker=broker)

        self.assertEqual(report["status"], "published")
        self.assertEqual(report["topic"], "mesh/v1/site-a/ops/up")
        self.assertEqual(report["queue_depth"], 0)
        self.assertEqual(len(broker.published_messages), 1)
        self.assertEqual(json.loads(broker.published_messages[0].payload_json)["msg_id"], "ops-test-0001")

    def test_simulated_mqtt_to_radio_emits_fixture_once(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir, site_code="b", gateway_id="bg02", radio_enabled=True)
        config = load_runtime_config(env_path)
        service = GatewayService(config)
        broker = InMemoryBrokerAdapter()
        radio = InMemoryRadioAdapter()
        broker.publish("mesh/v1/site-a/ops/up", json.dumps(OPS_FIXTURE, sort_keys=True))

        report = service.simulate_mqtt_to_radio(
            topic="mesh/v1/site-a/ops/up",
            broker=broker,
            radio=radio,
            timeout_seconds=0.1,
        )

        self.assertEqual(report["status"], "emitted")
        self.assertEqual(report["radio_state"], "healthy")
        self.assertEqual(radio.pop_emission()["msg_id"], "ops-test-0001")

    def test_duplicate_mqtt_message_is_suppressed(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir, site_code="b", gateway_id="bg02", radio_enabled=True)
        config = load_runtime_config(env_path)
        service = GatewayService(config)
        broker = InMemoryBrokerAdapter()
        radio = InMemoryRadioAdapter()
        payload_json = json.dumps(OPS_FIXTURE, sort_keys=True)
        broker.publish("mesh/v1/site-a/ops/up", payload_json)
        broker.publish("mesh/v1/site-a/ops/up", payload_json)

        first = service.simulate_mqtt_to_radio(
            topic="mesh/v1/site-a/ops/up",
            broker=broker,
            radio=radio,
            timeout_seconds=0.1,
        )
        second = service.simulate_mqtt_to_radio(
            topic="mesh/v1/site-a/ops/up",
            broker=broker,
            radio=radio,
            timeout_seconds=0.1,
        )

        self.assertEqual(first["status"], "emitted")
        self.assertEqual(second["status"], "duplicate")

    def test_rf_to_mqtt_queues_when_broker_publish_fails(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir, site_code="a", gateway_id="ag01", radio_enabled=False)
        config = load_runtime_config(env_path)
        service = GatewayService(config)

        class FailingBroker:
            def current_state(self) -> BrokerState:
                return BrokerState.DISCONNECTED

            def publish(self, topic: str, payload_json: str) -> None:
                del topic, payload_json
                raise RuntimeError("broker unavailable")

            def receive_one(self, topic: str, timeout_seconds: float):
                del topic, timeout_seconds
                return None

        report = service.simulate_rf_to_mqtt(OPS_FIXTURE, broker=FailingBroker())

        self.assertEqual(report["status"], "queued")
        self.assertEqual(report["queue_depth"], 1)
        self.assertEqual(report["broker_state"], "disconnected")

    def test_mqtt_to_radio_reports_unavailable_radio(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        env_path = self.write_env(temp_dir, site_code="b", gateway_id="bg02", radio_enabled=True)
        config = load_runtime_config(env_path)
        service = GatewayService(config)
        broker = InMemoryBrokerAdapter()
        radio = InMemoryRadioAdapter(state=RadioState.MISSING)
        broker.publish("mesh/v1/site-a/ops/up", json.dumps(OPS_FIXTURE, sort_keys=True))

        report = service.simulate_mqtt_to_radio(
            topic="mesh/v1/site-a/ops/up",
            broker=broker,
            radio=radio,
            timeout_seconds=0.1,
        )

        self.assertEqual(report["status"], "radio_unavailable")
        self.assertEqual(report["radio_state"], "missing")
        self.assertIsNotNone(broker.receive_one("mesh/v1/site-a/ops/up", 0.1))
