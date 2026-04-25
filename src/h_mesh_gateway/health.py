from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum


class ProcessState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    STOPPED = "stopped"
    ERROR = "error"


class RadioState(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    MISSING = "missing"
    UNHEALTHY = "unhealthy"


class BrokerState(StrEnum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(slots=True)
class GatewayHealthSnapshot:
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
        return replace(
            self,
            process_state=process_state or self.process_state,
            radio_state=radio_state or self.radio_state,
            broker_state=broker_state or self.broker_state,
            queue_depth=self.queue_depth if queue_depth is None else queue_depth,
            observed_at=datetime.now(timezone.utc),
        )

    def as_dict(self) -> dict[str, object]:
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
    return GatewayHealthSnapshot(
        gateway_id=gateway_id,
        site=site,
        process_state=ProcessState.STARTING,
        radio_state=RadioState.UNKNOWN,
        broker_state=BrokerState.UNKNOWN,
        queue_depth=0,
        observed_at=datetime.now(timezone.utc),
    )
