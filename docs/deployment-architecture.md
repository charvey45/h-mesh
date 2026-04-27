# Deployment Architecture

## Purpose

This document defines how `h-mesh` components are packaged, versioned, promoted, configured, and rolled back across lab, site-test, and production environments.

The deployment model intentionally treats the broker, gateways, radios, and custom sensors as different operational families. They do not share the same runtime shape, so they should not share a single deployment workflow.

## Deployment Families

### MQTT Infrastructure

MQTT infrastructure is the shared inter-site backbone. It should be managed as infrastructure plus runtime, not as an ad hoc host.

- infrastructure provisioning belongs in `Terraform`
- broker runtime belongs in a container image or system package
- runtime state such as retained topics or live sessions does not belong in `Terraform`
- DNS, certificates, storage, security groups, and backups do belong in `Terraform`

### Gateway Pis

Gateway Pis are application hosts. They run the bridge service, own the local queue database and logs, and carry site-specific runtime configuration.

- build and release the gateway software through GitHub Actions
- deploy versioned artifacts, not source checkouts
- keep the queue database and logs on persistent local storage
- keep live site configuration outside the public repository

### Radios

Meshtastic radios are configuration-managed devices, not general application hosts.

- manage firmware version
- manage channel and identity configuration
- manage GPS reporting and role settings
- do not treat a stock radio like a package deployment target

### Custom Sensors

Custom sensors are their own software family. Some may be microcontroller firmware, and others may be host-based applications running on Linux or another small system.

- build them as versioned artifacts
- keep private sensor code in private repositories when needed
- keep shared protocol and payload schemas in this design repository
- plan separate upgrade and rollback procedures per sensor type

## Recommended Repository Layout

Use multiple repositories with clear boundaries.

### `h-mesh`

Public design and shared implementation repository.

- architecture and protocol documentation
- gateway application code
- local lab Docker harnesses
- example configuration templates
- generic operator guides

### `h-mesh-infra`

Infrastructure-as-code repository for shared services.

- Terraform for MQTT host infrastructure
- DNS and certificate attachment points
- storage and backup policy
- monitoring and alerting infrastructure

### `h-mesh-private-config`

Private operational repository or secret-backed configuration source.

- site-specific `.env` files
- device inventory and assignment data
- broker credentials and certificate material references
- alert routes and operator contact data
- sensor threshold values if they expose site details

### Private Sensor Repositories

Create these only when sensor code has its own lifecycle.

- `h-mesh-sensor-basement`
- `h-mesh-sensor-relay`
- future hardware-specific sensor or actuator projects

## Versioning Model

Every deployable component should have an explicit version.

### Broker Runtime

- pin the broker container image tag
- pin the infrastructure module version
- track broker configuration revision separately from infrastructure revision when needed

### Gateway Application

- publish a versioned container image or package
- keep application version separate from site configuration revision
- record the running gateway version in health or management views when possible

### Radios

- track Meshtastic firmware version
- track channel/config profile revision
- track device identity assignment

### Custom Sensors

- publish a firmware or package version
- track schema compatibility with the gateway and downstream consumers

## Environment Promotion

Use three release lanes.

### Lab

- Docker-based local broker and simulated endpoints
- fast iteration
- disposable data
- suitable for protocol and dashboard validation

### Site-Test

- one broker path
- one or two real gateways
- controlled radios and sensors
- persistent data retained long enough to validate operational behavior

### Production

- live sites and real operators
- protected secrets
- rollback plan required before upgrade
- observability must already be in place

Promotion should be intentional:

1. validate locally in lab
2. promote the same version to site-test
3. observe broker health, queue depth, and logs
4. promote to production only after site-test behavior is stable

## Artifact Strategy

### Broker

- infrastructure artifact: Terraform plan and modules
- runtime artifact: pinned broker container image
- configuration artifact: broker config file or mounted config directory

### Gateway

- preferred artifact: container image published to GHCR
- acceptable Phase 1 artifact: Python package or release bundle
- persistent state remains outside the image on a mounted volume

### Sensor

- microcontroller sensor: firmware binary
- Linux-hosted sensor: container image or package

### Radio

- firmware image plus exported Meshtastic config profile

## Deployment Workflows

### MQTT Broker

- provision host, network, storage, and DNS in `Terraform`
- deploy the broker runtime with Docker on the target host
- keep broker data and config on persistent storage
- validate TLS, credentials, and topic policy before opening gateway access

For early lab work, a single Docker host is enough. For cloud production, the lowest-friction starting point is a small VM running Docker. ECS or another managed scheduler can come later if broker lifecycle management becomes more important than host simplicity.

### Gateway Pi

- build and release through GitHub Actions
- install a pinned artifact on the Pi
- place local state on a persistent volume or dedicated data directory
- load site-specific configuration from a private source
- restart under a service manager or container restart policy

### Custom Sensor

- build from its own private repository when required
- publish a release artifact
- deploy with a device-specific procedure
- validate payload shape against the shared application protocol

## Configuration And Secret Boundaries

Public repositories may contain:

- examples
- templates
- schemas
- public diagrams
- generic scripts that read from private config

Private repositories or secret stores may contain:

- real broker hostnames
- usernames and passwords
- certificate files and keys
- live site addresses or exact coordinates
- device-to-operator assignments

## Rollback Expectations

Every component needs a rollback path before production rollout.

### Broker

- previous container tag
- previous broker config revision
- infrastructure rollback plan for host or network changes

### Gateway

- previous image or package version
- preserved queue database
- preserved logs
- known-good site config revision

### Sensor

- previous firmware or package
- documented reflash or reinstall path

### Radio

- prior firmware image
- prior exported config profile

## Observability Requirements

Deployment health is not just “process started.”

Minimum management visibility should include:

- broker reachability
- gateway process state
- radio presence state
- queue depth
- recent publish and receive failures
- recent logs
- running software version where available

Future centralized archival can move logs to S3, but Phase 1 should assume local persistence first.

## Initial Implementation Plan

1. Use `Terraform` in `h-mesh-infra` to provision the MQTT host, storage, DNS, and security boundaries.
2. Run the broker as a pinned Docker container.
3. Release the gateway through GitHub Actions and publish artifacts to GitHub Releases or GHCR.
4. Keep private site configuration in `h-mesh-private-config` or an equivalent secret-backed source.
5. Manage radios through versioned firmware and config profiles.
6. Manage custom sensors through their own release artifacts and setup guides.
