# Operator Guide: Custom Sensors

## Scope

This guide covers setup and upgrade flow for custom sensors that publish into the `h-mesh` system.

## Deployment Shape

A custom sensor may be:

- microcontroller firmware
- a Linux-hosted process
- a simulated lab publisher

Treat each sensor family as its own software lifecycle.

## Prerequisites

- assigned sensor identifier such as `bs01`
- defined payload schema and threshold expectations
- private configuration for any broker or gateway access needed by the sensor
- hardware wiring or host runtime prepared for the specific sensor

## Initial Setup

1. Build or download the approved release artifact from the private sensor repository.
2. Apply the sensor identifier and site assignment.
3. Install runtime configuration from the private deployment source.
4. Validate that the published payload matches the shared schema.
5. Verify that the receiving gateway records the event.
6. Verify any alert threshold behavior in a test path before production use.

## Validation Checklist

- message `msg_type` and `channel` match the intended design
- source identity is correct
- timestamps are valid
- payload size respects transport constraints
- downstream storage and alert paths receive the event

## Upgrade Procedure

1. Review release notes for payload or threshold compatibility changes.
2. Back up any local sensor config if the device stores it.
3. Install the new artifact.
4. Run a controlled publish test.
5. Confirm dashboard visibility and downstream storage behavior.

## Rollback Procedure

1. Reinstall the previous firmware or package.
2. Restore prior configuration.
3. Re-run a controlled publish test.

## Operational Notes

- keep private sensor code out of the public repo when needed
- keep shared schemas and public integration docs in this repo
- do not allow custom sensors to bypass the documented message envelope without an explicit design decision
