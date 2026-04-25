# Telemetry And Alerting

## Purpose

This document defines the storage and alerting requirements for sensor nodes that report telemetry through the multi-site Meshtastic gateway architecture.

The immediate driver is the `bs01` basement sump monitor use case: humidity, temperature, and water level readings must be stored for later analysis and evaluated against thresholds that can raise operator alerts.

## Scope

This document applies to machine-readable `sensor_report` events produced by sensor nodes and normalized by the gateway service.

It covers:

- raw telemetry event storage
- metric-level storage for query and alert evaluation
- threshold configuration
- alert evaluation behavior
- alert event and lifecycle storage
- stale or missing sensor behavior
- evaluator outage behavior
- retention and audit requirements

It does not define the low-level RF payload encoding beyond the existing schema in [Sensor And Control Schemas](sensor-control-schemas.md).

## Core Decisions

### Decision 1: Store Raw Events And Parsed Metrics

The system should preserve the original normalized `sensor_report` envelope and also store parsed metric rows.

Raw event storage supports replay, audit, and later parser changes. Parsed metric storage supports threshold evaluation, charts, and time-range queries without repeatedly parsing JSON payloads.

### Decision 2: Evaluate Alerts Outside The RF Node

Sensor nodes should report measurements. Gateway-side or cloud-side services should own threshold evaluation.

This keeps RF nodes simple and avoids pushing policy, alert routing, and operator lifecycle rules into devices that are harder to update and inspect.

### Decision 3: Alert State Is Separate From Telemetry

A telemetry record is an observation. An alert is a derived state or event created from one or more observations.

The design must not treat every threshold-crossing measurement as a new unrelated incident without suppression or lifecycle rules.

## Ingestion Flow

1. a sensor node emits a compact `sensor_report`
2. the gateway receives and normalizes the event
3. the gateway validates the shared envelope and payload schema
4. the gateway writes the full envelope to `sensor_events`
5. the gateway writes one row per metric to `sensor_metric_readings`
6. the gateway publishes the normalized event to MQTT when bridge policy allows
7. an alert evaluator reads the persisted readings or subscribes to the MQTT sensor topic
8. threshold matches create or update alert records
9. operator-facing alert notifications are emitted only after alert lifecycle rules are applied

The preferred implementation is to evaluate alerts from persisted records, not only from transient MQTT messages. This allows recovery after evaluator downtime.

## Candidate Sensor Event

```json
{
  "schema_version": 1,
  "msg_type": "sensor_report",
  "msg_id": "sensor-20260425-0201",
  "source": "bs01",
  "source_site": "b",
  "target": null,
  "target_scope": null,
  "channel": "sensor",
  "observed_by": "bg02",
  "captured_at": "2026-04-25T14:25:00-04:00",
  "expires_at": null,
  "correlation_id": null,
  "priority": "normal",
  "flags": [],
  "payload": {
    "sensor_set": "basement_sump_monitor",
    "metrics": [
      {
        "name": "humidity_pct",
        "value": 68.4,
        "unit": "%"
      },
      {
        "name": "temperature_c",
        "value": 3.2,
        "unit": "C"
      },
      {
        "name": "water_level_cm",
        "value": 27.8,
        "unit": "cm"
      }
    ]
  }
}
```

## Storage Model

### `sensor_events`

Stores the full normalized sensor event as observed by the gateway.

Candidate fields:

- `event_id`
- `msg_id`
- `source`
- `source_site`
- `sensor_set`
- `captured_at`
- `observed_by`
- `payload_json`
- `ingest_status`
- `stored_at`

Requirements:

- `msg_id` must be unique within the event store
- duplicate replay of the same event must not create duplicate raw event rows
- malformed events may be stored with `ingest_status` if policy allows forensic retention
- payload JSON should be preserved losslessly

### `sensor_metric_readings`

Stores one row per metric value extracted from a `sensor_report`.

Candidate fields:

- `reading_id`
- `event_id`
- `source`
- `source_site`
- `sensor_set`
- `metric`
- `value`
- `unit`
- `captured_at`
- `observed_by`
- `stored_at`

Requirements:

- metric rows must reference the raw `sensor_events` row
- values must be numeric for threshold evaluation unless the metric registry explicitly allows enumerated states
- metric names and units must match the canonical metric registry
- time-range queries must be supported by `source`, `metric`, and `captured_at`

### `sensor_metric_registry`

Defines allowed metric names, units, and basic interpretation rules.

Candidate fields:

- `metric`
- `canonical_unit`
- `value_type`
- `description`
- `min_reasonable_value`
- `max_reasonable_value`
- `active`

Initial candidate metrics:

- `temperature_c`
- `humidity_pct`
- `water_level_cm`
- `pump_state`
- `battery_pct`
- `rssi_dbm`

Requirements:

- new metric names should be added deliberately, not invented ad hoc by each node
- unit normalization must happen before threshold evaluation
- clearly impossible values should be rejected or quarantined before alert evaluation

### `alert_thresholds`

Defines threshold rules for a sensor, sensor set, metric, or site.

Candidate fields:

