# Application Protocol

## Purpose

This document defines the shared application-layer envelope for non-adhoc traffic that passes through the Pi-assisted gateway service.

It does **not** define the final compact payload formats for every message class. Instead, it defines the common fields and rules that all machine-processed messages must follow so gateways, brokers, storage layers, and later protocol modules can interoperate consistently.

## Scope

This protocol applies to:

- `sensor` events
- `control` events
- gateway-generated operational events
- any normalized `ops` traffic that requires machine handling beyond raw text relay

This protocol does not replace native Meshtastic user experience for simple human text messages. Plain human chat may still originate as ordinary Meshtastic traffic and then be normalized by the gateway only as needed.

## Design Goals

- provide one canonical event envelope across RF, MQTT, and persistence
- preserve source identity and observation context
- support de-duplication, replay, and expiry
- remain compact enough for low-bandwidth [LoRa](https://www.semtech.com/lora) environments
- allow later message-class-specific schemas without changing the top-level contract

## Envelope Overview

Every normalized machine-processed event should follow this structure:

```json
{
  "schema_version": 1,
  "msg_type": "example",
  "msg_id": "example-20260425-0001",
  "source": "bs01",
  "source_site": "b",
  "target": null,
  "target_scope": null,
  "channel": "sensor",
  "observed_by": "bg02",
  "captured_at": "2026-04-25T10:15:00-04:00",
  "expires_at": null,
  "correlation_id": null,
  "priority": "normal",
  "flags": [],
  "payload": {}
}
```

## Field Definitions

### `schema_version`

- integer
- defines the envelope version
- initial value: `1`

### `msg_type`

- string
- identifies the semantic message class
- examples:
  - `ops_broadcast`
  - `ops_reply`
  - `ops_direct`
  - `position_report`
  - `sensor_report`
  - `control_request`
  - `control_result`
  - `alert_event`
  - `gateway_state`

### `msg_id`

- string
- globally unique id for the event
- required for de-duplication, replay safety, and auditability

Candidate form:

- `{class}-{yyyymmdd}-{sequence-or-random}`

Examples:

- `sensor-20260425-0201`
- `ctrl-20260425-a91f`

### `source`

- string
- canonical device or service id that originated the event
- examples:
  - `ar01`
  - `bs01`
  - `ag01`
  - `alert-module`

### `source_site`

- string
- canonical site code for the event source
- examples:
  - `a`
  - `b`
  - `c`

### `target`

- nullable string
- explicit target node or service when the event is directed
- examples:
  - `br02`
  - `ag01`

### `target_scope`

- nullable string
- logical audience when the event is not point-to-point
- examples:
  - `site-b-ops`
  - `site-a-gateways`
  - `all-alert-consumers`

Only one of `target` or `target_scope` should normally be populated.

### `channel`

- string
- logical channel class used by policy
- expected values in Phase 1:
  - `ops`
  - `sensor`
  - `control`

### `observed_by`

- string
- gateway id that observed or normalized the event for bridge handling
- examples:
  - `ag01`
  - `bg02`

### `captured_at`

- RFC 3339 timestamp string
- timestamp associated with when the gateway captured or normalized the event

### `expires_at`

- nullable RFC 3339 timestamp string
- optional expiration time after which the event should not be replayed or acted upon

Recommended:

- allow for `control_request`
- allow for urgent `ops` broadcasts
- optional for telemetry

### `correlation_id`

- nullable string
- links related events such as replies, conversations, requests, and results

Examples:

- a broadcast reply chain
- a direct conversation id
- a `control_result` linked to a `control_request`

### `priority`

- string
- candidate values:
  - `low`
  - `normal`
  - `high`
  - `critical`

### `flags`

- array of strings
- optional behavior hints or handling markers

Examples:

- `["replayed"]`
- `["alert"]`
- `["requires_ack"]`

### `payload`

- object
- message-class-specific body
- defined separately for each `msg_type`

## Core Rules

### Rule 1: Stable Identity

The gateway must preserve `msg_id`, `source`, and `source_site` across relay, replay, and persistence.

### Rule 2: No Blind Schema Guessing

Consumers must branch behavior from `schema_version` and `msg_type`, not by trying to infer payload shape dynamically.

### Rule 3: Preserve Original Meaning

Bridge handling must not silently convert:

- direct messages into broadcasts
- site-targeted messages into global messages
- telemetry into alert events

### Rule 4: Replay Must Preserve Message Identity

If an event is replayed after broker recovery, the gateway must preserve the original `msg_id` and mark replay state through observations or flags rather than inventing a new id.

### Rule 5: Expired Messages Must Not Act

If `expires_at` is present and in the past, the event:

- may still be stored for auditability
- must not trigger new control actions
- must not be emitted as fresh operator traffic

## Recommended Field Presence By Message Class

### `ops_broadcast`

- requires `msg_id`, `source`, `source_site`, `channel`, `captured_at`
- requires `target_scope`
- payload should contain text and optional priority context

### `ops_reply`

- requires `target`
- should populate `correlation_id` or equivalent reply linkage

### `ops_direct`

- requires `target`
- should populate `correlation_id` for conversation tracking
- must not also populate a site-wide `target_scope`
- represents targeted routing and presentation, not a guarantee of end-to-end privacy

## Direct Ops Semantics

Phase 1 direct operator dialogs are gateway-normalized `ops_direct` events with an explicit `target`.

Rules:

- the source gateway must preserve the original sender and target
- the destination gateway must verify that the target belongs to its site or is locally reachable
- gateways must not silently convert `ops_direct` into `ops_broadcast`
- gateways may store direct dialog events in `message_events` for troubleshooting, replay, and audit
- user-facing docs and clients must not imply end-to-end privacy unless a later implementation provides and validates it

This keeps direct dialogs from creating unnecessary shared-channel noise while avoiding a false privacy claim.

### `position_report`

- target fields should be null
- payload should contain compact positional metrics only

### `sensor_report`

- target fields should be null
- payload should contain a compact metric list or structured sensor block

### `control_request`

- requires `target`
- should require `expires_at`
- should normally include `requires_ack` in `flags`

### `control_result`

- requires `target`
- should carry `correlation_id` referencing the originating request

### `alert_event`

- target may be null if routed to a scope
- should identify the related source and threshold condition in payload

## Candidate Examples

### Example: Sensor Report

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
  "captured_at": "2026-04-25T10:30:00-04:00",
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

### Example: Control Request

```json
{
  "schema_version": 1,
  "msg_type": "control_request",
  "msg_id": "ctrl-20260425-a91f",
  "source": "ag01",
  "source_site": "a",
  "target": "bs01",
  "target_scope": null,
  "channel": "control",
  "observed_by": "ag01",
  "captured_at": "2026-04-25T10:31:00-04:00",
  "expires_at": "2026-04-25T10:31:30-04:00",
  "correlation_id": "ctrl-20260425-a91f",
  "priority": "high",
  "flags": [
    "requires_ack"
  ],
  "payload": {
    "action": "pump_test",
    "duration_s": 10
  }
}
```

### Example: Control Result

```json
{
  "schema_version": 1,
  "msg_type": "control_result",
  "msg_id": "ctrlres-20260425-b042",
  "source": "bg02",
  "source_site": "b",
  "target": "ag01",
  "target_scope": null,
  "channel": "control",
  "observed_by": "bg02",
  "captured_at": "2026-04-25T10:31:08-04:00",
  "expires_at": null,
  "correlation_id": "ctrl-20260425-a91f",
  "priority": "normal",
  "flags": [],
  "payload": {
    "status": "ok",
    "action": "pump_test",
    "duration_s": 10
  }
}
```

## Protocol Handling Expectations

### On RF Ingest

The gateway should normalize any bridgeable event into this envelope before:

- persistence
- MQTT publish
- policy enforcement that depends on message class

### On MQTT Ingest

The gateway should validate:

- `schema_version`
- required fields for the given `msg_type`
- site and target rules
- expiry
- de-duplication status

### On Persistence

The full envelope should be stored, or stored losslessly in normalized columns plus payload JSON.

## Validation Requirements

Every consumer should be able to reject an event if:

- `schema_version` is unsupported
- `msg_id` is missing
- `msg_type` is unknown
- `source` is missing
- `captured_at` is malformed
- both `target` and `target_scope` are set in a way that violates local rules
- required payload fields for the declared `msg_type` are missing

Rejected events should still produce a gateway observation for diagnostics.

## Out Of Scope For This Document

- exact compact payload field sets for `sensor_report`
- exact compact payload field sets for `control_request` and `control_result`
- final byte-budget limits for each message class
- chunking for oversized payload transfer

Those belong to later tasks.

## Open Decisions

- whether `msg_id` format should be gateway-generated, source-generated, or hybrid
- whether `captured_at` should be source time, gateway time, or both
- whether `priority` is free-form or enumerated strictly
- whether `flags` remain strings or become a compact bitset later
- whether human `ops` messages always enter this envelope or only when bridge logic requires it

## Exit Criteria For This Task

This task is complete when the design defines:

- the shared envelope fields
- required identity and timing metadata
- target versus target-scope rules
- replay and expiry expectations
- validation rules for consumers
- enough common structure for later `sensor` and `control` schemas to build on
