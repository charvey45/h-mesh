# Architecture

## System Context

The system consists of one or more independent local Meshtastic meshes connected by an internet backbone.

- Each physical site has local radios and sensors.
- Each fixed site has one Raspberry Pi-assisted gateway pair composed of a Pi and a USB-connected Heltec ESP32 V3.
- A private MQTT broker provides inter-site backhaul.
- Optional cloud services provide centralized logging, dashboards, backups, and management tooling.

## Diagram

```mermaid
flowchart LR
  subgraph SA[Site A]
    AR[Field Radios<br/>arxx]
    AS[Sensor Nodes<br/>asxx]
    AGR[Gateway Radio<br/>agxx]
    AGP[Gateway Pi<br/>logging queue policy]
    AR <-- LoRa --> AGR
    AS <-- LoRa --> AGR
    AGR <-- USB Serial --> AGP
  end

  subgraph SB[Site B]
    BR[Field Radios<br/>brxx]
    BS[Sensor Nodes<br/>bsxx]
    BGR[Gateway Radio<br/>bgxx]
    BGP[Gateway Pi<br/>logging queue policy]
    BR <-- LoRa --> BGR
    BS <-- LoRa --> BGR
    BGR <-- USB Serial --> BGP
  end

  subgraph SC[Cloud]
    MQTT[Private MQTT Broker<br/>cgxx]
    OBS[Optional Logging Dashboards Backups]
  end

  AGP <-- MQTT over Internet --> MQTT
  BGP <-- MQTT over Internet --> MQTT
  MQTT --- OBS
```

## Reference Hardware

<p align="center">
  <img src="assets/heltec-v3.png" width="48%" alt="Heltec WiFi LoRa 32 V3 product imagery" />
  <img src="assets/raspberry-pi-4.png" width="48%" alt="Raspberry Pi 4 product imagery" />
</p>

The reference fixed-site gateway pairs a Raspberry Pi host with a Heltec ESP32 V3 radio. Meshtastic provides the RF mesh behavior while the Pi hosts queueing, logging, and bridge policy.

## Logical Flow

1. A local node transmits over LoRa on the relevant site mesh.
2. The site gateway radio receives the packet.
3. The attached Raspberry Pi classifies the packet by channel, origin, and policy.
4. If the packet is approved for inter-site forwarding, the Pi publishes it to the private MQTT broker.
5. Remote site gateways subscribe to the broker, apply local policy, and inject approved traffic into their local mesh.
6. If the WAN path is unavailable, the Pi queues eligible inter-site traffic for later replay.

## Site Layout

Each fixed site contains these major elements:

- RF nodes: handheld, vehicle, equipment, sensor, and fixed radios
- Gateway radio: fixed Meshtastic radio with stable power and antenna placement
- Gateway host: Raspberry Pi responsible for logging, queueing, and bridge policy
- Local LAN/Wi-Fi: path from the Pi to the internet backbone

## Functional Boundaries

### Meshtastic Radio

- Participates in the local LoRa mesh
- Transmits and receives site traffic
- Exposes a serial interface to the gateway host
- Maintains the on-air channel configuration required for its role

### Gateway Pi

- Maintains a serial link to the local gateway radio
- Logs packets, node updates, and position data
- Applies per-channel forwarding policy
- Queues outbound inter-site traffic when WAN is unavailable
- Replays queued traffic after broker connectivity is restored
- Provides a controlled boundary between mesh traffic and any automation outputs

### MQTT Backbone

- Moves selected messages between sites
- Decouples site availability from cloud availability
- Allows future addition of cloud-side consumers, dashboards, and audit services

## Channel Separation

### Ops

- Human-to-human communication
- Direct messages and group traffic
- Highest priority for usability

### Sensor

- Telemetry and status messages
- Lower priority than human communication
- Good candidate for aggregation and rate limiting on the Pi

### Control

- Automation requests and acknowledgements
- Strictly filtered and logged
- Must not directly energize high-current hardware without host-side validation

## Reliability Model

- Local RF operation continues even if WAN is lost.
- Inter-site forwarding pauses when the broker or WAN path is unavailable.
- Gateway Pi hosts persist queued inter-site traffic for later replay.
- Queueing policy should prefer bounded retention over unbounded growth.

## Security Model

- Live credentials and keys are private deployment data.
- Versioned content includes schemas, templates, and examples only.
- Control traffic is subject to stricter policy than chat or telemetry traffic.
- Cloud and site services use separate credentials and should support credential rotation.

## Example Deployment

- Site A fixed gateway: `ag01`
- Site B fixed gateway: `bg02`
- Site A handheld radio: `ar10`
- Site B equipment radio: `br11`
- Site A sensor node: `as20`
- Cloud MQTT broker service: `cgf0`

The serial suffix remains globally unique across the fleet.