- `threshold_id`
- `scope_type`
- `scope_id`
- `metric`
- `condition`
- `threshold_value`
- `severity`
- `clear_condition`
- `clear_value`
- `hold_down_seconds`
- `repeat_after_seconds`
- `enabled`
- `version`
- `updated_by`
- `updated_at`

Candidate `scope_type` values:

- `device`
- `sensor_set`
- `site`
- `global`

Candidate `condition` values:

- `>`
- `>=`
- `<`
- `<=`
- `==`
- `!=`

Requirements:

- threshold changes must be versioned for auditability
- a disabled threshold must not generate new alerts
- threshold matching must record which threshold version created the alert
- thresholds must define clear behavior or explicitly rely on manual acknowledgement

### `alert_events`

Stores individual threshold evaluation outcomes and notification-worthy events.

Candidate fields:

- `alert_event_id`
- `alert_id`
- `event_id`
- `threshold_id`
- `threshold_version`
- `source`
- `source_site`
- `metric`
- `observed_value`
- `unit`
- `severity`
- `state`
- `captured_at`
- `created_at`

Candidate `state` values:

- `raised`
- `repeated`
- `cleared`
- `suppressed`
- `acknowledged`

### `alert_state`

Stores the current lifecycle state of an active or recently cleared alert.

Candidate fields:

- `alert_id`
- `source`
- `metric`
- `threshold_id`
- `current_state`
- `severity`
- `first_raised_at`
- `last_observed_at`
- `last_notified_at`
- `acknowledged_at`
- `acknowledged_by`
- `cleared_at`
- `repeat_count`

Requirements:

- repeated bad readings should update alert state instead of creating unlimited new incidents
- alert state must preserve the first raised time and most recent observation time
- acknowledgement must not erase the underlying telemetry or alert event history
- clear behavior must be deterministic and auditable

## Threshold Evaluation

### Normal Evaluation

For each metric reading:

1. load enabled thresholds that apply by device, sensor set, site, or global scope
2. normalize the reading into the threshold's expected unit
3. compare the value against the threshold condition
4. create or update alert state if the threshold is breached
5. create a clear event if the clear condition is met for an active alert
6. apply suppression and repeat rules before notifying operators

### Example Thresholds

```json
[
  {
    "threshold_id": "thr-bs01-water-warning",
    "scope_type": "device",
    "scope_id": "bs01",
    "metric": "water_level_cm",
    "condition": ">=",
    "threshold_value": 30.0,
    "severity": "warning",
    "clear_condition": "<",
    "clear_value": 26.0,
    "hold_down_seconds": 300,
    "repeat_after_seconds": 1800,
    "enabled": true,
    "version": 1
  },
  {
    "threshold_id": "thr-bs01-temp-freeze",
    "scope_type": "device",
    "scope_id": "bs01",
    "metric": "temperature_c",
    "condition": "<=",
    "threshold_value": 0.0,
    "severity": "critical",
    "clear_condition": ">",
    "clear_value": 2.0,
    "hold_down_seconds": 0,
    "repeat_after_seconds": 900,
    "enabled": true,
    "version": 1
  }
]
```

### Hysteresis And Hold-Down

Thresholds should support separate raise and clear conditions. This avoids alert flapping when a sensor hovers near the threshold.

Example:

- raise water alert at `>= 30.0 cm`
- clear water alert only after `< 26.0 cm`

`hold_down_seconds` should allow the evaluator to require a condition to remain true for a defined interval before raising an alert.

### Suppression And Repeat

The evaluator must prevent alert storms.

Requirements:

- active alerts should not notify on every matching reading
- `repeat_after_seconds` controls reminder notifications for still-active alerts
- suppressed events should remain visible in `alert_events`
- suppression must not hide state transitions such as `raised` to `cleared`

## Alert Notification Flow

Operator-facing notifications should be generated from alert lifecycle events, not raw threshold comparisons.

Candidate alert envelope:

```json
{
  "schema_version": 1,
  "msg_type": "alert_event",
  "msg_id": "alert-20260425-0301",
  "source": "cg-alert-evaluator",
  "source_site": "c",
  "target": null,
  "target_scope": "site-b-ops",
  "channel": "ops",
  "observed_by": "cg-alert-evaluator",
  "captured_at": "2026-04-25T15:02:00-04:00",
  "expires_at": "2026-04-25T15:32:00-04:00",
  "correlation_id": "alert-bs01-water-level",
  "priority": "high",
  "flags": [
    "alert"
  ],
  "payload": {
    "related_source": "bs01",
    "metric": "water_level_cm",
    "observed_value": 31.4,
    "threshold": 30.0,
    "severity": "warning",
    "action": "notify_operator"
  }
}
```

Requirements:

- human-readable alert text may be generated for `ops`, but machine-readable fields remain authoritative
- alert notifications should include enough context for an operator to act without querying a dashboard first
- alert notifications should have expiry so stale alerts are not replayed as fresh emergencies
- external notification channels may be added later without changing telemetry ingest

## Stale Or Missing Data

Missing sensor data can be as important as bad sensor data.

