# Requirements Use Cases

## Purpose

This document explores realistic message flows across the current architecture so protocol, storage, alerting, and test requirements can be defined from concrete examples instead of abstractions.

## Scenario Conventions

- Device codes are shown in lowercase to match the naming standard.
- Human-written examples may refer to uppercase forms such as `AR01`; those map to `ar01` in structured examples.
- One requested node id, `RG04`, does not match the current `[site][type][hex][hex]` naming rule because `r` is not a defined site code. It is preserved here as `rg04` as a placeholder that must be resolved before implementation.

## Architectural Assumptions

- Site A and Site B each have a Pi-assisted gateway connected to a Meshtastic radio.
- Inter-site traffic crosses a private MQTT backbone.
- `ops` is used for human communication.
- `sensor` is used for telemetry and position reporting.
- Direct human-to-human dialogs should avoid unnecessary shared-channel noise when possible.
- Sensor and position events should be persisted for later analysis.

## Use Case 1: Broadcast Check-In Request

### Narrative

`ar01` sends a site-to-site broadcast requesting a status update from operators at Site B.

Message:

> What's going on down there. Please check in.

### User-Level Intent

- sender: `ar01`
- audience: Site B operators
- class: human `ops` traffic
- urgency: normal
- delivery goal: broadcast to a remote site without requiring individual addressing

### Candidate Structured Event

```json
{
  "msg_type": "ops_broadcast",
  "msg_id": "ops-20260424-0001",
  "source": "ar01",
  "target_group": "site-b-ops",
  "channel": "ops",
  "text": "What's going on down there. Please check in.",
  "priority": "normal",
  "created_at": "2026-04-24T14:15:00-04:00"
}
```

### Flow Through The Architecture

1. `ar01` sends the message over the local Site A mesh.
2. Site A gateway receives and classifies it as inter-site `ops` traffic.
3. Site A gateway logs the event and publishes it to the MQTT broker.
4. Site B gateway subscribes, validates, and injects it into the Site B mesh.
5. Site B radios receive the broadcast according to local reachability and channel membership.

### Derived Requirements

- support site-scoped broadcast groups
- preserve sender identity across the bridge
- avoid duplicate rebroadcast loops
- log the original message id and bridge decisions on both gateways

## Use Case 2: Broadcast Response With Operator Context

### Narrative

`br02` responds to `ar01` with who the operator is and what they are doing.

Message:

> br02 here. Chris is in the basement checking the sump pump and water level.

### Candidate Structured Event

```json
{
  "msg_type": "ops_reply",
  "msg_id": "ops-20260424-0002",
  "reply_to": "ops-20260424-0001",
  "source": "br02",
  "target": "ar01",
  "channel": "ops",
  "text": "br02 here. Chris is in the basement checking the sump pump and water level.",
  "created_at": "2026-04-24T14:16:10-04:00"
}
```

### Derived Requirements

- support reply correlation with `reply_to`
- keep human identity in message text or optional metadata without requiring a separate directory service
- preserve direct response routing from Site B back to Site A

## Use Case 3: Direct Operator Dialog

### Narrative

After the check-in, `ar01` and `br02` continue a direct conversation that should not clutter the shared broadcast path.

Example dialog:

- `ar01` to `br02`: "How high is the water now?"
- `br02` to `ar01`: "About two inches below the alarm float. Pump cycled once in the last hour."

### Candidate Structured Events

```json
{
  "msg_type": "ops_direct",
  "msg_id": "ops-20260424-0003",
  "source": "ar01",
  "target": "br02",
  "channel": "ops",
  "text": "How high is the water now?",
  "conversation_id": "conv-ar01-br02-20260424",
  "created_at": "2026-04-24T14:17:00-04:00"
}
```

```json
{
  "msg_type": "ops_direct",
  "msg_id": "ops-20260424-0004",
  "source": "br02",
  "target": "ar01",
  "channel": "ops",
  "text": "About two inches below the alarm float. Pump cycled once in the last hour.",
  "conversation_id": "conv-ar01-br02-20260424",
  "created_at": "2026-04-24T14:17:25-04:00"
}
```

### Derived Requirements

- support direct addressing without forcing shared broadcast behavior
- track dialog correlation with a `conversation_id`
- keep direct-message delivery distinct from shared-channel broadcasts
- confirm how Meshtastic direct messages map onto gateway logging and MQTT topics

## Use Case 4: Position Reporting And Movement History

### Narrative

`br03` and `rg04` report their locations every few minutes according to Meshtastic position settings. Operators at Site A want to view current positions on a node map. Historical positions should also be stored for later movement analysis.

