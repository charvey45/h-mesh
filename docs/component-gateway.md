# Gateway Components

## Purpose

Gateway components bridge a local [Meshtastic](https://meshtastic.org/) RF mesh to the inter-site internet path. In Phase 1, each gateway is a Raspberry Pi host attached by USB to a Heltec ESP32 V3 radio.

## Component Family

This document covers all `?gxx` devices, including:

- `ag01`
- `bg02`
- future fixed gateways at other sites
- cloud-adjacent gateway or integration hosts using the `cgxx` pattern where needed

## Physical Composition

- Raspberry Pi with stable power and storage
- Heltec ESP32 V3 connected by USB
- Fixed antenna installation appropriate for the site
- Local LAN or Wi-Fi connectivity for WAN access
- Optional UPS or battery backup

## Responsibilities

### Gateway Radio

- Participate in local [LoRa](https://www.semtech.com/lora) mesh traffic
- Receive and transmit on the channels assigned to the gateway role
- Provide the RF entry and exit point for inter-site traffic

### Gateway Pi

- Run bridge software that speaks to the radio over serial
- Log packets, positions, and node state changes
- Enforce message forwarding rules
- Persist queued outbound traffic during WAN outages
- Replay queued traffic after recovery
- Expose health metrics and operational logs

## Software Functions

- serial radio interface
- local packet log store
- durable inter-site queue
- MQTT publisher and subscriber
- policy engine for channel and sender filtering
- optional local API or dashboard
- optional relay/control adapter process

## Control Safety

Gateway hosts may support automation workflows, but they must never forward arbitrary packets directly into high-current hardware actions.

A gateway host controlling a relay or contactor should:

- validate the sender identity and message class
- require an allowlisted command format
- log every request and result
- apply local interlocks and timeout limits
- default to fail-safe behavior on reboot or software crash

## Availability Expectations

- One fixed gateway per site for initial deployment
- Stable power and networking
- Persistent local storage for logs and queued messages
- Recover automatically after power interruption

## Example Naming

- `ag01` = Site A fixed gateway
- `bg02` = Site B fixed gateway
- `cgf0` = cloud-hosted integration service using the gateway code family
