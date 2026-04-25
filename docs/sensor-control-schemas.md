# Sensor And Control Schemas

## Purpose

This document defines compact payload-body schemas for the most important machine-processed message classes in Phase 1:

- `position_report`
- `sensor_report`
- `control_request`
- `control_result`
- `alert_event`

These schemas sit **inside** the shared envelope defined in [Application Protocol](application-protocol.md). This document does not redefine common fields such as `msg_id`, `source`, `captured_at`, or `target`.

## Design Goals

- keep payload bodies compact and predictable
- preserve the minimum fields needed for the identified use cases
- avoid verbose free-form text for machine decisions
- make gateway validation and downstream storage straightforward

## Shared Payload Design Rules

### Rule 1: Keep Field Names Stable

Field names should be stable even if later encodings move to shorter coded representations.

### Rule 2: No Repeated Static Metadata

Do not repeat installation metadata, long descriptions, or static thresholds in routine payloads.

### Rule 3: Machine-Relevant First

Payloads should prioritize the fields needed for:

- routing
- actuation
- alert evaluation
- storage
- operator interpretation

### Rule 4: Human Text Is Optional

Free-form text may exist for operator context, but core machine behavior must not depend on text parsing.

## `position_report`

### Purpose

Represents a current location observation for a node that should be rendered on a map or stored for movement history.

### Payload Schema

```json
{
  "lat": 39.76841,
  "lon": -86.15804,
  "alt_m": 218,
  "precision_m": 12,
  "speed_mps": 0.7,
  "heading_deg": 183,
  "battery_pct": 78
}
```

### Field Notes

- `lat`: required decimal latitude
- `lon`: required decimal longitude
- `alt_m`: optional altitude in meters
- `precision_m`: optional estimated horizontal precision
- `speed_mps`: optional speed in meters per second
- `heading_deg`: optional course over ground
- `battery_pct`: optional battery percentage

### Required Fields

- `lat`
- `lon`

### Compactness Guidance

- omit speed or heading when unknown or irrelevant
- omit altitude when it does not materially help the use case
- do not include human-readable place names in the payload

## `sensor_report`

### Purpose

Represents one capture cycle from a sensor node or sensor group.

### Payload Schema

```json
{
  "sensor_set": "basement_sump_monitor",
  "metrics": [
    {
      "name": "temperature_c",
      "value": 3.2,
      "unit": "C"
    },
    {
      "name": "humidity_pct",
      "value": 68.4,
      "unit": "%"
    },
    {
      "name": "water_level_cm",
      "value": 27.8,
      "unit": "cm"
    }
  ]
}
```

### Field Notes

- `sensor_set`: required compact logical name for the source sensor block
- `metrics`: required non-empty list of metric records

Each metric record contains:

- `name`: required canonical metric identifier
- `value`: required numeric value
- `unit`: required compact unit string

### Required Fields

- `sensor_set`
- `metrics`

### Compactness Guidance

- keep `sensor_set` short and stable
- use canonical metric identifiers rather than prose labels
- prefer one multi-metric report per sample time when the metric set belongs together
- do not include thresholds, descriptions, or site context in the payload

### Candidate Canonical Metric Names

- `temperature_c`
- `humidity_pct`
- `water_level_cm`
- `pump_state`
- `battery_pct`
- `rssi_dbm`

## `control_request`

### Purpose

Represents an explicit actuation or test request that requires policy enforcement and usually acknowledgement.

### Payload Schema

```json
{
  "action": "pump_test",
  "params": {
    "duration_s": 10
  }
}
```

### Field Notes

- `action`: required compact action identifier
- `params`: optional object containing only the parameters needed for the action

### Required Fields

- `action`

### Compactness Guidance

- action names should be short and enumerated
- parameter names should be stable and minimal
- do not embed explanatory prose in routine requests

### Candidate Actions

- `pump_test`
- `relay_on`
- `relay_off`
- `status_ping`
- `ack_only`

## `control_result`

### Purpose

Represents the outcome of a `control_request`.

### Payload Schema

```json
{
  "status": "ok",
  "action": "pump_test",
  "params": {
    "duration_s": 10
  },
  "observed": {
    "pump_state": "cycled"
  }
}
```

### Field Notes

- `status`: required enumerated result
- `action`: required echoed action name
- `params`: optional normalized request parameters
- `observed`: optional compact observed outcome values

### Candidate Status Values

- `ok`
- `rejected`
- `timeout`
- `failed`
- `expired`

### Required Fields

- `status`
- `action`

### Compactness Guidance

- prefer enumerated result states over prose
- include only the minimum observed state needed to prove the outcome

## `alert_event`

### Purpose

Represents a generated alert derived from telemetry or control outcomes.

### Payload Schema

```json
{
  "related_source": "bs01",
  "metric": "water_level_cm",
  "observed_value": 31.4,
  "threshold": 30.0,
  "severity": "warning",
  "action": "notify_operator"
}
```

### Required Fields

- `related_source`
- `metric`
- `observed_value`
- `threshold`
- `severity`

### Candidate Severity Values

- `info`
- `warning`
- `critical`

## Validation Expectations

### `position_report`

Reject if:

- `lat` or `lon` is missing
- coordinates are outside legal range

### `sensor_report`

Reject if:

- `sensor_set` is missing
- `metrics` is empty
- any metric lacks `name`, `value`, or `unit`

### `control_request`

Reject if:

- `action` is missing
- the envelope lacks a directed target
- the action is not allowlisted for the sender or target

### `control_result`

Reject if:

- `status` or `action` is missing
- the event lacks correlation to a known request when correlation is required

### `alert_event`

Reject if:

- threshold context is incomplete
- the event cannot identify the related source

## Storage Implications

These schemas imply normalized storage patterns.

### Position Tables

- one current-state record by node
- one append-only history record by observation

### Sensor Tables

- one event row per `sensor_report`
- optional metric child rows if later analytics need metric-level indexing

### Control Tables

- one request row
- one result row linked by correlation id

### Alert Tables

- one alert event row per generated alert
- optional incident-state table if alerts later gain acknowledgement and lifecycle management

## Concerns

- metric names can sprawl if they are not centrally governed
- enumerated action names need version control and compatibility rules
- position payloads can still become too frequent even if individually small
- control results need to be concise without becoming too ambiguous for operators

## Missed Requirements

- a canonical registry for metric names and units
- a canonical registry for control action names and parameter sets
- whether enumerated values remain strings or move to compact numeric codes later
- whether `sensor_report` should support multiple sensor sets in one payload or always remain single-set

## Open Decisions

- whether `sensor_set` is sufficient, or whether a separate `sensor_model` field will be needed later
- whether `observed` in `control_result` should remain free-form object or be action-specific
- whether alert payloads need incident ids once acknowledgement workflow exists

## Exit Criteria For This Task

This task is complete when the design defines:

- compact payload bodies for the main machine message classes
- required and optional fields for each body
- validation rules for each message class
- storage implications for later persistence work
