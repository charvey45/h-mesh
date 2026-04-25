# Gateway Service Design

## Purpose

This document defines the Phase 1 service design for the Raspberry Pi-assisted gateway that bridges a local [Meshtastic](https://meshtastic.org/) radio mesh to the inter-site [MQTT](https://mqtt.org/) backbone.

The gateway service is the core application component in this architecture. It owns radio integration, message normalization, bridge policy, logging, queueing, replay behavior, and degraded-mode handling.

## Design Goals

- bridge approved traffic between local RF and MQTT
- preserve local RF operation when WAN is unavailable
- provide deterministic logging and replay behavior
- prevent silent message loss when the USB radio or broker is unavailable
- separate human, telemetry, and automation handling paths
- make later protocol and test design hang from a clear service contract

## Service Boundary

The gateway service runs on the Raspberry Pi and communicates with:

- the local Meshtastic radio over USB serial
- the MQTT broker over IP networking
- local persistent storage for logs, queue state, and current state caches
- optional local APIs, dashboards, or control adapters
- optional external consumers such as alert evaluators or dashboards

The service does **not** own:

- Meshtastic firmware behavior on the radio
- broker implementation details
- external notification delivery beyond publishing the relevant event
- final operator UI design

## Service Responsibilities

### Radio Integration

- maintain the USB serial connection to the local gateway radio
- observe radio health and serial health separately
- ingest received packets from the local mesh
- request local RF transmission for approved outbound traffic

### Message Handling

- normalize received packets into a gateway event envelope
- classify traffic by channel and message class
- apply per-channel and per-sender bridge policy
- preserve source identity, timestamps, and message ids

### Broker Integration

- publish approved inter-site events to MQTT
- subscribe to relevant inbound relay topics
- pause or resume inbound consumption according to local radio health

### Reliability

- persist outbound bridge-eligible events before publish
- replay pending events after broker recovery
- de-duplicate inbound relay events
- keep bounded queue semantics with expiry and replay controls

### Observability

- log all observation, publish, consume, replay, and rejection decisions
- publish gateway health state
- expose counters and recent state for troubleshooting

### Safety

- prevent arbitrary MQTT or mesh events from directly driving high-current control outputs
- enforce stricter policy for `control` than for `ops` or `sensor`

## Candidate Runtime Components

The gateway service may be implemented as one process or several cooperating modules. The design assumes these logical components exist even if they end up in one binary.

### Radio Adapter

- owns serial session lifecycle
- decodes local radio events into internal service events
- encodes outbound local RF transmission requests

### Event Normalizer

- converts radio-specific input into a shared internal event model
- stamps observation metadata such as `observed_by` and `captured_at`

### Policy Engine

- evaluates whether an event is local-only, bridge-eligible, blocked, or requires special handling
- applies per-channel, per-type, and per-site rules

### Queue Manager

- stores outbound pending events durably
- tracks publish attempts, expiry, and replay status
- handles inbound quarantine only if explicitly enabled later

### MQTT Adapter

- manages broker connection lifecycle
- publishes normalized events
- subscribes to inbound topics
- pauses consumption when the local radio cannot transmit

### State Store

- stores current gateway health
- stores de-duplication history
- stores last-known state such as current positions if the gateway owns that responsibility

### Control Adapter

- optional module for supervised automation outputs
- consumes only allowlisted control intents after policy approval

## Candidate Data Stores

SQLite is the default Phase 1 assumption for local state because it is simple, durable, and easy to back up from a Raspberry Pi.

### `message_events`

Stores normalized human and machine events observed or relayed by the gateway.

Candidate fields:

- `msg_id`
- `msg_type`
- `source`
- `source_site`
- `target`
- `target_scope`
- `channel`
- `captured_at`
- `observed_by`
- `direction` such as `rf_in`, `mqtt_in`, `mqtt_out`, `rf_out`
- `payload_json`
- `status`

### `gateway_observations`

Stores operational decisions and health transitions.

Candidate fields:

- `event_id`
- `gateway_id`
- `observed_at`
- `kind`
- `detail`
- `related_msg_id`

Example kinds:

- `radio_connected`
- `radio_disconnected`
- `mqtt_connected`
- `mqtt_disconnected`
- `publish_succeeded`
- `publish_failed`
- `rf_emit_succeeded`
- `rf_emit_failed`
- `policy_rejected`
- `replay_started`
- `replay_completed`

### `outbound_queue`

Stores bridge-eligible events waiting for broker publish or replay.

Candidate fields:

- `queue_id`
- `msg_id`
- `topic`
- `payload_json`
- `queued_at`
- `expires_at`
- `attempt_count`
- `last_attempt_at`
- `status`

### `dedupe_cache`

Stores recently seen message ids for loop prevention and replay safety.

Candidate fields:

- `msg_id`
- `first_seen_at`
- `source_path`
- `expires_at`

## Service State Model

The gateway service should track these health axes independently:

- process health
- radio presence
- radio serial health
- broker connectivity
- local queue depth

### Composite Modes

#### Healthy

- radio present
- serial healthy
- broker connected
- inbound subscriptions active
- outbound queue draining normally

#### Broker Down

- radio present
- serial healthy
- broker unavailable
- outbound bridge-eligible traffic queued locally
- local RF still functions

#### Radio Down

- broker connected
- USB radio absent or serial unhealthy
- outbound RF reinjection disabled
- inbound relay consumption paused

#### Fully Degraded

- broker unavailable
- radio unavailable
- service remains observable but cannot bridge or radiate

## Message Paths

### RF To MQTT

1. radio adapter receives a packet over serial
2. event normalizer creates a gateway event
3. policy engine decides whether the event is bridge-eligible
4. dedupe cache rejects repeats if already seen
5. event is written to `message_events`
6. if bridge-eligible, queue manager persists it in `outbound_queue`
7. MQTT adapter publishes it
8. on success, queue status is updated and a `publish_succeeded` observation is written

### MQTT To RF

1. MQTT adapter receives an event from a subscribed topic
2. dedupe cache rejects repeats if already seen
3. event is written to `message_events`
4. policy engine validates site, channel, and sender rules
5. if radio is healthy, radio adapter emits to local RF
6. result is written to `gateway_observations`

### Local-Only Handling

Some messages should never cross the site boundary. The policy engine must support local-only rules by channel, message class, sender, or receiver.

## MQTT Behavior

### Publish Rules

- publish only normalized gateway events, not raw radio-specific blobs
- use a stable topic taxonomy per site and channel
- prefer QoS `1` for inter-site control and important event delivery
- use non-retained messages for transient chat and telemetry events

### Subscribe Rules

- subscribe only to topics relevant to the local site and channel policy
- pause or unsubscribe from inbound relay topics when the local radio is unavailable
- do not silently consume inbound messages that the gateway cannot emit locally

### Candidate Topic Pattern

- `mesh/v1/site-a/ops/up`
- `mesh/v1/site-a/sensor/up`
- `mesh/v1/site-a/control/up`
- `mesh/v1/site-b/ops/up`
- `mesh/v1/site-b/sensor/up`
- `mesh/v1/site-b/control/up`
- `mesh/v1/site-a/gateway/ag01/state`
- `mesh/v1/site-b/gateway/bg02/state`

## Queueing And Replay

### Outbound Queue

Phase 1 requires durable queueing for outbound inter-site traffic when broker connectivity is unavailable.

Rules:

- queue before publish for bridge-eligible traffic
- apply expiry to prevent stale replay
- preserve ordering within a site and channel where practical
- increment attempt count and record failures

### Replay

When broker connectivity returns:

- replay pending entries in oldest-first order by default
- skip expired entries
- preserve original `msg_id`
- write replay observations for auditability

### Inbound Queueing

Inbound MQTT queueing for later RF reinjection is **not** the default behavior.

Default Phase 1 rule:

- if the radio is unavailable, pause inbound consumption rather than draining site-bound relay traffic into a local queue

Inbound queueing should be added only if later requirements justify:

- bounded durable storage
- replay ordering rules
- message expiry
- duplicate suppression
- explicit operator visibility into backlog state

## De-Duplication And Loop Prevention

Every bridgeable event needs a stable `msg_id`.

The gateway must:

- remember recently seen ids from both RF and MQTT paths
- reject events already relayed by the local gateway
- prevent A-to-B-to-A ping-pong loops
- preserve original ids during replay

## Policy Model

### Ops

- supports broadcast, reply, and direct human messaging
- usually bridge-eligible between approved sites
- should preserve sender and target semantics

### Sensor

- supports structured telemetry and position reports
- may be bridge-eligible with rate limits
- should flow into persistence and alerting consumers

### Control

- strictest policy path
- allowlisted senders, targets, and actions only
- requires explicit logging and result reporting
- must not directly energize high-current hardware without control adapter validation

## Gateway Health Publication

Each gateway should publish a lightweight health event.

Candidate topic:

- `mesh/v1/site-a/gateway/ag01/state`

Candidate payload:

```json
{
  "gateway_id": "ag01",
  "site": "a",
  "radio_state": "healthy",
  "broker_state": "connected",
  "queue_depth": 0,
  "observed_at": "2026-04-25T09:10:00-04:00"
}
```

## Operational Rules

### Startup

1. initialize storage
2. start radio adapter
3. start MQTT adapter
4. publish gateway health
5. if broker is connected, resume outbound replay
6. enable inbound subscriptions only when the radio is healthy

### Shutdown

1. stop new inbound handling
2. flush in-memory observations
3. preserve queue state
4. close serial and broker sessions cleanly

### Recovery

- radio recovery should re-enable inbound relay consumption
- broker recovery should trigger outbound replay
- repeated flapping should be visible in `gateway_observations`

## Security And Privacy

- broker credentials and channel secrets remain outside version control
- control intents require stricter policy and auditing than human chat
- direct operator dialogs may still be logged by the gateway even if treated as private from a user perspective
- sensitive payload logging should be configurable if later privacy requirements demand redaction

## Testing Implications

This service contract implies these test classes:

- radio adapter connection and recovery tests
- broker disconnect and replay tests
- de-duplication and loop-prevention tests
- policy acceptance and rejection tests
- radio-absent inbound pause tests
- outbound queue expiry tests
- gateway health publication tests

## Open Decisions

- whether the gateway runs as one process or several services
- whether the gateway owns current-state caches such as current positions or forwards that entirely to a central service
- exact MQTT topic taxonomy and QoS choices per message class
- whether direct human dialogs are normalized beyond native Meshtastic semantics
- whether inbound quarantine is ever needed for `ops`, `sensor`, or `control`

## Exit Criteria For This Task

This task is complete when the design clearly defines:

- serial integration responsibility
- MQTT bridge flow
- queue and replay behavior
- logging and observability boundaries
- degraded-mode handling for broker-down and radio-down states
- policy boundaries for `ops`, `sensor`, and `control`
