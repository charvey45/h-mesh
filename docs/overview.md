# Overview

<p align="center">
  <img src="assets/meshtastic-hero-crop.png" width="32%" alt="Meshtastic project imagery" />
  <img src="assets/heltec-v3.png" width="32%" alt="Heltec WiFi LoRa 32 V3 product imagery" />
  <img src="assets/raspberry-pi-4.png" width="32%" alt="Raspberry Pi 4 product imagery" />
</p>

Illustrative imagery in this repository is derived from the official Meshtastic, Heltec, and Raspberry Pi project and product pages.

## Design Overview

This design defines a [Meshtastic](https://meshtastic.org/) deployment that supports communication across multiple physical sites that are not within direct [LoRa](https://www.semtech.com/lora) radio range of each other.

Each site runs a local RF mesh for nearby radios, sensors, and mobile devices. Site gateway components bridge selected traffic over the internet so users and systems at one site can exchange messages with another site.

The reference fixed-site model uses Raspberry Pi-assisted gateways with USB-connected Heltec radios. A later mobile gateway variant can use a Wi-Fi capable Meshtastic node directly when a separate host is not needed.

## Problem Statement

The design addresses an operating environment where:

- work areas are larger than the coverage of local Wi-Fi or cellular service
- teams and equipment still need low-power field communication
- multiple sites have internet access but are outside each other's [LoRa](https://www.semtech.com/lora) RF range
- operators need to locate radios, vehicles, people, or assets by position reporting
- telemetry and automation messages should not be mixed indiscriminately with human chat traffic

## Solution Design

The solution combines four layers:

### Local RF Mesh

- handheld radios
- vehicle and equipment radios
- fixed radios
- sensor nodes

### Site Gateway

- a fixed [Meshtastic](https://meshtastic.org/) gateway radio
- a Raspberry Pi host for serial integration, policy, logging, and queueing

### Inter-Site Backbone

- private [MQTT](https://mqtt.org/) transport for lightweight publish/subscribe message exchange between site gateways
- optional cloud-hosted logging and observability

### Controlled Automation Boundary

- policy enforcement on the gateway host
- explicit separation between telemetry and command traffic
- supervised control for relay and contactor actions

## Goals

- bidirectional communication between separate physical sites
- local communications when internet is unavailable inside a site
- GPS-aware field devices for locating people and equipment
- separation of human, sensor, and automation traffic
- Pi-assisted logging, policy enforcement, and WAN outage queueing
- maintainable naming and configuration patterns across the fleet

## Channel Model

The design starts with three logical communication classes:

- `ops`: ad hoc communication for people and general field operations
- `sensor`: telemetry, status, and low-rate machine data
- `control`: automation and command traffic with stricter policy enforcement

These classes may map to one or more [Meshtastic](https://meshtastic.org/) channels during implementation.

## Design Principles

- Keep the RF side simple and durable.
- Centralize policy and buffering on the Raspberry Pi gateway hosts.
- Treat automation as supervised control, not as raw packet forwarding.
- Keep live deployment secrets and site-specific values outside versioned example files.
- Use a short, human-readable device code that also supports inventory tracking.
