# Requirements Use Cases

## Purpose

This document explores realistic message flows across the current architecture so protocol, storage, alerting, and test requirements can be defined from concrete examples instead of abstractions.

The goal is not to lock in a final protocol. The goal is to model realistic end-to-end behavior with enough fidelity that requirements, constraints, and test cases can be derived from something concrete.

## Scenario Conventions

- Device codes are shown in lowercase to match the naming standard.
- Human-written examples may refer to uppercase forms such as `AR01`; those map to `ar01` in structured examples.
- The original prompt included `RG04`; that value does not match the `[site][type][hex][hex]` naming rule because `r` is not a defined site code. This document normalizes that example to `br04`, a Site B radio.

## Architectural Assumptions

- Site A and Site B each have a Pi-assisted gateway connected to a Meshtastic radio.
- Inter-site traffic crosses a private [MQTT](https://mqtt.org/) backbone.
- `ops` is used for human communication.
- `sensor` is used for telemetry and position reporting.
- Direct human-to-human dialogs should avoid unnecessary shared-channel noise when possible.
- Sensor and position events should be persisted for later analysis.
- Alert evaluation runs on a gateway-side or cloud-side service, not on the RF node itself.

## Candidate Data Flow Vocabulary

These examples use a consistent candidate data model so the same event can be traced across RF, gateway, broker, and storage boundaries.

### Candidate Topic Layout

These are example topics, not final decisions:

- `mesh/v1/site-a/ops/up`
- `mesh/v1/site-b/ops/up`
- `mesh/v1/site-a/sensor/up`
- `mesh/v1/site-b/sensor/up`
- `mesh/v1/site-a/control/up`
- `mesh/v1/site-b/control/up`
- `mesh/v1/site-a/gateway/ag01/state`
- `mesh/v1/site-b/gateway/bg02/state`
- `mesh/v1/alerts/up`

### Candidate Shared Envelope

```json
{
  "schema_version": 1,
  "msg_type": "example",
  "msg_id": "example-20260424-0001",
  "source": "ag01",
  "source_site": "a",
  "channel": "ops",
  "observed_by": "ag01",
  "captured_at": "2026-04-24T14:15:00-04:00",
  "payload": {}
}
```

### Candidate Stores

- `message_events`: all bridged human and machine events
- `gateway_observations`: gateway health, bridge actions, replay actions
- `positions_current`: last-known position by node
- `positions_history`: historical movement records
- `sensor_events`: raw telemetry records
- `alert_thresholds`: threshold definitions
- `alert_events`: generated alerts and their lifecycle

## Use Case 1: Broadcast Check-In Request

### Narrative

`ar01` sends a site-to-site broadcast requesting a status update from operators at Site B.

Message:

> What's going on down there. Please check in.

### Intent

- sender: `ar01`
- audience: Site B operators
- class: human `ops` traffic
- urgency: normal
- delivery goal: broadcast to a remote site without requiring individual addressing

### Realistic Data Flow

#### Step 1: Operator Input On Site A

`ar01` composes the message in a Meshtastic client and sends it on the `ops` channel.

Candidate client-visible message:

```text
What's going on down there. Please check in.
```

#### Step 2: Local RF Observation At Site A

`ag01` hears the packet over the local LoRa mesh and passes it to the Pi over USB serial.

Candidate normalized gateway event:

```json
{
  "schema_version": 1,
  "msg_type": "ops_broadcast",
  "msg_id": "ops-20260424-0001",
  "source": "ar01",
  "source_site": "a",
  "target_scope": "site-b-ops",
  "channel": "ops",
  "observed_by": "ag01",
  "captured_at": "2026-04-24T14:15:00-04:00",
  "payload": {
    "text": "What's going on down there. Please check in.",
    "priority": "normal"
  }
}
```

#### Step 3: Site A Gateway Processing

`ag01` Pi:

- validates that the event is bridge-eligible
- writes a record to `message_events`
- writes a bridge action record to `gateway_observations`
- publishes to MQTT

Candidate MQTT publish:

- topic: `mesh/v1/site-a/ops/up`
- qos: `1`
- retain: `false`

Candidate payload:

```json
{
  "schema_version": 1,
  "msg_type": "ops_broadcast",
  "msg_id": "ops-20260424-0001",
  "source": "ar01",
  "source_site": "a",
  "target_scope": "site-b-ops",
  "channel": "ops",
  "observed_by": "ag01",
  "captured_at": "2026-04-24T14:15:00-04:00",
  "payload": {
    "text": "What's going on down there. Please check in.",
    "priority": "normal"
  }
}
```

#### Step 4: Site B Gateway Consumption

`bg02` Pi receives the MQTT event and:

- validates schema version and target scope
- checks `msg_id` against recent history for de-duplication
- writes the event to `message_events`
- asks the local USB radio to emit the message on Site B `ops`

#### Step 5: RF Delivery On Site B

Site B radios on the `ops` channel receive the broadcast according to local reachability and node state.

### Deep Analysis

#### Requirements

- support a site-targeted broadcast scope
- preserve original sender identity and text
- support de-duplication with a stable `msg_id`
- log bridge decisions at both the source and destination gateways
- support replay or retry behavior if the remote gateway is temporarily unavailable

#### Concerns

- nearby colocated sites could hear each other directly and make the bridge path look healthy when it is not
- broadcast messages can create noise if remote site targeting is too broad
- repeated relay of the same event must not loop between gateways

#### Missed Requirements

- message expiry for stale broadcasts
- acknowledgement model for inter-site broadcast delivery
- optional priority or escalation model for urgent broadcasts

## Use Case 2: Broadcast Response With Operator Context

### Narrative

`br02` responds to `ar01` with who the operator is and what they are doing.

Message:

> br02 here. Chris is in the basement checking the sump pump and water level.

### Realistic Data Flow

#### Step 1: Site B Operator Response

`br02` sends a response from Site B using the shared `ops` path.

#### Step 2: Site B Gateway Normalization

```json
{
  "schema_version": 1,
  "msg_type": "ops_reply",
  "msg_id": "ops-20260424-0002",
  "reply_to": "ops-20260424-0001",
  "source": "br02",
  "source_site": "b",
  "target": "ar01",
  "channel": "ops",
  "observed_by": "bg02",
  "captured_at": "2026-04-24T14:16:10-04:00",
  "payload": {
    "text": "br02 here. Chris is in the basement checking the sump pump and water level."
  }
}
```

#### Step 3: MQTT Publish From Site B

- topic: `mesh/v1/site-b/ops/up`
- qos: `1`
- retain: `false`

#### Step 4: Site A Gateway Handling

`ag01` Pi:

- verifies `reply_to` references a known or recent message id
- records the event in `message_events`
- emits the message toward `ar01` over local RF

#### Step 5: User Experience On Site A

`ar01` sees the reply from `br02` and has enough context to decide whether to continue in broadcast mode or move to direct messaging.

### Deep Analysis

#### Requirements

- support reply correlation through `reply_to`
- preserve operator context without requiring a separate directory lookup
- support direct routing to a target node even when the previous message was a broadcast

#### Concerns

- operator identity in free text is useful but hard to query later
- if the user who sent the original request is offline, the response still needs a delivery policy
- replies may expose information broadly if they are accidentally sent as broadcasts rather than direct messages

#### Missed Requirements

- optional metadata fields for operator name, role, or activity code
- delivery receipt semantics for targeted human responses
- policy for how long `reply_to` references stay valid

## Use Case 3: Direct Operator Dialog

### Narrative

After the check-in, `ar01` and `br02` continue a direct conversation that should not clutter the shared broadcast path.

For Phase 1, "direct" means the gateway preserves a single explicit `target` and does not intentionally rebroadcast the message to a site-wide scope. It does not mean the message is invisible to every radio transport participant, gateway log, broker administrator, or storage operator.

Example dialog:

- `ar01` to `br02`: "How high is the water now?"
- `br02` to `ar01`: "About two inches below the alarm float. Pump cycled once in the last hour."

### Realistic Data Flow

#### Step 1: Dialog Starts

The user experience should switch from broadcast-style messaging to targeted dialog semantics.

Candidate gateway-normalized event from `ar01`:

```json
{
  "schema_version": 1,
  "msg_type": "ops_direct",
  "msg_id": "ops-20260424-0003",
  "source": "ar01",
  "source_site": "a",
  "target": "br02",
  "channel": "ops",
  "observed_by": "ag01",
  "captured_at": "2026-04-24T14:17:00-04:00",
  "payload": {
    "text": "How high is the water now?",
    "conversation_id": "conv-ar01-br02-20260424"
  }
}
```

Candidate response from `br02`:

```json
{
  "schema_version": 1,
  "msg_type": "ops_direct",
  "msg_id": "ops-20260424-0004",
  "source": "br02",
  "source_site": "b",
  "target": "ar01",
  "channel": "ops",
  "observed_by": "bg02",
  "captured_at": "2026-04-24T14:17:25-04:00",
  "payload": {
    "text": "About two inches below the alarm float. Pump cycled once in the last hour.",
    "conversation_id": "conv-ar01-br02-20260424"
  }
}
```

#### Step 2: MQTT Relay

The dialog events still traverse the same broker, but they should remain explicitly targeted.

- topic from Site A: `mesh/v1/site-a/ops/up`
- topic from Site B: `mesh/v1/site-b/ops/up`

#### Step 3: Destination Gateway Filtering

The receiving gateway:

- checks that the target belongs to its site or is reachable via its local mesh
- does not reframe the message as a broadcast
- logs the conversation metadata

#### Step 4: Privacy And Logging Treatment

The gateway may store the direct dialog in `message_events` for audit, replay, and troubleshooting. Any user-facing client should avoid presenting this as end-to-end private unless the implementation later proves a stronger encryption and logging model.

### Deep Analysis

#### Requirements

- support direct addressing across sites
- maintain `conversation_id` or equivalent correlation
- avoid shared-channel noise by preserving targeted message semantics
- make privacy and logging behavior explicit to operators
- allow a dialog to continue even if started from a broadcast exchange

#### Concerns

- native Meshtastic direct-message semantics may not map one-to-one to gateway conversation semantics
- conversation state can become a hidden coupling if the target node roams or changes site
- operator expectations for "private" may not match actual RF visibility or logging behavior

#### Missed Requirements

- whether conversation history should be queryable in the same way as broadcasts
- rules for conversation expiry and archival

## Use Case 4: Position Reporting And Movement History

### Narrative

`br03` and `br04` report their locations every few minutes according to Meshtastic position settings. Operators at Site A want to view current positions on a node map. Historical positions should also be stored for later movement analysis.

### Realistic Data Flow

#### Step 1: Periodic Position Capture

Every few minutes, the reporting nodes emit position updates on the `sensor` path.

Candidate position event for `br03`:

```json
{
  "schema_version": 1,
  "msg_type": "position_report",
  "msg_id": "pos-20260424-0101",
  "source": "br03",
  "source_site": "b",
  "channel": "sensor",
  "observed_by": "bg02",
  "captured_at": "2026-04-24T14:20:00-04:00",
  "payload": {
    "lat": 39.76841,
    "lon": -86.15804,
    "alt_m": 218,
    "precision_m": 12,
    "speed_mps": 0.7,
    "heading_deg": 183,
    "battery_pct": 78
  }
}
```

Candidate position event for `br04`:

```json
{
  "schema_version": 1,
  "msg_type": "position_report",
  "msg_id": "pos-20260424-0102",
  "source": "br04",
  "source_site": "b",
  "channel": "sensor",
  "observed_by": "bg02",
  "captured_at": "2026-04-24T14:20:00-04:00",
  "payload": {
    "lat": 39.76802,
    "lon": -86.15755,
    "alt_m": 217,
    "precision_m": 8,
    "speed_mps": 1.2,
    "heading_deg": 270,
    "battery_pct": 62
  }
}
```

#### Step 2: Site B Gateway Processing

`bg02` Pi:

- writes raw events to `message_events`
- updates `positions_current`
- appends rows to `positions_history`
- publishes normalized events to MQTT on `mesh/v1/site-b/sensor/up`

#### Step 3: Site A Consumption

`ag01` Pi or a central service receives the events and:

- updates Site A's operator-facing current map state
- optionally writes a replicated copy of history records for cross-site analysis

#### Step 4: Operator Query

An operator at Site A opens a map view and sees the current positions of `br03` and `br04`.

Historical movement queries should be able to answer questions such as:

- where was `br03` between `14:00` and `15:00`
- how often did `br04` move between zones
- what was the last observed location before loss of connectivity

### Candidate Position History Record

```json
{
  "event_id": "pos-20260424-0101",
  "source": "br03",
  "source_site": "b",
  "captured_at": "2026-04-24T14:20:00-04:00",
  "lat": 39.76841,
  "lon": -86.15804,
  "alt_m": 218,
  "precision_m": 12,
  "speed_mps": 0.7,
  "heading_deg": 183,
  "battery_pct": 78,
  "observed_by": "bg02"
}
```

### Deep Analysis

#### Requirements

- support current-position display and historical position retention
- update current state and append historical state in one ingest path
- support time-range queries by node and site
- preserve observation metadata such as which gateway saw the event

#### Concerns

- historical position retention can become large quickly
- inaccurate or stale GPS points can degrade trust in the system
- map display requirements and history-analysis requirements are different and should not share the same storage shape blindly

#### Missed Requirements

- retention period and down-sampling strategy for movement history
- privacy policy for long-term location retention
- handling of clock drift between nodes and gateways
- governance for rejecting identifiers that do not match the fleet naming standard

## Use Case 5: Basement Environmental And Water Monitoring

### Narrative

`bs01` measures basement humidity, temperature, and sump pit water level at Site B. The readings must be stored for later analysis and evaluated against alert thresholds.

Detailed telemetry storage, threshold evaluation, alert lifecycle, and stale-data requirements are refined in [Telemetry And Alerting](telemetry-alerting.md).

### Realistic Data Flow

#### Step 1: Sensor Capture At Site B

`bs01` emits a compact telemetry packet at a configured interval, for example every 5 minutes.

Candidate sensor event:

```json
{
  "schema_version": 1,
  "msg_type": "sensor_report",
  "msg_id": "sensor-20260424-0201",
  "source": "bs01",
  "source_site": "b",
  "channel": "sensor",
  "observed_by": "bg02",
  "captured_at": "2026-04-24T14:25:00-04:00",
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

#### Step 2: Site B Gateway Ingest

`bg02` Pi:

- writes the raw record to `sensor_events`
- writes a bridge observation record
- publishes the event to `mesh/v1/site-b/sensor/up`

#### Step 3: Alert Evaluation

An alert evaluator service subscribes to `mesh/v1/site-b/sensor/up` or reads from persisted `sensor_events`.

Candidate threshold records:

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

#### Step 4: Alert Generation

Later, the water level crosses the threshold.

Candidate alert event:

```json
{
  "schema_version": 1,
  "msg_type": "alert_event",
  "msg_id": "alert-20260424-0301",
  "source": "alert-module",
  "source_site": "b",
  "channel": "ops",
  "captured_at": "2026-04-24T15:02:00-04:00",
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

The alert can then be:

- stored in `alert_events`
- shown in a dashboard
- emitted as an operator-facing `ops` notification
- forwarded to an external notification channel later

### Deep Analysis

#### Requirements

- store raw sensor events for later analysis
- support threshold definitions in a database or configuration store
- evaluate alerts outside the RF node on a gateway or cloud-side module
- support alert severity and action mapping
- support multi-metric sensor reports without making the RF payload too large

#### Concerns

- sensor bursts or noisy readings can create alert storms
- threshold changes need versioning and auditability
- combining multiple metrics into one packet is efficient but complicates partial parsing and alerting

#### Missed Requirements

- sensor calibration metadata and units normalization
- alert suppression, acknowledgement, and escalation policies
- behavior when sensor data is stale or missing
- behavior when the alert evaluator is down but the gateway is still ingesting telemetry

## Cross-Use-Case Analysis

### Shared Requirements

- every event needs a stable message id for logging, replay, and de-duplication
- site-to-site traffic should preserve source identity, source site, and event timestamps
- current state and historical state are separate needs and should be stored separately where useful
- alert generation should be derived from persisted telemetry, not only from transient in-flight packets
- gateway logs should record observation, publish, consume, replay, and rejection decisions

### Shared Concerns

- nearby colocated radios can hide failures in the MQTT relay path
- low-bandwidth RF links make payload size and message frequency first-order constraints
- device naming inconsistencies will leak directly into schemas, queries, and alerts if not resolved early
- clock drift between nodes, gateways, and cloud services can make event ordering ambiguous
- replay and de-duplication policies must be consistent across gateways and downstream services

### Shared Missed Requirements

- a canonical event schema for all machine-processed traffic
- explicit expiry and retry semantics for each message class
- retention policies for chat, positions, telemetry, and alerts
- explicit privacy and logging expectations for operator conversations and historical location data
- a formal topic taxonomy for MQTT
- a decision on whether source gateways or a central service own cross-site fan-out

## Candidate Test Seeds

### Test 1: Broadcast Check-In Relay

- inject an `ops_broadcast` from `ar01`
- verify it is logged on Site A, published once to MQTT, received on Site B, and emitted on Site B RF

### Test 2: Direct Reply Path

- inject a direct `ops_reply` from `br02` to `ar01`
- verify only the addressed remote path is used for bridge delivery

### Test 3: Direct Dialog Correlation

- inject a two-message `ops_direct` exchange with a shared `conversation_id`
- verify both ends preserve the target and do not fall back to broadcast handling

### Test 4: Position History Persistence

- feed a timed series of `position_report` events for `br03`
- verify current map state updates and historical records remain queryable by time range

### Test 5: Threshold Alert Generation

- feed `sensor_report` events for `bs01` with rising `water_level_cm`
- verify no alert below threshold and correct alert generation once the threshold is crossed

### Test 6: Radio-Absent Gateway Behavior

- deliver inbound MQTT traffic to a gateway with no attached USB radio
- verify the gateway does not silently consume messages it cannot radiate locally

## Open Questions

- how much conversation history should be retained for targeted operator dialogs
- should position history live on the gateway, in a central database, or in both
- what final production retention periods are required for movement history and sensor history
- should alert thresholds be managed centrally or per site
- should invalid or legacy device identifiers be rejected at ingest or mapped through an inventory alias table
- should human-readable alerts also produce machine-readable incident records
