"""Synthetic sensor publisher used by the management demo and lab workflows."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone

from h_mesh_gateway.interfaces import BrokerAdapter
from h_mesh_gateway.service import GatewayService


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def build_clock_sensor_payload(
    *,
    source: str,
    site_code: str,
    sensor_set: str = "clock",
    captured_at: datetime | None = None,
) -> dict[str, object]:
    """Build a normalized synthetic sensor_report payload."""
    observed_at = captured_at or utc_now()
    iso_timestamp = observed_at.isoformat()
    minute_of_day = (observed_at.hour * 60) + observed_at.minute

    return {
        "msg_type": "sensor_report",
        "msg_id": f"sensor-{source}-{observed_at.strftime('%Y%m%dT%H%M%S%fZ')}",
        "source": source,
        "source_site": site_code,
        "channel": "sensor",
        "captured_at": iso_timestamp,
        "payload": {
            "sensor_set": sensor_set,
            "metrics": [
                {
                    "name": "epoch_s",
                    "value": int(observed_at.timestamp()),
                    "unit": "s",
                },
                {
                    "name": "minute_of_day",
                    "value": minute_of_day,
                    "unit": "m",
                },
                {
                    "name": "second_of_minute",
                    "value": observed_at.second,
                    "unit": "s",
                },
            ],
        },
    }


def run_clock_sensor(
    *,
    service: GatewayService,
    broker: BrokerAdapter,
    source: str,
    sensor_set: str = "clock",
    count: int = 1,
    interval_seconds: float = 5.0,
    forever: bool = False,
    now_provider: Callable[[], datetime] = utc_now,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Publish one or more synthetic sensor reports through the gateway service."""
    if not forever and count < 1:
        raise ValueError("count must be at least 1 when forever is false")

    reports: list[dict[str, object]] = []
    emitted_count = 0

    while forever or emitted_count < count:
        payload = build_clock_sensor_payload(
            source=source,
            site_code=service.config.site_code,
            sensor_set=sensor_set,
            captured_at=now_provider(),
        )
        result = service.simulate_rf_to_mqtt(payload, broker)
        reports.append(
            {
                "msg_id": str(payload["msg_id"]),
                "captured_at": str(payload["captured_at"]),
                "status": str(result["status"]),
                "topic": str(result["topic"]),
            }
        )
        emitted_count += 1
        if forever or emitted_count < count:
            sleep_fn(interval_seconds)

    return {
        "status": "complete",
        "source": source,
        "sensor_set": sensor_set,
        "emitted_count": emitted_count,
        "reports": reports,
    }
