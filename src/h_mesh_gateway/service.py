from __future__ import annotations

from collections.abc import Callable
import logging
import json
from datetime import timedelta

from h_mesh_gateway.interfaces import BrokerAdapter, RadioAdapter
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
    DedupeRecord,
    parse_iso_timestamp,
    utc_now_iso,
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

    def _initialize_storage(self) -> list[str]:
        self._ensure_runtime_paths()
        return self.storage.initialize()

    def _resolve_event_topic(self, payload: dict[str, object]) -> str:
        source_site = str(payload["source_site"])
        channel = str(payload["channel"])
        return f"{self.config.mqtt.topic_prefix}/site-{source_site}/{channel}/up"

    def _health_topic(self) -> str:
        return (
            f"{self.config.mqtt.topic_prefix}/site-{self.config.site_code}/gateway/"
            f"{self.config.gateway_id}/state"
        )

    def _resolve_expiry(self, payload: dict[str, object]) -> str:
        expires_at = payload.get("expires_at")
        if isinstance(expires_at, str) and expires_at:
            return expires_at
        captured_at = payload.get("captured_at")
        if isinstance(captured_at, str) and captured_at:
            return (parse_iso_timestamp(captured_at) + timedelta(days=1)).isoformat()
        return (parse_iso_timestamp(utc_now_iso()) + timedelta(days=1)).isoformat()

    def publish_health_snapshot(
        self,
        broker: BrokerAdapter,
        *,
        broker_state: BrokerState | None = None,
        radio_state: RadioState | None = None,
        queue_depth: int | None = None,
    ) -> dict[str, object]:
        self._initialize_storage()
        self.health = self.health.with_states(
            process_state=ProcessState.READY,
            broker_state=broker_state or BrokerState.CONNECTED,
            radio_state=radio_state or self._determine_radio_state(),
            queue_depth=self.storage.queue_depth() if queue_depth is None else queue_depth,
        )
        payload_json = json.dumps(self.health.as_dict(), sort_keys=True)
        topic = self._health_topic()
        broker.publish(topic, payload_json)
        self.storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id=self.config.gateway_id,
                kind="gateway_state_published",
                detail=f"Published health snapshot to {topic}",
            )
        )
        return {
            "status": "published",
            "topic": topic,
            "health": self.health.as_dict(),
        }

    def maybe_publish_health_snapshot(
        self,
        broker: BrokerAdapter,
        *,
        broker_state: BrokerState | None = None,
        radio_state: RadioState | None = None,
        queue_depth: int | None = None,
    ) -> dict[str, object] | None:
        try:
            return self.publish_health_snapshot(
                broker,
                broker_state=broker_state,
                radio_state=radio_state,
                queue_depth=queue_depth,
            )
        except RuntimeError as exc:
            self.storage.record_gateway_observation(
                GatewayObservationRecord(
                    gateway_id=self.config.gateway_id,
                    kind="gateway_state_publish_failed",
                    detail=f"Failed to publish health snapshot: {exc}",
                )
            )
            return None

    def run_skeleton(self) -> dict[str, object]:
        tables = self._initialize_storage()
        startup_stamp = self.health.observed_at.strftime("%Y%m%dT%H%M%S%fZ")
        self.storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id=self.config.gateway_id,
                kind="service_initialized",
                detail="Gateway skeleton initialized storage",
            )
        )
        startup_msg_id = f"{self.config.gateway_id}-startup-{startup_stamp}"
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
        queued_health = self.health.with_states(
            process_state=ProcessState.READY,
            radio_state=self._determine_radio_state(),
            broker_state=self._determine_broker_state(),
            queue_depth=self.storage.queue_depth() + 1,
        )
        self.health = queued_health
        self.storage.enqueue_outbound_event(
            OutboundQueueRecord(
                msg_id=f"{startup_msg_id}-queued",
                topic=f"{self.config.mqtt.topic_prefix}/site-{self.config.site_code}/gateway/{self.config.gateway_id}/state",
                payload_json=json.dumps(queued_health.as_dict(), sort_keys=True),
                status="pending",
            )
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

    def simulate_rf_to_mqtt(
        self,
        payload: dict[str, object],
        broker: BrokerAdapter,
    ) -> dict[str, object]:
        tables = self._initialize_storage()
        msg_id = str(payload["msg_id"])
        if self.storage.has_seen_message(msg_id):
            self.storage.record_gateway_observation(
                GatewayObservationRecord(
                    gateway_id=self.config.gateway_id,
                    kind="duplicate_suppressed",
                    detail=f"RF message {msg_id} already seen",
                    related_msg_id=msg_id,
                )
            )
            return {
                "status": "duplicate",
                "msg_id": msg_id,
                "topic": self._resolve_event_topic(payload),
                "storage_tables": tables,
            }

        payload_json = json.dumps(payload, sort_keys=True)
        self.storage.record_message_event(
            MessageEventRecord(
                msg_id=msg_id,
                msg_type=str(payload["msg_type"]),
                source=str(payload["source"]),
                source_site=str(payload["source_site"]),
                target=str(payload.get("target")) if payload.get("target") is not None else None,
                target_scope=(
                    str(payload.get("target_scope"))
                    if payload.get("target_scope") is not None
                    else None
                ),
                channel=str(payload["channel"]),
                captured_at=str(payload["captured_at"]),
                observed_by=self.config.gateway_id,
                direction="rf_in",
                payload_json=payload_json,
                status="recorded",
            )
        )
        topic = self._resolve_event_topic(payload)
        self.storage.enqueue_outbound_event(
            OutboundQueueRecord(
                msg_id=msg_id,
                topic=topic,
                payload_json=payload_json,
                expires_at=self._resolve_expiry(payload),
            )
        )
        self.storage.remember_seen_message(
            DedupeRecord(
                msg_id=msg_id,
                source_path=f"rf:{self.config.gateway_id}",
                expires_at=self._resolve_expiry(payload),
            )
        )
        pre_publish_health = self.maybe_publish_health_snapshot(
            broker,
            broker_state=BrokerState.CONNECTED,
            radio_state=self._determine_radio_state(),
            queue_depth=self.storage.queue_depth(),
        )
        try:
            broker.publish(topic, payload_json)
        except RuntimeError as exc:
            self.storage.mark_outbound_attempt(msg_id, status="retrying")
            self.storage.record_gateway_observation(
                GatewayObservationRecord(
                    gateway_id=self.config.gateway_id,
                    kind="publish_failed",
                    detail=f"Failed to publish {msg_id} to {topic}: {exc}",
                    related_msg_id=msg_id,
                )
            )
            return {
                "status": "queued",
                "msg_id": msg_id,
                "topic": topic,
                "queue_depth": self.storage.queue_depth(),
                "broker_state": broker.current_state().value,
                "storage_tables": tables,
            }

        self.storage.mark_outbound_published(msg_id)
        health_report = self.maybe_publish_health_snapshot(
            broker,
            broker_state=BrokerState.CONNECTED,
            radio_state=self._determine_radio_state(),
            queue_depth=self.storage.queue_depth(),
        ) or {"topic": self._health_topic()}
        self.storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id=self.config.gateway_id,
                kind="publish_succeeded",
                detail=f"Published {msg_id} to {topic}",
                related_msg_id=msg_id,
            )
        )
        return {
            "status": "published",
            "msg_id": msg_id,
            "topic": topic,
            "queue_depth": self.storage.queue_depth(),
            "broker_state": broker.current_state().value,
            "health_topic": health_report["topic"],
            "storage_tables": tables,
        }

    def simulate_mqtt_to_radio(
        self,
        *,
        topic: str,
        broker: BrokerAdapter,
        radio: RadioAdapter,
        timeout_seconds: float = 10.0,
        on_broker_ready: Callable[[], None] | None = None,
    ) -> dict[str, object]:
        tables = self._initialize_storage()
        if radio.current_state() != RadioState.HEALTHY:
            health_report = self.maybe_publish_health_snapshot(
                broker,
                broker_state=broker.current_state(),
                radio_state=radio.current_state(),
                queue_depth=self.storage.queue_depth(),
            ) or {"topic": self._health_topic()}
            self.storage.record_gateway_observation(
                GatewayObservationRecord(
                    gateway_id=self.config.gateway_id,
                    kind="rf_emit_blocked",
                    detail=f"Radio unavailable before MQTT consume on {topic}",
                )
            )
            return {
                "status": "radio_unavailable",
                "topic": topic,
                "radio_state": radio.current_state().value,
                "health_topic": health_report["topic"],
                "storage_tables": tables,
            }
        message = broker.receive_one(topic, timeout_seconds, on_ready=on_broker_ready)
        if message is None:
            self.storage.record_gateway_observation(
                GatewayObservationRecord(
                    gateway_id=self.config.gateway_id,
                    kind="mqtt_receive_timeout",
                    detail=f"No MQTT message received on {topic}",
                )
            )
            return {
                "status": "timeout",
                "topic": topic,
                "radio_state": radio.current_state().value,
                "storage_tables": tables,
            }

        payload = json.loads(message.payload_json)
        msg_id = str(payload["msg_id"])
        if self.storage.has_seen_message(msg_id):
            self.storage.record_gateway_observation(
                GatewayObservationRecord(
                    gateway_id=self.config.gateway_id,
                    kind="duplicate_suppressed",
                    detail=f"MQTT message {msg_id} already seen",
                    related_msg_id=msg_id,
                )
            )
            return {
                "status": "duplicate",
                "msg_id": msg_id,
                "topic": topic,
                "radio_state": radio.current_state().value,
                "storage_tables": tables,
            }

        self.storage.record_message_event(
            MessageEventRecord(
                msg_id=msg_id,
                msg_type=str(payload["msg_type"]),
                source=str(payload["source"]),
                source_site=str(payload["source_site"]),
                target=str(payload.get("target")) if payload.get("target") is not None else None,
                target_scope=(
                    str(payload.get("target_scope"))
                    if payload.get("target_scope") is not None
                    else None
                ),
                channel=str(payload["channel"]),
                captured_at=str(payload["captured_at"]),
                observed_by=self.config.gateway_id,
                direction="mqtt_in",
                payload_json=message.payload_json,
                status="recorded",
            )
        )
        emission = radio.emit(message.payload_json)
        self.storage.remember_seen_message(
            DedupeRecord(
                msg_id=msg_id,
                source_path=f"mqtt:{self.config.gateway_id}",
                expires_at=self._resolve_expiry(payload),
            )
        )
        health_report = self.maybe_publish_health_snapshot(
            broker,
            broker_state=BrokerState.CONNECTED,
            radio_state=radio.current_state(),
            queue_depth=self.storage.queue_depth(),
        ) or {"topic": self._health_topic()}
        self.storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id=self.config.gateway_id,
                kind="rf_emit_succeeded",
                detail=f"Emitted {msg_id} to {emission.path}",
                related_msg_id=msg_id,
            )
        )
        return {
            "status": "emitted",
            "msg_id": msg_id,
            "topic": topic,
            "radio_state": radio.current_state().value,
            "radio_output_path": str(emission.path),
            "health_topic": health_report["topic"],
            "storage_tables": tables,
        }
