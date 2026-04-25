# Gateway Acceptance Test Plan

## Purpose

This document defines the first implementation-facing acceptance tests for the Raspberry Pi-assisted gateway service.

The goal is to convert the architecture and requirements documents into executable expectations before gateway code is written. These tests should be usable against a local lab implementation with a Docker MQTT broker, a gateway service process, a local SQLite store, and either a real or simulated Meshtastic serial radio.

## Scope

These tests cover gateway behavior at the service boundary:

- radio health handling
- broker health handling
- outbound queueing and replay
- expiry handling
- de-duplication and loop prevention
- policy rejection
- gateway health publication
- telemetry ingest and alert-evaluator handoff

They do not require final hardware installation or outdoor RF validation. RF behavior may be simulated when the test is about gateway state transitions rather than radio propagation.

## Test Environment Assumptions

Phase 1 acceptance testing should support this minimum lab setup:

- one gateway service instance configured as `ag01`
- one gateway service instance configured as `bg02`
- one private MQTT broker reachable by both gateway instances
- one local SQLite database per gateway
- one real or simulated serial radio per gateway, depending on the test
- deterministic test fixtures for `ops`, `sensor`, `control`, and `gateway_state` messages

The test harness should be able to:

- start and stop the MQTT broker
- disconnect and reconnect the simulated radio
- inject RF-observed events into the gateway
- inject MQTT-delivered events into the gateway
- inspect gateway database rows
- inspect MQTT publishes
- inspect gateway health state

## Common Fixtures

### `ops_broadcast`

```json
{
  "schema_version": 1,
  "msg_type": "ops_broadcast",
  "msg_id": "ops-test-0001",
  "source": "ar01",
  "source_site": "a",
  "target": null,
  "target_scope": "site-b-ops",
  "channel": "ops",
  "observed_by": "ag01",
  "captured_at": "2026-04-25T12:00:00-04:00",
  "expires_at": "2026-04-25T12:15:00-04:00",
  "correlation_id": null,
  "priority": "normal",
  "flags": [],
  "payload": {
    "text": "What's going on down there. Please check in."
  }
}
```

### `sensor_report`

