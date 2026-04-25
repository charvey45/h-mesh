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
- may be exposed over IPv4, IPv6, or dual-stack networking because gateway connectivity is handled by the Raspberry Pi host rather than the Meshtastic radio

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
- small VPS with public IPv4, IPv6, or dual-stack access
- hosted service with restricted access
- self-hosted server at a trusted site if its uptime is sufficient for the deployment

For Phase 1, an external VPS is preferred because it avoids making Site A or Site B the single point of failure for all inter-site traffic.

## Addressing Note

If the MQTT broker is hosted on AWS and exposed over IPv6, the design still works normally. The important requirement is that each site gateway Pi can establish IP connectivity to the broker. Meshtastic remains the local RF transport, while IPv6 applies only to the internet-facing broker connection.

## Security Expectations

- use separate credentials for broker clients and operators
- support credential rotation
- restrict network exposure to required services only
- do not commit real cloud hostnames, addresses, or credentials to version control

## Naming Guidance

Cloud services that behave as shared transport or integration infrastructure may use the `cgxx` pattern until a larger service taxonomy is needed.
