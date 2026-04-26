# Log Archival Requirements

## Purpose

This document defines how gateway log files can later be archived to [Amazon S3](https://aws.amazon.com/s3/) without changing the Phase 1 local dashboard model.

Phase 1 remains local-first:

- gateways write structured log files to a persistent local path
- the management dashboard reads those local files directly
- log archival is an asynchronous copy path, not the primary operator path

## Design Goals

- keep the gateway write path simple and local
- avoid making S3 availability a runtime dependency for the gateway
- preserve local troubleshooting when internet access is degraded
- support low-cost retention of older logs outside the Pi local volume
- make archival additive so the dashboard does not need to change

## Phase Boundary

The design is intentionally split into two layers:

1. Local runtime layer
   - gateway writes `*.log` files into the shared state path
   - dashboard reads recent local logs from that same path
   - local volume sizing covers short-term operator use
2. Archival layer
   - a separate process copies rotated or aged logs to S3
   - archival failure does not block gateway logging
   - recovery is based on retrying file uploads, not replaying MQTT traffic

## Required Log Layout

To make archival deterministic, each gateway log file should follow a stable naming pattern:

- `<gateway_id>.log` for the active log
- `<gateway_id>-YYYYMMDD-HHMMSS.log` for rotated files

Examples:

- `ag01.log`
- `bg02-20260426-230000.log`

This keeps the active file predictable for the dashboard while giving the archival process immutable rotated files to upload.

## S3 Object Layout

Archived objects should use a path that keeps site, gateway, and date-based retrieval simple:

```text
s3://<bucket>/gateway-logs/site=<site_code>/gateway=<gateway_id>/year=<yyyy>/month=<mm>/day=<dd>/<filename>
```

Example:

```text
s3://h-mesh-logs/gateway-logs/site=a/gateway=ag01/year=2026/month=04/day=26/ag01-20260426-230000.log
```

Requirements for the object layout:

- path must be derivable from local filename and gateway id alone
- object keys must be immutable after upload
- date partitions must support low-cost lifecycle rules and selective retrieval

## Archival Trigger Model

Archival should operate on rotated files, not the active log file.

Required behavior:

- the active `*.log` file stays local and writable
- only closed, rotated files are candidates for S3 upload
- uploads are retried independently of gateway message processing
- an uploaded file is marked locally so it is not repeatedly re-sent

Recommended first implementation:

- rotate locally by size or age
- run a lightweight sidecar or scheduled job on the Pi
- upload eligible rotated files with idempotent overwrite-safe semantics

## Local Metadata Requirements

The archival process needs a small local manifest or SQLite table to track:

- local filename
- file size
- last modified timestamp
- archive status such as `pending`, `uploaded`, or `failed`
- upload attempt count
- most recent error text
- S3 object key
- archived timestamp

This metadata is operational state only. The log file remains the source artifact.

## Failure Handling

S3 archival must degrade cleanly under normal edge failures.

Required behavior:

- if internet access is down, logs continue writing locally
- if S3 credentials are broken, the gateway and dashboard continue operating
- if archival is backlogged, operators can still inspect recent local logs
- if the local disk approaches capacity, the system must surface a local health signal before logs are lost

Operational consequence:

- log archival backlog is a management concern
- it is not allowed to break gateway MQTT relay behavior

## Retention Model

Phase 1 local retention and later S3 retention serve different purposes.

Local retention should cover:

- recent troubleshooting
- dashboard log browsing
- temporary WAN outage during archival backlog

S3 retention should cover:

- historical troubleshooting
- incident research
- movement or telemetry investigations that need correlated gateway logs

Recommended baseline:

- local volume: 7 to 14 days, sized for worst-case log growth
- S3: 90 days in standard storage, then lifecycle transition to a cheaper class if historical access remains useful

Exact retention values should stay in private deployment configuration.

## Security Requirements

The archival path introduces cloud credentials and needs explicit boundaries.

Required controls:

- the gateway service itself should not require S3 permissions
- archival credentials should be scoped to write only into the designated bucket prefix
- bucket access should default to private
- object encryption at rest should be enabled
- uploads and failures should be logged locally for auditability

If AWS-native execution is introduced later, IAM role-based access is preferred over long-lived access keys.

## Cost And Simplicity Guidance

For low-cost AWS usage:

- prefer one S3 bucket with prefix partitioning over many buckets
- use lifecycle rules instead of manual cleanup
- avoid streaming every log line directly to S3 in Phase 1
- upload whole rotated files rather than per-event objects

This keeps request volume and implementation complexity down while preserving operator usefulness.

## Out Of Scope

This document does not introduce:

- centralized search across archived logs
- a hosted observability vendor
- broker-native MQTT metrics export
- cloud-only logging that replaces the local volume

Those can be added later, but they are not required for the first archival step.

## Acceptance Criteria

The archival design is acceptable when:

- local gateway logging still works with no S3 connectivity
- the dashboard still reads local logs with no dependency on S3
- rotated files can be uploaded later without changing gateway message flow
- archival backlog and failures can be surfaced as health signals
- private AWS details such as bucket names and credentials stay out of versioned example config
