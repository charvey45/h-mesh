# Management Dashboard

## Purpose

The management dashboard provides a local operator view of gateway health, queue backlog, MQTT-path failures, and recent logs without requiring a separate cloud observability stack.

Phase 1 keeps the management surface close to the gateway state directory:

- queue depth comes from the local SQLite queue database
- broker and radio health come from persisted gateway health snapshots
- recent failures come from `gateway_observations`
- logs come from local gateway log files

## Phase 1 Metrics

The dashboard currently exposes:

- total queue depth across discovered gateway databases
- queue status counts such as `pending`, `retrying`, and `published`
- latest gateway health per gateway id
- queue depth sparkline history per gateway
- recent sensor traffic observed by the gateway
- recent broker-path and radio-path failures
- recent local gateway logs

MQTT visibility in Phase 1 is gateway-centric. The dashboard shows what the gateway observed:

- publish failures
- health publish failures
- MQTT receive timeouts
- RF emit blocked conditions

This is enough to answer practical operator questions such as:

- are messages backing up
- did the broker path fail recently
- is a gateway healthy but unable to reach radio or MQTT
- what happened most recently in the local logs

## Runtime Model

The dashboard scans a shared state directory for:

- `*.sqlite3` gateway databases
- `*.log` gateway log files

This lets one dashboard cover multiple gateways as long as they write into the same persistent host path or mounted volume.

## Docker Runtime

Use the provided compose file:

```powershell
docker compose -f docker-compose.management.yml up --build -d
```

The default local lab mapping uses:

- host path `./state`
- container path `/data/state`

For Pi deployment, map a persistent host path such as `/srv/h-mesh/state` instead of a repo-relative directory.

For a runnable local demo with synthetic sensor traffic, use:

```powershell
docker compose -f docker-compose.management-demo.yml up --build -d
```

That demo starts a broker, the dashboard, and a clock sensor publisher that continuously emits `sensor_report` messages as source `as01`.

## HTTP Surface

The dashboard serves:

- `/` for the HTML operator view
- `/api/summary` for aggregated JSON metrics
- `/api/logs` for recent log content
- `/healthz` for a basic process health probe

## Current Limits

Phase 1 intentionally avoids a second datastore or metrics system. The dashboard is a read-only window into local gateway state.

Current limits:

- no log rotation yet
- no S3 archival yet
- no direct broker-internal metrics such as socket count or retained message count
- failure counters are local gateway observations, not broker-native telemetry
- sensor traffic visibility is based on stored `message_events`, not a dedicated timeseries store

## Next Evolution

Later enhancements can add:

- log retention and rotation
- S3 archival or shipping
- time-windowed failure metrics
- broker-native telemetry if a dedicated broker exporter is introduced

The forward path for S3-based archival is defined in [Log Archival Requirements](log-archival-requirements.md).
