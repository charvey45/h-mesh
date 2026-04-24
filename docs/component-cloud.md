# Cloud Components

## Purpose

Cloud components provide shared services that are not tied to a single physical RF site.

Cloud components use site code `c`.

## Component Family

Examples:

- `cgf0` = primary MQTT broker or integration host
- `cgf1` = backup integration or observability host

## Core Services

### MQTT Broker

- private inter-site message transport
- isolated from public Meshtastic infrastructure
- reachable from each participating site gateway

### Observability

- central log collection
- queue health reporting
- gateway heartbeat tracking
- retained audit trail for automation commands

### Management

- configuration template storage
- backup target for gateway exports
- optional dashboards and operator tools

## Placement Options

- small VPS with a public IP
- hosted service with restricted access
- self-hosted server at a trusted site if its uptime is sufficient for the deployment

For Phase 1, an external VPS is preferred because it avoids making Site A or Site B the single point of failure for all inter-site traffic.

## Security Expectations

- use separate credentials for broker clients and operators
- support credential rotation
- restrict network exposure to required services only
- do not commit real cloud hostnames, addresses, or credentials to the public repository

## Naming Guidance

Cloud services that behave as shared transport or integration infrastructure may use the `cgxx` pattern until a larger service taxonomy is needed.
