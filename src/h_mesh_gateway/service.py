from __future__ import annotations

import logging
from pathlib import Path

from h_mesh_gateway.config import GatewayRuntimeConfig
from h_mesh_gateway.health import (
    BrokerState,
    ProcessState,
    RadioState,
    initial_health_snapshot,
)


LOGGER = logging.getLogger(__name__)


class GatewayService:
    def __init__(self, config: GatewayRuntimeConfig) -> None:
        self.config = config
        self.health = initial_health_snapshot(config.gateway_id, config.site_code)

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
        self.health = self.health.with_states(
            process_state=ProcessState.READY,
            radio_state=self._determine_radio_state(),
            broker_state=self._determine_broker_state(),
            queue_depth=0,
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
            "mqtt_topic_prefix": self.config.mqtt.topic_prefix,
            "health": self.health.as_dict(),
            "next_steps": (
                "Implement SQLite schema initialization, MQTT adapter wiring, and serial "
                "radio integration."
            ),
        }
