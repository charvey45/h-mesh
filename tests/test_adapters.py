from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from h_mesh_gateway.adapters import PahoMqttBrokerAdapter


class PahoAdapterTests(unittest.TestCase):
    def test_publish_wraps_connect_errors_as_runtime_error(self) -> None:
        class FakeClient:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def connect(self, *_args, **_kwargs) -> None:
                raise OSError("connection refused")

            def username_pw_set(self, *_args, **_kwargs) -> None:
                return

            def tls_set(self) -> None:
                return

        fake_mqtt = types.SimpleNamespace(
            CallbackAPIVersion=types.SimpleNamespace(VERSION2="v2"),
            MQTT_ERR_SUCCESS=0,
            Client=lambda *_args, **_kwargs: FakeClient(),
        )

        adapter = PahoMqttBrokerAdapter(
            host="127.0.0.1",
            port=1883,
            client_id="ag01-test",
        )

        with patch.object(PahoMqttBrokerAdapter, "_load_mqtt", return_value=fake_mqtt):
            with self.assertRaisesRegex(RuntimeError, "MQTT connect failed"):
                adapter.publish("mesh/v1/site-a/sensor/up", "{}")
