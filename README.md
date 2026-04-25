# h-mesh

[Meshtastic](https://meshtastic.org/)-based design for a multi-site mesh deployment with internet-assisted site bridging, logging, and controlled automation.

<p align="center">
  <img src="docs/assets/meshtastic-hero-crop.png" width="32%" alt="Meshtastic project imagery" />
  <img src="docs/assets/heltec-v3.png" width="32%" alt="Heltec WiFi LoRa 32 V3 product imagery" />
  <img src="docs/assets/raspberry-pi-4.png" width="32%" alt="Raspberry Pi 4 product imagery" />
</p>

Illustrative imagery in this repository is derived from the official Meshtastic, Heltec, and Raspberry Pi project and product pages.

## Design Overview

This design describes a [Meshtastic](https://meshtastic.org/) deployment that links separate physical [LoRa](https://www.semtech.com/lora) coverage areas through an internet backhaul while preserving local radio-first operation at each site.

The baseline model uses a Raspberry Pi and a USB-connected Heltec radio as the gateway at each fixed site. These gateway hosts handle bridge policy, logging, queueing, and controlled automation boundaries while the radios provide local RF access.

## Problem Statement

Many operating areas have strong local needs for off-grid communication but are split across multiple properties or work zones that cannot reach each other over [LoRa](https://www.semtech.com/lora) alone.

Field teams, equipment, and sensors need:

- local communication beyond Wi-Fi coverage
- inter-site communication when sites have internet but not RF line of sight
- GPS-aware node reporting for locating people and assets
- separation between chat, telemetry, and automation traffic
- a controlled path for machine actions such as supervised relay or contactor control

## Solution Design

The proposed solution combines:

- one local [Meshtastic](https://meshtastic.org/) mesh per site
- one Pi-assisted gateway per fixed site
- a private [MQTT](https://mqtt.org/) backbone for inter-site transport, where MQTT is a lightweight publish/subscribe messaging protocol commonly used in IoT systems
- per-channel policy for `ops`, `sensor`, and `control` traffic
- private deployment configuration separated from versioned examples and templates

## Documentation

- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Gateway Service Design](docs/gateway-service-design.md)
- [Application Protocol](docs\application-protocol.md)
- [Sensor And Control Schemas](docs/sensor-control-schemas.md)
- [Requirements Use Cases](docs/requirements-use-cases.md)
- [Naming And Configuration](docs/naming-and-configuration.md)
- [Gateway Components](docs/component-gateway.md)
- [Radio Components](docs/component-radio.md)
- [Sensor Components](docs/component-sensor.md)
- [Cloud Components](docs/component-cloud.md)
- [Private Configuration](docs/private-configuration.md)
