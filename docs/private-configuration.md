# Private Configuration

## Goal

This repository is intended to be public. Private deployment values must stay out of git history while still allowing repeatable builds and deployments.

## What Stays Private

- Meshtastic channel secrets and pre-shared keys
- MQTT broker endpoints, usernames, passwords, and certificates
- exact site addresses and coordinates
- device management credentials
- VPN details and firewall allowlists
- operator names, phone numbers, and contact routes
- hardware serial numbers if they reveal procurement or site details

## What Can Be Public

- redacted architecture diagrams
- component definitions
- naming standards
- sample config files with placeholder values
- provisioning checklists
- generic deployment scripts that read values from private files or environment variables

## Repository Pattern

Use this split:

- `config/examples/` for shareable templates
- `config/private/` for real deployment values

The public repo should never depend on committed secrets. Instead, scripts and services should load values from:

- environment variables
- local env files outside version control
- deployment-specific files under `config/private/`
- a dedicated secret manager, if added later

## Example Files

Public example:

```env
MQTT_HOST=example-broker
MQTT_PORT=8883
MQTT_USERNAME=replace-me
MQTT_PASSWORD=replace-me
SITE_CODE=a
GATEWAY_ID=ag01
```

Private file:

```env
MQTT_HOST=broker.example.net
MQTT_PORT=8883
MQTT_USERNAME=site_a_gateway
MQTT_PASSWORD=<real secret>
SITE_CODE=a
GATEWAY_ID=ag01
```

## Operational Rules

- never paste live secrets into markdown
- never commit screenshots that expose live channel or broker data
- rotate credentials if they are ever accidentally published
- keep private topology details in private deployment notes, not in public docs