### Candidate Position Event

```json
{
  "msg_type": "position_report",
  "msg_id": "pos-20260424-0101",
  "source": "br03",
  "channel": "sensor",
  "position": {
    "lat": 39.76841,
    "lon": -86.15804,
    "alt_m": 218,
    "precision_m": 12
  },
  "speed_mps": 0.7,
  "heading_deg": 183,
  "battery_pct": 78,
  "captured_at": "2026-04-24T14:20:00-04:00"
}
```

```json
{
  "msg_type": "position_report",
  "msg_id": "pos-20260424-0102",
  "source": "rg04",
  "channel": "sensor",
  "position": {
    "lat": 39.76802,
    "lon": -86.15755,
    "alt_m": 217,
    "precision_m": 8
  },
  "speed_mps": 1.2,
  "heading_deg": 270,
  "battery_pct": 62,
  "captured_at": "2026-04-24T14:20:00-04:00"
}
```

### Data Persistence Need

Position reports should be written to a history store, not only exposed as last-known map state.

Candidate storage fields:

- event id
- source device
- captured timestamp
- latitude
- longitude
- altitude
- precision
- speed
- heading
- battery level
- gateway that observed or relayed the event

### Derived Requirements

- support current-position display and historical position retention
- define retention policy for movement history
- support time-range queries by device
- resolve the invalid `rg04` device code before implementation

## Use Case 5: Basement Environmental And Water Monitoring

### Narrative

`bs01` measures basement humidity, temperature, and sump pit water level at Site B. The readings must be stored for later analysis and evaluated against alert thresholds.

### Candidate Sensor Event

```json
{
  "msg_type": "sensor_report",
  "msg_id": "sensor-20260424-0201",
  "source": "bs01",
  "channel": "sensor",
  "sensor_set": "basement_sump_monitor",
  "captured_at": "2026-04-24T14:25:00-04:00",
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
```

### Candidate Alert Threshold Records

```json
[
  {
    "sensor_id": "bs01",
    "metric": "water_level_cm",
    "condition": ">=",
    "threshold": 30.0,
    "severity": "warning",
    "action": "notify_operator"
  },
  {
    "sensor_id": "bs01",
    "metric": "temperature_c",
    "condition": "<=",
    "threshold": 0.0,
    "severity": "critical",
    "action": "notify_operator"
  }
]
```

### Candidate Alert Event

```json
{
  "msg_type": "alert_event",
  "msg_id": "alert-20260424-0301",
  "source": "alert-module",
  "related_source": "bs01",
  "metric": "water_level_cm",
  "observed_value": 31.4,
  "threshold": 30.0,
  "severity": "warning",
  "created_at": "2026-04-24T15:02:00-04:00"
}
```

### Derived Requirements

- store raw sensor events for later analysis
- support threshold definitions in a database or configuration store
- evaluate alerts outside the RF node on a gateway or cloud-side module
- support alert escalation rules by severity and metric
- keep the sensor payload compact while still supporting multiple metrics in one report

## Cross-Cutting Requirements

- each event needs a stable message id for logging, replay, and de-duplication
- site-to-site traffic should preserve source identity and event timestamps
- direct operator messages, position reports, and sensor telemetry should not all share the same handling path
- current state and historical state are separate needs and should be stored separately where useful
- alert generation should be derived from persisted telemetry, not only from transient in-flight packets

## Candidate Test Seeds

### Test 1: Broadcast Check-In Relay

- inject an `ops_broadcast` from `ar01`
- verify it is logged on Site A, published once to MQTT, received on Site B, and emitted on Site B RF

### Test 2: Direct Reply Path

- inject a direct `ops_reply` from `br02` to `ar01`
- verify only the addressed remote path is used for bridge delivery

### Test 3: Position History Persistence

- feed a timed series of `position_report` events for `br03`
- verify current map state updates and historical records remain queryable by time range

### Test 4: Threshold Alert Generation

- feed `sensor_report` events for `bs01` with rising `water_level_cm`
- verify no alert below threshold and correct alert generation once the threshold is crossed

### Test 5: Radio-Absent Gateway Behavior

- deliver inbound MQTT traffic to a gateway with no attached USB radio
- verify the gateway does not silently consume messages it cannot radiate locally

## Open Questions

- should direct operator dialogs stay entirely in native Meshtastic semantics or be normalized into a gateway conversation model
- should position history live on the gateway, in a central database, or in both
- what retention periods are required for movement history and sensor history
- should alert thresholds be managed centrally or per site
- how should invalid or legacy device identifiers such as `rg04` be normalized before implementation
