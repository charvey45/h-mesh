from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from h_mesh_gateway.health import BrokerState, RadioState


@dataclass(slots=True)
class AdapterStatus:
    state: str
    detail: str


@dataclass(slots=True)
class BrokerMessage:
    topic: str
    payload_json: str


@dataclass(slots=True)
class RadioEmission:
    path: Path
    payload_json: str


class BrokerAdapter(Protocol):
    def current_state(self) -> BrokerState:
        ...

    def publish(self, topic: str, payload_json: str) -> None:
        ...

    def receive_one(self, topic: str, timeout_seconds: float) -> BrokerMessage | None:
        ...

    def receive_many(
        self,
        topic: str,
        max_messages: int,
        timeout_seconds: float,
    ) -> list[BrokerMessage]:
        ...


class RadioAdapter(Protocol):
    def current_state(self) -> RadioState:
        ...

    def emit(self, payload_json: str) -> RadioEmission:
        ...
