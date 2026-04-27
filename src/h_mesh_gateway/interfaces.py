"""Protocol definitions for broker and radio adapter boundaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from h_mesh_gateway.health import BrokerState, RadioState


@dataclass(slots=True)
class AdapterStatus:
    """Reserved status shape for future richer adapter reporting."""

    state: str
    detail: str


@dataclass(slots=True)
class BrokerMessage:
    """Minimal MQTT message shape used by the service layer."""

    topic: str
    payload_json: str


@dataclass(slots=True)
class RadioEmission:
    """Result returned by radio emit operations."""

    path: Path
    payload_json: str


class BrokerAdapter(Protocol):
    """Behavior required from any MQTT-facing adapter implementation."""

    def current_state(self) -> BrokerState:
        ...

    def publish(self, topic: str, payload_json: str) -> None:
        ...

    def receive_one(
        self,
        topic: str,
        timeout_seconds: float,
        on_ready: Callable[[], None] | None = None,
    ) -> BrokerMessage | None:
        ...

    def receive_many(
        self,
        topic: str,
        max_messages: int,
        timeout_seconds: float,
        on_ready: Callable[[], None] | None = None,
    ) -> list[BrokerMessage]:
        ...


class RadioAdapter(Protocol):
    """Behavior required from any radio-facing adapter implementation."""

    def current_state(self) -> RadioState:
        ...

    def emit(self, payload_json: str) -> RadioEmission:
        ...
