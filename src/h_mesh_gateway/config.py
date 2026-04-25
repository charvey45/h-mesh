from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


GATEWAY_ID_RE = re.compile(r"^[a-z]g[0-9a-f]{2}$")


@dataclass(slots=True)
class MqttRuntimeConfig:
    host: str
    port: int
    username: str
    password: str
    tls_enabled: bool
    topic_prefix: str

    def as_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "tls_enabled": self.tls_enabled,
            "topic_prefix": self.topic_prefix,
        }


@dataclass(slots=True)
class GatewayRuntimeConfig:
    env_file: Path
    site_code: str
    gateway_id: str
    device_role: str
    log_level: str
    state_dir: Path
    queue_db_path: Path
    policy_file: Path | None
    radio_enabled: bool
    serial_port: str | None
    mqtt: MqttRuntimeConfig

    def as_dict(self) -> dict[str, object]:
        return {
            "env_file": str(self.env_file),
            "site_code": self.site_code,
            "gateway_id": self.gateway_id,
            "device_role": self.device_role,
            "log_level": self.log_level,
            "state_dir": str(self.state_dir),
            "queue_db_path": str(self.queue_db_path),
            "policy_file": str(self.policy_file) if self.policy_file else None,
            "radio_enabled": self.radio_enabled,
            "serial_port": self.serial_port,
            "mqtt": self.mqtt.as_dict(),
        }


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise ValueError(f"Env file does not exist: {path}")

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError(f"Invalid env line in {path}: {line}")
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_bool(value: str, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field_name} must be a boolean-like value")


def require_value(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ValueError(f"Missing required config value: {key}")
    return value


def resolve_path(raw_path: str | None, base_dir: Path) -> Path | None:
    if not raw_path:
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def validate_gateway_identity(site_code: str, gateway_id: str, device_role: str) -> None:
    if len(site_code) != 1 or not site_code.islower() or not site_code.isalpha():
        raise ValueError("SITE_CODE must be a single lowercase letter")
    if device_role != "gateway":
        raise ValueError("DEVICE_ROLE must be 'gateway' for the gateway service")
    if not GATEWAY_ID_RE.match(gateway_id):
        raise ValueError("Gateway id must match [site]g[hex][hex], for example ag01")
    if gateway_id[0] != site_code:
        raise ValueError("SITE_CODE must match the first character of the gateway id")


def load_runtime_config(env_path: Path) -> GatewayRuntimeConfig:
    env_path = env_path.resolve()
    values = parse_env_file(env_path)
    base_dir = Path(os.getcwd()).resolve()

    site_code = require_value(values, "SITE_CODE")
    gateway_id = values.get("GATEWAY_ID", values.get("DEVICE_CODE", "")).strip()
    device_role = values.get("DEVICE_ROLE", "").strip() or "gateway"
    validate_gateway_identity(site_code, gateway_id, device_role)

    state_dir = resolve_path(values.get("STATE_DIR", "./state"), base_dir)
    if state_dir is None:
        raise ValueError("STATE_DIR must resolve to a valid path")

    queue_db_path = resolve_path(
        values.get("QUEUE_DB_PATH", str(state_dir / "queue.sqlite3")), base_dir
    )
    if queue_db_path is None:
        raise ValueError("QUEUE_DB_PATH must resolve to a valid path")

    mqtt = MqttRuntimeConfig(
        host=values.get("MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=int(values.get("MQTT_PORT", "1883")),
        username=values.get("MQTT_USERNAME", "").strip(),
        password=values.get("MQTT_PASSWORD", "").strip(),
        tls_enabled=parse_bool(values.get("MQTT_TLS_ENABLED", "false"), "MQTT_TLS_ENABLED"),
        topic_prefix=values.get("MQTT_TOPIC_PREFIX", "mesh/v1").strip() or "mesh/v1",
    )

    return GatewayRuntimeConfig(
        env_file=env_path,
        site_code=site_code,
        gateway_id=gateway_id,
        device_role=device_role,
        log_level=values.get("LOG_LEVEL", "INFO").strip() or "INFO",
        state_dir=state_dir,
        queue_db_path=queue_db_path,
        policy_file=resolve_path(values.get("POLICY_FILE"), base_dir),
        radio_enabled=parse_bool(values.get("RADIO_ENABLED", "false"), "RADIO_ENABLED"),
        serial_port=values.get("SERIAL_PORT", "").strip() or None,
        mqtt=mqtt,
    )
