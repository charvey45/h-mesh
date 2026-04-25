# Position Persistence

## Purpose

This document defines the persistence requirements for current and historical position tracking in the multi-site Meshtastic design.

The key architectural decision is that **current map state** and **historical movement history** are different products with different storage and retention needs. They should not be treated as the same data structure with two query styles layered on top.

## Scope

This document applies to position-bearing nodes such as:

- handheld radios
- vehicle radios
- equipment-attached radios
- tracker-style devices

It covers:

- ingestion of position events
- last-known state storage
- historical movement storage
- retention and privacy concerns
- query expectations

It does not define the RF reporting intervals themselves. That belongs to transport and reporting policy.

## Core Decision

Use two persistence models:

### Current Position Store

One record per tracked node representing the latest trusted position.

Use cases:

- render the operator map
- show current status for a node
- answer "where is it now"

### Historical Position Store

Append-only time-series records of prior observations.

Use cases:

- movement review
- route reconstruction
- dwell analysis
- incident and research analysis
- last known location before loss of contact

## Ingestion Flow

1. a `position_report` arrives at a gateway
2. the event is validated
3. the event is written to `message_events`
4. the current position store is upserted for the node
5. the historical position store is appended
6. optional replication or forwarding occurs for cross-site visibility

The current and historical writes should be treated as one logical ingest step even if they land in different tables or systems.

## Current Position Requirements

### Purpose

Current position storage exists to answer operator-facing questions quickly.

### Minimum Fields

- `node_id`
- `site`
- `lat`
- `lon`
- `captured_at`
- `observed_by`
- `precision_m`
- `speed_mps`
- `heading_deg`
- `battery_pct`

### Behavior

- one active row per node
- overwrite only when the incoming event is newer and trusted
- retain the last observation even when the node stops reporting
- expose freshness so stale current positions are visible as stale

### Freshness Requirement

The current position view must include enough metadata to distinguish:

- current and healthy
- current but stale
- unknown or never seen

This means the UI or downstream consumers need at least:

- last update timestamp
- age of last report
- optional gateway/source health context

## Historical Position Requirements

### Purpose

Historical position storage exists to answer analytical questions over time.

### Minimum Fields

- `event_id`
- `node_id`
- `site`
- `captured_at`
- `lat`
- `lon`
- `alt_m`
- `precision_m`
- `speed_mps`
- `heading_deg`
- `battery_pct`
- `observed_by`

### Behavior

- append-only by default
- preserve original capture timestamp
- support efficient time-range queries by node
- support cross-node queries for a site and time window

### Analytical Queries To Support

- where was `br03` between `14:00` and `15:00`
- what was the last known location before disconnect
- how often did a node enter a given zone
- how long was a node stationary

## Trust And Ordering Rules

### Newer Wins For Current State

An incoming event should replace current state only when it is newer than the stored current observation, subject to trust checks.

### Clock Drift Matters

Nodes, gateways, and cloud services may not share perfect clocks.

Requirements:

- preserve the original event timestamp
- preserve gateway observation time when available
- document which timestamp is authoritative for current-state replacement

### Duplicate Handling

The same position event may be seen multiple times because of replay or relay behavior.

Requirements:

- deduplicate by stable event id where possible
- avoid writing duplicate history rows when the same event is observed more than once

## Candidate Storage Shape

### `positions_current`

Candidate columns:

- `node_id`
- `site`
- `lat`
- `lon`
- `alt_m`
- `precision_m`
- `speed_mps`
- `heading_deg`
- `battery_pct`
- `captured_at`
- `observed_by`
- `updated_at`
- `stale_after`

### `positions_history`

Candidate columns:

- `event_id`
- `node_id`
- `site`
- `lat`
- `lon`
- `alt_m`
- `precision_m`
- `speed_mps`
- `heading_deg`
- `battery_pct`
- `captured_at`
- `observed_by`
- `stored_at`

## Ownership Model

Phase 1 should allow for either of these deployment patterns:

### Gateway-Owned Current State With Central Replication

- each gateway maintains a local current-state cache
- a central service may replicate or aggregate for cross-site visibility

### Central Current State And Central History

- gateways forward validated position events
- a central service owns map-ready current state and history

The design requirement is not that one model must win today. The requirement is that the event model and storage shape support either path without data loss.

## Recommended Near-Term Direction

For the current architecture, the practical default is:

- gateway writes local current and history records when it observes position events
- a central service may later aggregate those events for a fleet-wide map and cross-site analysis

This preserves local usefulness while not blocking later centralization.

## Retention Requirements

### Current Position

- retain indefinitely while the node is active in inventory
- stale rows remain visible until explicitly retired or archived

### Historical Position

Retention is an open policy decision, but the design must support:

- finite retention windows
- archiving
- optional down-sampling for older data

At minimum, the design should allow configuration of:

- raw retention window
- archive retention window
- down-sample cadence for older records

## Privacy And Governance

Historical movement data is more sensitive than current operator convenience data.

Requirements:

- document who can query historical movement
- document retention policy explicitly
- support deletion or retirement when a node leaves service
- avoid keeping unnecessary precision or retention if the use case does not require it

## Query Requirements

The persistence layer should support these classes of query:

### Current State Queries

- current position by node id
- all currently known positions for a site
- all stale positions for a site

### Historical Queries

- movement history by node and time range
- last known observation before a time boundary
- all node observations in a site during a time window

### Derived Analytics

The design should not block later calculations such as:

- dwell time
- path reconstruction
- zone transitions
- inactivity detection

## Concerns

- history volume may grow quickly for frequently reporting nodes
- inaccurate GPS fixes can pollute both map state and historical analysis
- a current-state-only implementation will look fine in demos but fail later research needs
- a history-only implementation will make map views unnecessarily expensive

## Missed Requirements

- exact stale timeout policy for current positions
- exact historical retention periods
- down-sampling policy for long-lived history
- zone or geofence model for later movement analytics
- whether battery and speed belong in history for all nodes or only mobile ones

## Open Decisions

- whether the authoritative current-state store is local, central, or both
- whether historical records remain only on gateways, only centrally, or replicated
- whether privacy policy requires precision reduction after a retention threshold
- whether invalid identifiers are rejected immediately or mapped through an inventory alias table

## Exit Criteria For This Task

This task is complete when the design defines:

- separate current and historical position persistence requirements
- minimum field sets for both stores
- current-state freshness expectations
- historical query and retention expectations
- governance and privacy concerns around movement history