Each monitored sensor should define freshness expectations.

Candidate fields:

- `source`
- `sensor_set`
- `expected_interval_seconds`
- `stale_after_seconds`
- `missing_after_seconds`
- `severity_when_missing`
- `enabled`

Requirements:

- stale status must be visible separately from threshold breaches
- missing-data alerts should not fire during planned maintenance windows
- gateway radio-down and broker-down states should be considered when explaining stale sensors
- stale detection should use gateway observation time when source clocks are untrusted

## Evaluator Outage Behavior

The alert evaluator may be unavailable while gateways continue ingesting telemetry.

Requirements:

- gateways must continue storing `sensor_events` and `sensor_metric_readings`
- evaluator recovery must process unread persisted readings from a known checkpoint
- evaluator checkpoints must be durable
- backfill evaluation must honor alert expiry and stale notification policy
- evaluator health must be observable through gateway or cloud health reporting

Candidate evaluator checkpoint fields:

- `consumer_id`
- `last_event_id`
- `last_captured_at`
- `updated_at`
- `status`

## Placement Options

### Gateway-Local Evaluation

Good for lab work and local resilience.

Tradeoffs:

- continues to work when WAN is down
- keeps decisions close to the sensor
- requires threshold configuration on each gateway
- complicates cross-site alert consistency

### Central Evaluation

Good for fleet-wide dashboards and unified alert policy.

Tradeoffs:

- single place for threshold configuration
- easier central reporting and notification integration
- depends on broker and central service availability
- requires backfill from persisted telemetry after outages

### Phase 1 Recommendation

Use gateway-local persistence for raw telemetry and allow either gateway-local or central alert evaluation.

For the lab, a single evaluator can run near the MQTT broker or on one Pi. The storage model should not assume this placement is permanent.

## Retention Requirements

Telemetry retention should be configurable by data class.

Minimum policy fields:

- raw event retention window
- parsed metric retention window
- alert event retention window
- alert state retention after clear
- archive or export path

Recommended Phase 1 defaults:

- raw `sensor_events`: retain at least 30 days
- parsed `sensor_metric_readings`: retain at least 180 days
- `alert_events`: retain at least 1 year
- cleared `alert_state`: retain at least 1 year after clear

These are starting points for lab and design work, not final operational policy.

## Privacy And Configuration

Telemetry can expose site behavior, equipment state, and building conditions.

Requirements:

- live thresholds and exact site placement details belong in private configuration
- public examples may use realistic but non-sensitive values
- operator contact routes must stay outside versioned docs
- sensor calibration records should be private if they reveal exact installation details

## Failure Modes

The design must explicitly handle:

- duplicate sensor events after replay
- sensor clock drift
- gateway clock drift
- malformed metric payloads
- unit mismatch
- impossible values
- noisy readings near thresholds
- evaluator downtime
- MQTT outage
- gateway radio outage
- storage full on the Pi

## Candidate Acceptance Tests

### Test 1: Raw And Parsed Storage

Feed one valid `sensor_report` for `bs01`.

Expected:

- one `sensor_events` row is written
- three `sensor_metric_readings` rows are written
- parsed rows reference the raw event id

### Test 2: Duplicate Replay

Replay the same `msg_id` twice.

Expected:

- no duplicate raw event row is created
- no duplicate metric rows are created
- a duplicate observation is logged

### Test 3: Threshold Raise

Feed `water_level_cm` below threshold, then above threshold.

Expected:

- no alert below threshold
- alert state becomes `raised` once the threshold is breached
- one notification-worthy alert event is produced

### Test 4: Hysteresis Clear

Feed water readings of `31.4`, `29.8`, then `25.5`.

Expected:

- the alert remains active at `29.8` if clear value is `< 26.0`
- the alert clears at `25.5`
- the clear event is recorded

### Test 5: Alert Suppression

Feed repeated bad readings while an alert is active.

Expected:

- alert state updates `last_observed_at`
- notifications are suppressed until `repeat_after_seconds` is reached
- suppressed evaluations remain queryable

### Test 6: Evaluator Recovery

Stop the evaluator while telemetry continues to ingest, then restart it.

Expected:

- stored readings are processed from the last durable checkpoint
- alerts are evaluated without skipping stored events
- stale or expired alert notifications are not emitted as fresh events

### Test 7: Missing Sensor

Stop receiving events from `bs01` beyond `missing_after_seconds`.

Expected:

- sensor state becomes missing or stale
- optional missing-data alert is generated according to policy
- gateway and broker health context is available for diagnosis

## Open Decisions

- whether Phase 1 alert evaluation runs on each gateway, centrally, or both
- exact retention windows for lab versus production deployments
- exact metric registry governance process
- whether alert acknowledgement starts as local state or requires a central operator identity model
- how maintenance windows suppress stale and missing-data alerts

## Exit Criteria

This task is complete when the design defines:

- raw sensor event storage
- parsed metric storage
- threshold configuration
- alert evaluation rules
- alert lifecycle storage
- stale or missing sensor behavior
- evaluator outage behavior
- acceptance tests for storage and alert paths
