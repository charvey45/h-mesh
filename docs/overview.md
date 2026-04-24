# Overview

## Purpose

This project defines a Meshtastic deployment that supports communication across multiple physical sites that are not within direct LoRa radio range of each other.

Each site runs a local RF mesh for nearby radios, sensors, and mobile devices. Site gateway components bridge selected traffic over the internet so users and systems at one site can exchange messages with another site.

## Phase 1 Scope

Phase 1 assumes fixed gateway nodes at Site A and Site B:

- `agxx` devices are site gateway radios attached to Raspberry Pi hosts.
- `brxx`, `arxx`, and similar devices are general radios used by people, vehicles, and equipment.
- `asxx`, `bsxx`, and similar devices are sensor-focused nodes.
- Cloud services are represented under site code `c`.

Site C is reserved for a later mobile gateway model where a Wi-Fi capable Meshtastic device may bridge traffic directly without a Raspberry Pi.

## Primary Goals

- Bidirectional communication between separate physical sites.
- Local communications when internet is unavailable inside a site.
- GPS-aware field devices for locating people and equipment.
- Separation of human, sensor, and automation traffic.
- Pi-assisted logging, policy enforcement, and WAN outage queueing.
- Public documentation with private configuration kept outside version control.

## Channel Model

The design starts with three logical communication classes:

- `ops`: ad hoc communication for people and general field operations
- `sensor`: telemetry, status, and low-rate machine data
- `control`: automation and command traffic with stricter policy enforcement

These classes may map to one or more Meshtastic channels during implementation.

## Design Principles

- Keep the RF side simple and durable.
- Centralize policy and buffering on the Raspberry Pi gateway hosts.
- Treat automation as supervised control, not as raw packet forwarding.
- Make public documentation safe to share by separating examples from live values.
- Use a short, human-readable device code that also supports inventory tracking.