```json
{
  "schema_version": 1,
  "msg_type": "sensor_report",
  "msg_id": "sensor-test-0001",
  "source": "bs01",
  "source_site": "b",
  "target": null,
  "target_scope": null,
  "channel": "sensor",
  "observed_by": "bg02",
  "captured_at": "2026-04-25T12:05:00-04:00",
  "expires_at": null,
  "correlation_id": null,
  "priority": "normal",
  "flags": [],
  "payload": {
    "sensor_set": "basement_sump_monitor",
    "metrics": [
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

### `control_request`

```json
{
  "schema_version": 1,
  "msg_type": "control_request",
  "msg_id": "ctrl-test-0001",
  "source": "ag01",
  "source_site": "a",
  "target": "bs01",
  "target_scope": null,
  "channel": "control",
  "observed_by": "ag01",
  "captured_at": "2026-04-25T12:10:00-04:00",
  "expires_at": "2026-04-25T12:10:30-04:00",
  "correlation_id": "ctrl-test-0001",
  "priority": "high",
  "flags": [
    "requires_ack"
  ],
  "payload": {
    "action": "pump_test",
    "params": {
      "duration_s": 10
    }
  }
}
```

## Acceptance Tests

### Test 1: Healthy RF To MQTT Bridge

Preconditions:

- `ag01` radio is healthy
- MQTT broker is connected
- `ops` channel policy allows `ar01` traffic to bridge

Steps:

1. inject `ops_broadcast` as an RF-observed event at `ag01`
2. wait for gateway processing
3. inspect `ag01` storage and MQTT publishes

Expected:

- `message_events` contains one `rf_in` observation
- `outbound_queue` contains the event before publish
- MQTT receives one publish on the configured Site A `ops` topic
- queue status becomes published or complete
- `gateway_observations` records `publish_succeeded`
- the original `msg_id` is preserved

### Test 2: Broker Down Queueing

Preconditions:

- `ag01` radio is healthy
- MQTT broker is unavailable
- `ops` channel policy allows queueing

Steps:

1. stop the MQTT broker
2. inject `ops_broadcast` as an RF-observed event
3. inspect gateway storage

Expected:

- local RF ingest succeeds
- `message_events` records the event
- `outbound_queue` contains a pending entry
- `gateway_observations` records publish failure or broker unavailable state
- no event is lost because the broker is down
- gateway health reports `broker_state` as disconnected and queue depth greater than zero

### Test 3: Broker Recovery Replay

Preconditions:

- Test 2 has left one pending non-expired queue entry
- MQTT broker is restarted

Steps:

1. restore broker connectivity
2. wait for replay
3. inspect MQTT publishes and queue state

Expected:

- queued event is published once
- original `msg_id` is preserved
- `gateway_observations` records `replay_started` and `replay_completed`
- queue entry status becomes published or complete
- replay does not create a second logical `message_events` event

### Test 4: Expired Queue Entry Is Not Replayed

Preconditions:

- broker is down
- a bridge-eligible event exists with `expires_at` in the past before broker recovery

Steps:

1. queue the expired event
2. restore broker connectivity
3. inspect MQTT publishes and queue state

Expected:

- expired event is not published as fresh traffic
- queue entry becomes expired or discarded
- `gateway_observations` records expiry handling
- event remains available for audit if storage policy allows

### Test 5: Radio Missing Pauses Inbound MQTT Consumption

Preconditions:

- `bg02` broker connection is healthy
- `bg02` USB radio is missing or serial unhealthy
- inbound site-bound relay topics are normally subscribed when radio is healthy

Steps:

1. put `bg02` into radio-missing state
2. deliver an inbound MQTT `ops_broadcast` targeted to Site B
3. inspect subscriptions, storage, and RF transmit attempts

Expected:

- gateway health reports radio unavailable
- gateway pauses or unsubscribes from inbound site-bound relay topics
- gateway does not silently consume and discard site-bound MQTT traffic
- no RF transmit attempt is made while radio is unavailable
- if any inbound event is accepted, it is stored only under an explicitly enabled bounded inbound queue policy

### Test 6: Radio Recovery Resumes Inbound Relay

Preconditions:

- `bg02` is in radio-missing state from Test 5
- MQTT broker remains healthy

Steps:

1. restore the USB radio or simulated radio health
2. wait for gateway health transition
3. deliver a new inbound MQTT event targeted to Site B

Expected:

- gateway health reports radio healthy
- inbound topic consumption resumes
- new inbound event is validated
- RF transmit is requested once
- `gateway_observations` records radio recovery and RF emit result

### Test 7: Duplicate MQTT Event Is Suppressed

Preconditions:

- `bg02` radio and broker are healthy
- de-duplication cache is empty

Steps:

1. deliver an inbound MQTT event with `msg_id` `ops-test-0001`
2. deliver the same event again
3. inspect RF transmit attempts and storage

Expected:

- first event is processed according to policy
- second event is rejected as duplicate
- only one RF transmit attempt is made
- duplicate handling is recorded in `gateway_observations`
- de-duplication uses stable `msg_id`, not payload text comparison

### Test 8: Loop Prevention Across Gateways

Preconditions:

- `ag01` and `bg02` are both connected to the broker
- both gateways subscribe to their relevant inbound topics

Steps:

1. inject a Site A event that bridges to MQTT
2. let Site B consume and emit it locally
3. simulate the emitted event being observed again by the Site B gateway

Expected:

- Site B does not republish the same `msg_id` back to Site A
- dedupe cache or source-path tracking prevents A-to-B-to-A ping-pong
- loop prevention is logged

### Test 9: Policy Rejection

Preconditions:

- gateway policy rejects `control_request` from non-allowlisted senders

Steps:

1. inject a `control_request` with an unapproved `source`
2. inspect storage, MQTT publishes, and control adapter calls

Expected:

- request is rejected before any control adapter action
- no MQTT publish occurs unless policy explicitly allows rejected-event audit publication
- `gateway_observations` records `policy_rejected`
- rejection includes enough detail to diagnose sender, target, channel, and reason

### Test 10: Gateway Health Publication

Preconditions:

- gateway service is running
- broker is reachable

Steps:

1. start the gateway service
2. inspect MQTT gateway state topic
3. change radio or broker state
4. inspect updated gateway state

Expected:

- gateway publishes health on its configured gateway state topic
- health includes gateway id, site, radio state, broker state, queue depth, and timestamp
- state changes are published after broker or radio transitions
- private credentials or channel secrets are not included in health payloads

### Test 11: Telemetry Storage Handoff

Preconditions:

- `bg02` accepts `sensor_report` events from `bs01`
- telemetry storage is enabled

Steps:

1. inject the `sensor_report` fixture
2. inspect `sensor_events`
3. inspect parsed metric storage or handoff output

Expected:

- full normalized event is stored once
- parsed metric rows or equivalent handoff records are created for each metric
- metric values preserve source, sensor set, unit, and capture time
- alert evaluator can process the event from persisted state or a durable handoff

### Test 12: Malformed Event Rejection

Preconditions:

- gateway is healthy

Steps:

1. inject an event missing `msg_id`
2. inject an event with unsupported `schema_version`
3. inject an event with both incompatible target and target scope values

Expected:

- invalid events are rejected
- rejection is recorded in `gateway_observations`
- rejected events do not reach RF transmit, MQTT publish, control adapter, or alert evaluator paths
- forensic storage behavior follows configured policy

## Validation Artifacts

Each automated acceptance test should capture:

- gateway id and site
- test case id
- input fixture
- observed database rows
- observed MQTT messages
- observed radio transmit requests
- gateway health before and after the test
- pass or fail result

## Exit Criteria

This test plan is ready to implement when:

- every listed behavior has a deterministic fixture or state setup
- expected storage side effects are defined
- expected MQTT side effects are defined
- expected radio side effects are defined
- degraded-mode expectations are testable without relying on outdoor RF conditions
- failures produce enough observations to diagnose the broken boundary
