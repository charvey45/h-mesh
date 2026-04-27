"""Health-state model for the gateway scaffold."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum


class ProcessState(StrEnum):
    """Lifecycle states for the local gateway process."""

    STARTING = "starting"
    READY = "ready"
    STOPPED = "stopped"
    ERROR = "error"


class RadioState(StrEnum):
    """Health states for the local RF boundary."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    MISSING = "missing"
    UNHEALTHY = "unhealthy"


class BrokerState(StrEnum):
    """Health states for the MQTT broker boundary."""

    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(slots=True)
class GatewayHealthSnapshot:
    """Normalized health document shared by MQTT publication and local storage."""

    gateway_id: str
    site: str
    process_state: ProcessState
    radio_state: RadioState
    broker_state: BrokerState
    queue_depth: int
    observed_at: datetime

    def with_states(
        self,
        *,
        process_state: ProcessState | None = None,
        radio_state: RadioState | None = None,
        broker_state: BrokerState | None = None,
        queue_depth: int | None = None,
    ) -> "GatewayHealthSnapshot":
        """Return a new snapshot with selected state fields updated."""
        return replace(
            self,
            process_state=process_state or self.process_state,
            radio_state=radio_state or self.radio_state,
            broker_state=broker_state or self.broker_state,
            queue_depth=self.queue_depth if queue_depth is None else queue_depth,
            observed_at=datetime.now(timezone.utc),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize the health snapshot into a JSON-ready dictionary."""
        return {
            "gateway_id": self.gateway_id,
            "site": self.site,
            "process_state": self.process_state.value,
            "radio_state": self.radio_state.value,
            "broker_state": self.broker_state.value,
            "queue_depth": self.queue_depth,
            "observed_at": self.observed_at.isoformat(),
        }


def initial_health_snapshot(gateway_id: str, site: str) -> GatewayHealthSnapshot:
    """Build the initial health state for a just-started gateway process."""
    return GatewayHealthSnapshot(
        gateway_id=gateway_id,
        site=site,
        process_state=ProcessState.STARTING,
        radio_state=RadioState.UNKNOWN,
        broker_state=BrokerState.UNKNOWN,
        queue_depth=0,
        observed_at=datetime.now(timezone.utc),
    )
