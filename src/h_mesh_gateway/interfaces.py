from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from h_mesh_gateway.health import BrokerState, RadioState


@dataclass(slots=True)
class AdapterStatus:
    # Reserved for future richer adapter status surfaces. It remains simple for now.
    state: str
    detail: str


@dataclass(slots=True)
class BrokerMessage:
    # This is the minimal broker payload shape the service layer cares about.
    topic: str
    payload_json: str


@dataclass(slots=True)
class RadioEmission:
    # The radio side returns both where the payload went and what was emitted.
    path: Path
    payload_json: str


class BrokerAdapter(Protocol):
    # The BrokerAdapter protocol defines exactly what the service expects from any MQTT boundary,
    # whether it is a real broker client or an in-memory test double.
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
    # The RadioAdapter protocol keeps the service blind to whether "radio" means a file,
    # an in-memory queue, or a future serial-connected device.
    def current_state(self) -> RadioState:
        ...

    def emit(self, payload_json: str) -> RadioEmission:
        ...
