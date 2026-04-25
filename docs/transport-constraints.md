# Transport Constraints

## Purpose

This document defines the practical transport constraints that should shape the application protocol and payload designs for the multi-site Meshtastic system.

The goal is not to guess a single magic payload limit. The goal is to define safe engineering rules for a low-bandwidth [LoRa](https://www.semtech.com/lora) transport where airtime, retries, and contention matter more than raw network throughput.

## Primary Design Principle

Treat the RF mesh as a scarce transport.

That means:

- keep messages small
- keep message frequency bounded
- avoid needless repetition
- prefer state changes over verbose snapshots
- design for graceful degradation when bandwidth is limited

## Constraint Categories

### Airtime Is Expensive

Longer payloads consume more airtime and increase the chance of contention, collisions, and delayed delivery.

Implications:

- short payloads are preferable even when the broker path is healthy
- chat, telemetry, and control traffic compete for the same limited RF opportunity
- repeated retransmission of large messages can degrade the entire local mesh

### Multi-Hop Costs Compound

A message that crosses multiple local hops before reaching the gateway consumes more local mesh capacity than a gateway-originated event.

Implications:

- the system should not assume that every field node has the same practical transport budget as a gateway node
- payload design must remain conservative even if a lab test works well at one hop

### RF And Broker Constraints Are Different

The MQTT backbone can carry richer payloads than the RF side, but the end-to-end design must still honor the narrowest segment.

Implications:

- the gateway should normalize once, but payload design should be driven by RF constraints first
- do not design an envelope that is comfortable for MQTT but hostile to LoRa

### Reliability Adds Overhead

De-duplication, acknowledgements, correlation ids, retries, and replay behavior all consume bytes and processing.

Implications:

- identity fields must be compact and stable
- message metadata must earn its place
- optional fields should stay optional

## Phase 1 Message Budget Guidance

The following guidance is intentionally expressed as policy rather than fixed byte limits. Exact numerical limits should be confirmed later against real gateway and field-node behavior.

### Ops Messages

- keep human text concise
- prefer direct responses over repeated broad broadcasts
- avoid embedding large structured metadata in human message envelopes

### Sensor Messages

- prefer compact metric names or coded forms later if needed
- send only the metrics required for the current use case
- avoid repeating static configuration in every report
- prefer one compact report over multiple fragmented reports when the report still fits the transport budget

### Control Messages

- keep request and result payloads minimal
- send action intent and outcome, not verbose narration
- make correlation and expiry mandatory before adding optional detail

### Position Messages

- send only fields needed for map display, routing context, or historical analysis
- avoid unnecessary precision if it does not improve the use case
- rate-limit periodic updates based on movement and actual need

## Recommended Payload Strategy

### Strategy 1: Compact Shared Envelope

Use one small common envelope for identity, timing, and routing, then keep message-class payloads compact.

### Strategy 2: Favor Delta-Oriented Thinking

When possible, send:

- a state change
- a threshold crossing
- a short summary

instead of:

- a full repeated snapshot
- a verbose event history
- large descriptive text

### Strategy 3: Optimize Frequency Before Compression

Before introducing compression or chunking:

- reduce message frequency
- reduce field count
- shorten field names or move to coded forms
- eliminate redundant metadata

Compression and chunking should be later tools, not first instincts.

## Message Frequency Guidance

### Human Ops

- user-driven
- naturally bursty
- should be protected from telemetry flooding

### Position Reports

- periodic
- should be tied to movement, not just time
- should support slower reporting for stationary nodes

### Sensor Reports

- periodic or threshold-driven
- should not send fast repeated updates unless the use case requires it
- should support local aggregation at the sensor or gateway if readings are noisy

### Control Traffic

- event-driven
- should be rare
- should never depend on repeated spam to achieve correctness

## When To Reject A Payload Design

A candidate message design should be rejected or revised if it:

- requires fragmentation in normal operation
- repeats static fields in every message without clear value
- depends on verbose text for machine interpretation
- assumes the broker path is the only bottleneck
- cannot survive retransmission without flooding the mesh

## Fragmentation And Large Payloads

Phase 1 should assume that large-payload transfer is out of scope unless proven necessary.

Reasons:

- fragmentation increases implementation complexity
- reassembly requires ordering, expiry, and integrity tracking
- partial loss creates ambiguous outcomes
- large transfers can dominate airtime and damage usability for human traffic

If later requirements force chunked transfer, the system will need:

- transfer ids
- chunk indexes and counts
- per-transfer expiry
- integrity checks
- duplicate suppression
- explicit queue and retry policy

That belongs to a separate task and should not leak into ordinary telemetry design.

## Field Budget Guidance

The protocol envelope and payloads should be designed in this order of priority:

1. source identity
2. message identity
3. timing and expiry
4. routing target or scope
5. the smallest payload body that still satisfies the use case
6. optional observability detail

If tradeoffs are required, optional detail should lose before identity or expiry semantics.

## Queueing And Replay Implications

Transport constraints do not end at transmission time. They also affect replay.

Implications:

- expired queued events should be dropped rather than replayed blindly
- replay must not starve fresh operator traffic
- replay order may need to favor control and alerts over stale telemetry

## Test Expectations

Every protocol or payload change should eventually be evaluated against:

- small single-hop lab cases
- noisier or multi-hop relay cases
- broker disconnect and replay cases
- mixed traffic cases where ops, telemetry, and control overlap

The goal is to validate not only correctness, but also whether the transport remains usable under realistic contention.

## Requirements Derived From These Constraints

- the shared application envelope must stay compact
- sensor and control schemas must be designed with explicit field economy
- periodic reporting features must expose rate and threshold controls
- replay policy must honor expiry and freshness
- large-payload transfer must remain a separate, explicitly justified feature

## Concerns

- overly optimistic lab tests can hide real-world airtime problems
- verbose payloads create operational pain long before they create obvious failures
- adding features at the payload layer without transport budgeting will degrade the mesh over time

## Missed Requirements To Resolve Later

- quantitative payload budgets by message class
- measured acceptable reporting intervals for each node type
- replay prioritization policy across `ops`, `sensor`, and `control`
- whether field names remain human-readable or become compact coded identifiers
