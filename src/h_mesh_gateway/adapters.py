from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from h_mesh_gateway.health import BrokerState, RadioState
from h_mesh_gateway.interfaces import BrokerAdapter, BrokerMessage, RadioAdapter, RadioEmission


class PahoMqttBrokerAdapter(BrokerAdapter):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        client_id: str,
        username: str = "",
        password: str = "",
        tls_enabled: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.tls_enabled = tls_enabled
        self._state = BrokerState.UNKNOWN

    def current_state(self) -> BrokerState:
        return self._state

    def publish(self, topic: str, payload_json: str) -> None:
        mqtt = self._load_mqtt()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        if self.username:
            client.username_pw_set(self.username, self.password)
        if self.tls_enabled:
            client.tls_set()
        client.connect(self.host, self.port, keepalive=30)
        client.loop_start()
        result = client.publish(topic, payload=payload_json, qos=1, retain=False)
        result.wait_for_publish()
        client.loop_stop()
        client.disconnect()
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self._state = BrokerState.DISCONNECTED
            raise RuntimeError(f"MQTT publish failed rc={result.rc}")
        self._state = BrokerState.CONNECTED

    def receive_one(self, topic: str, timeout_seconds: float) -> BrokerMessage | None:
        messages = self.receive_many(topic, max_messages=1, timeout_seconds=timeout_seconds)
        if not messages:
            return None
        return messages[0]

    def receive_many(
        self,
        topic: str,
        max_messages: int,
        timeout_seconds: float,
    ) -> list[BrokerMessage]:
        mqtt = self._load_mqtt()
        received: list[BrokerMessage] = []
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        if self.username:
            client.username_pw_set(self.username, self.password)
        if self.tls_enabled:
            client.tls_set()

        def on_connect(
            connected_client,
            _userdata,
            _flags,
            reason_code,
            _properties=None,
        ) -> None:
            if int(reason_code) != 0:
                self._state = BrokerState.DISCONNECTED
                return
            connected_client.subscribe(topic, qos=1)
            self._state = BrokerState.CONNECTED

        def on_message(_client, _userdata, message) -> None:
            received.append(
                BrokerMessage(
                    topic=str(message.topic),
                    payload_json=message.payload.decode("utf-8"),
                )
            )

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(self.host, self.port, keepalive=30)
        client.loop_start()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if len(received) >= max_messages:
                break
            time.sleep(0.1)
        client.loop_stop()
        client.disconnect()
        return received

    @staticmethod
    def _load_mqtt():
        try:
            import paho.mqtt.client as mqtt
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "paho-mqtt is required for MQTT adapter usage. Install project dependencies "
                "or use the Docker harness."
            ) from exc
        return mqtt


@dataclass(slots=True)
class InMemoryBrokerAdapter(BrokerAdapter):
    published_messages: list[BrokerMessage] = field(default_factory=list)
    _state: BrokerState = BrokerState.CONNECTED

    def current_state(self) -> BrokerState:
        return self._state

    def publish(self, topic: str, payload_json: str) -> None:
        self.published_messages.append(BrokerMessage(topic=topic, payload_json=payload_json))

    def receive_one(self, topic: str, timeout_seconds: float) -> BrokerMessage | None:
        messages = self.receive_many(topic, max_messages=1, timeout_seconds=timeout_seconds)
        if not messages:
            return None
        return messages[0]

    def receive_many(
        self,
        topic: str,
        max_messages: int,
        timeout_seconds: float,
    ) -> list[BrokerMessage]:
        del timeout_seconds
        matches: list[BrokerMessage] = []
        kept: list[BrokerMessage] = []
        for message in self.published_messages:
            if message.topic == topic and len(matches) < max_messages:
                matches.append(message)
            else:
                kept.append(message)
        self.published_messages = kept
        return matches


@dataclass(slots=True)
class FileRadioAdapter(RadioAdapter):
    output_path: Path
    state: RadioState = RadioState.HEALTHY

    def current_state(self) -> RadioState:
        return self.state

    def emit(self, payload_json: str) -> RadioEmission:
        if self.state != RadioState.HEALTHY:
            raise RuntimeError(f"Radio is not healthy: {self.state.value}")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(payload_json, encoding="utf-8")
        return RadioEmission(path=self.output_path, payload_json=payload_json)


@dataclass(slots=True)
class InMemoryRadioAdapter(RadioAdapter):
    state: RadioState = RadioState.HEALTHY
    emissions: deque[str] = field(default_factory=deque)

    def current_state(self) -> RadioState:
        return self.state

    def emit(self, payload_json: str) -> RadioEmission:
        if self.state != RadioState.HEALTHY:
            raise RuntimeError(f"Radio is not healthy: {self.state.value}")
        self.emissions.append(payload_json)
        return RadioEmission(path=Path("<memory>"), payload_json=payload_json)

    def pop_emission(self) -> dict[str, object]:
        return json.loads(self.emissions.popleft())
