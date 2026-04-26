from __future__ import annotations

import logging
import json

from h_mesh_gateway.config import GatewayRuntimeConfig
from h_mesh_gateway.health import (
    BrokerState,
    ProcessState,
    RadioState,
    initial_health_snapshot,
)
from h_mesh_gateway.storage import (
    GatewayObservationRecord,
    GatewayStorage,
    MessageEventRecord,
    OutboundQueueRecord,
)


LOGGER = logging.getLogger(__name__)


class GatewayService:
    def __init__(self, config: GatewayRuntimeConfig) -> None:
        self.config = config
        self.health = initial_health_snapshot(config.gateway_id, config.site_code)
        self.storage = GatewayStorage(config.queue_db_path)

    def _ensure_runtime_paths(self) -> None:
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.config.queue_db_path.parent.mkdir(parents=True, exist_ok=True)

    def _determine_radio_state(self) -> RadioState:
        if not self.config.radio_enabled:
            return RadioState.MISSING
        if self.config.serial_port:
            return RadioState.HEALTHY
        return RadioState.UNHEALTHY

    def _determine_broker_state(self) -> BrokerState:
        # MQTT integration is intentionally stubbed in this scaffold.
        return BrokerState.UNKNOWN

    def run_skeleton(self) -> dict[str, object]:
        self._ensure_runtime_paths()
        tables = self.storage.initialize()
        self.storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id=self.config.gateway_id,
                kind="service_initialized",
                detail="Gateway skeleton initialized storage",
            )
        )
        startup_msg_id = f"{self.config.gateway_id}-startup"
        self.storage.record_message_event(
            MessageEventRecord(
                msg_id=startup_msg_id,
                msg_type="gateway_state",
                source=self.config.gateway_id,
                source_site=self.config.site_code,
                channel="ops",
                captured_at=self.health.observed_at.isoformat(),
                observed_by=self.config.gateway_id,
                direction="internal",
                payload_json=json.dumps({"state": "startup"}, sort_keys=True),
                status="recorded",
            )
        )
        self.storage.enqueue_outbound_event(
            OutboundQueueRecord(
                msg_id=f"{startup_msg_id}-queued",
                topic=f"{self.config.mqtt.topic_prefix}/site-{self.config.site_code}/gateway/{self.config.gateway_id}/state",
                payload_json=json.dumps(self.health.as_dict(), sort_keys=True),
                status="pending",
            )
        )
        self.health = self.health.with_states(
            process_state=ProcessState.READY,
            radio_state=self._determine_radio_state(),
            broker_state=self._determine_broker_state(),
            queue_depth=self.storage.queue_depth(),
        )

        LOGGER.info("Gateway skeleton prepared for %s", self.config.gateway_id)
        return {
            "gateway_id": self.config.gateway_id,
            "site_code": self.config.site_code,
            "state_dir": str(self.config.state_dir),
            "queue_db_path": str(self.config.queue_db_path),
            "policy_file": (
                str(self.config.policy_file) if self.config.policy_file else "not configured"
            ),
            "storage_tables": tables,
            "mqtt_topic_prefix": self.config.mqtt.topic_prefix,
            "health": self.health.as_dict(),
            "next_steps": (
                "Implement MQTT adapter wiring, serial radio integration, and live replay "
                "state transitions."
            ),
        }
