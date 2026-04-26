from __future__ import annotations

import json
import os
import sys
import time
from threading import Event

import paho.mqtt.client as mqtt


BROKER_HOST = os.environ.get("BROKER_HOST", "mqtt-broker")
BROKER_PORT = int(os.environ.get("BROKER_PORT", "1883"))
ROLE = os.environ.get("ROLE", "subscriber")
TOPIC = os.environ.get("TOPIC", "mesh/v1/site-a/ops/up")
START_DELAY_SECONDS = float(os.environ.get("START_DELAY_SECONDS", "0"))
TIMEOUT_SECONDS = float(os.environ.get("TIMEOUT_SECONDS", "20"))
MESSAGE_ID = os.environ.get("MESSAGE_ID", "ops-test-0001")
TARGET_SCOPE = os.environ.get("TARGET_SCOPE", "site-b-ops")


def build_fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "msg_type": "ops_broadcast",
        "msg_id": MESSAGE_ID,
        "source": "ag01",
        "source_site": "a",
        "target": None,
        "target_scope": TARGET_SCOPE,
        "channel": "ops",
        "observed_by": "ag01",
        "captured_at": "2026-04-26T10:00:00-04:00",
        "expires_at": "2026-04-26T10:15:00-04:00",
        "correlation_id": None,
        "priority": "normal",
        "flags": [],
        "payload": {
            "text": "integration harness message"
        },
    }


def run_publisher() -> int:
    time.sleep(START_DELAY_SECONDS)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ag01-publisher")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_start()
    payload = json.dumps(build_fixture(), sort_keys=True)
    result = client.publish(TOPIC, payload=payload, qos=1, retain=False)
    result.wait_for_publish()
    client.loop_stop()
    client.disconnect()

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"publish failed rc={result.rc}", file=sys.stderr)
        return 1

    print(payload)
    return 0


def run_subscriber() -> int:
    done = Event()
    outcome: dict[str, object] = {"status": "timeout"}

    def on_connect(
        client: mqtt.Client,
        _userdata: object,
        _flags: dict[str, object],
        reason_code: mqtt.ReasonCode,
        _properties: object | None = None,
    ) -> None:
        if int(reason_code) != 0:
            outcome["status"] = "connect_failed"
            outcome["reason_code"] = int(reason_code)
            done.set()
            return
        client.subscribe(TOPIC, qos=1)

    def on_message(
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        payload = json.loads(message.payload.decode("utf-8"))
        outcome["status"] = "received"
        outcome["payload"] = payload
        done.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bg02-subscriber")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_start()
    done.wait(TIMEOUT_SECONDS)
    client.loop_stop()
    client.disconnect()

    if outcome["status"] != "received":
        print(json.dumps(outcome, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(outcome["payload"], sort_keys=True))
    return 0


def main() -> int:
    if ROLE == "publisher":
        return run_publisher()
    if ROLE == "subscriber":
        return run_subscriber()
    print(f"unknown ROLE={ROLE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
