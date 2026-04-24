# Sensor Components

## Purpose

Sensor components provide telemetry, status, and low-rate machine communication into the site mesh.

## Component Family

This document covers all `?sxx` devices:

- environmental sensors
- equipment health monitors
- fixed telemetry nodes
- low-rate automation endpoints that report state

Examples:

- `as20`
- `bs21`
- `ds7e`

## Primary Use Cases

- report environmental values
- report equipment state or fault conditions
- provide lightweight remote observability in areas without Wi-Fi or cellular coverage
- support position reporting for mobile assets when needed

## Channel Participation

- `sensor` is the default channel
- `control` is optional and should be restricted to devices that genuinely need command acknowledgement paths
- `ops` is usually unnecessary unless the node also serves a human-facing role

## Design Constraints

- low power operation may be more important than responsiveness
- message rate should be bounded to protect airtime
- local buffering may be required if a sensor generates bursts faster than the mesh should carry
- sensor payloads should be normalized by the gateway or cloud services before long-term storage

## Automation Boundary

Sensor nodes may observe or report automation state, but command authorization should terminate at the gateway host or another supervised controller.

If a sensor-adjacent device must actuate hardware, document it as a controlled automation endpoint and apply the same policy standards as gateway-side control logic.

## Installation Notes

- locate antennas for reliable local coverage, not just device convenience
- document power source, service interval, and physical mount in private deployment records
- keep calibration and maintenance details out of versioned docs if they expose site-sensitive information
