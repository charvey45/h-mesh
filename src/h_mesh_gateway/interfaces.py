from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from h_mesh_gateway.health import BrokerState, RadioState


@dataclass(slots=True)
class AdapterStatus:
    state: str
    detail: str


class BrokerAdapter(Protocol):
    def current_state(self) -> BrokerState:
        ...


class RadioAdapter(Protocol):
    def current_state(self) -> RadioState:
        ...
