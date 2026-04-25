# Payload Transfer Decision

## Purpose

This document records the Phase 1 decision for large-payload transfer over the Meshtastic plus MQTT architecture and defines the rules that would apply if chunked transfer becomes necessary later.

## Decision

Large-payload transfer is **out of scope for Phase 1**.

Phase 1 will optimize for:

- human messaging
- compact telemetry
- compact control requests and results
- compact position updates

The system should not assume that arbitrary large payloads can be moved safely across the RF mesh.

## Why This Decision Exists

### RF Capacity Is Limited

The local [LoRa](https://www.semtech.com/lora) mesh is the narrowest transport in the system. Large transfers increase airtime consumption, delay other traffic, and raise the chance of partial delivery.

### Chunking Adds Significant Complexity

Any multi-part transfer requires:

- transfer identity
- ordering
- expiry
- retry policy
- integrity checks
- duplicate suppression
- reassembly buffers

That is a separate protocol problem, not a small extension of ordinary telemetry.

### Human And Control Traffic Must Win

If the system ever experiences contention, ordinary operator traffic and important control outcomes must not lose to bulk transfer attempts.

## Phase 1 Policy

### Allowed

- compact `ops` text
- compact `sensor_report`
- compact `position_report`
- compact `control_request`
- compact `control_result`
- compact `alert_event`

### Not Allowed

- large text documents
- log dumps
- firmware blobs
- repeated history snapshots
- arbitrary file transfer
- routine fragmentation as a normal message path

## Default Gateway Behavior

If a message design requires fragmentation for normal operation, the gateway design should reject that payload model as not Phase 1 compatible.

If a rare oversized event is encountered before a formal fragmentation protocol exists, the gateway should:

- reject the event for RF relay
- record a diagnostic observation
- optionally preserve the event locally for analysis if policy allows

The gateway should not invent an ad hoc fragmentation scheme at runtime.

## What Counts As Oversized

This decision intentionally avoids hardcoding a single byte limit here.

For Phase 1, a payload should be considered oversized if:

- it cannot be sent comfortably without fragmentation in the expected RF path
- it materially harms ordinary operator or telemetry traffic
- it requires an unusual encoding trick just to fit routine use

Exact thresholds belong in later measured transport-budget work.

## If Chunked Transfer Becomes Necessary Later

The system will need an explicit transfer protocol layered on top of the shared application envelope.

## Candidate Chunked Transfer Envelope

Each chunk event should still use the shared application envelope, with a payload such as:

```json
{
  "transfer_id": "xfer-20260425-0001",
  "chunk_index": 0,
  "chunk_count": 4,
  "chunk_bytes_b64": "AQIDBA==",
  "content_type": "application/octet-stream",
  "checksum": "sha256:example",
  "final": false
}
```

## Required Fields For Future Chunking

### `transfer_id`

- unique id shared by all chunks in one transfer

### `chunk_index`

- zero-based index of this chunk

### `chunk_count`

- total number of chunks expected

### `chunk_bytes_b64`

- encoded bytes for the chunk body

### `checksum`

- integrity token for whole-transfer or per-chunk validation

### `final`

- indicates whether the chunk is the final chunk in the transfer

## Required Rules For Any Future Chunking Protocol

### Rule 1: Bounded Transfer Size

Every transfer class must have a maximum allowed total size.

### Rule 2: Bounded Reassembly Lifetime

Partial transfers must expire after a defined timeout.

### Rule 3: Duplicate Suppression

Repeated chunks must not produce repeated reassembly work indefinitely.

### Rule 4: Integrity Validation

The receiving side must validate that the reassembled content matches the expected checksum before acting on it.

### Rule 5: Freshness Over Completeness

Expired or stale multi-part data must be discarded rather than replayed blindly.

### Rule 6: Traffic Class Protection

Chunked transfer must not starve:

- human `ops` traffic
- active control flows
- urgent alert propagation

### Rule 7: Clear Failure Semantics

The system must define what counts as:

- incomplete
- failed
- expired
- superseded

for a transfer.

## Candidate Transfer States

If later implemented, each transfer should move through a state model such as:

- `queued`
- `sending`
- `partial`
- `complete`
- `failed`
- `expired`
- `discarded`

## Candidate Storage For Future Transfers

If chunking is ever added, the gateway will likely need:

### `transfer_sessions`

- `transfer_id`
- `source`
- `target`
- `content_type`
- `created_at`
- `expires_at`
- `status`
- `expected_chunks`
- `received_chunks`

### `transfer_chunks`

- `transfer_id`
- `chunk_index`
- `stored_at`
- `chunk_data`
- `checksum`

## Risks If This Decision Is Ignored

- RF airtime can be consumed by low-value bulk traffic
- operator messaging becomes unreliable during transfer bursts
- partial transfers create ambiguous state
- debugging becomes much harder because failures are no longer single-event failures

## Requirements Derived From This Decision

- compact message classes remain the default design path
- future large transfer support requires a dedicated protocol and storage model
- replay policy must treat chunked transfer as lower priority than normal operator and control traffic

## Open Decisions For A Future Chunking Task

- whether chunking is ever needed at all
- which content types would justify it
- whether chunking should be broker-only, RF-only, or truly end-to-end
- whether chunking should ever be allowed from ordinary field radios rather than gateway-only services

## Exit Criteria For This Task

This task is complete when the design:

- explicitly rejects large-payload transfer for Phase 1
- defines how the gateway should behave when oversized payloads appear
- records the mandatory protocol rules that any future chunking feature would need
