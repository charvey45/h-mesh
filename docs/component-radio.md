# Radio Components

## Purpose

Radio components provide human communication and general field connectivity within a local site mesh.

## Component Family

This document covers all `?rxx` devices, regardless of site:

- handheld radios
- vehicle-mounted radios
- equipment-attached radios
- fixed support radios that are not the designated site gateway

Examples:

- `ar10`
- `br11`
- `dr8a`

## Primary Use Cases

- person-to-person messaging
- coordination between field teams and the fixed site gateway
- status communication from equipment that needs a user-facing radio presence
- position reporting for people or mobile assets when GPS is installed

## Expected Characteristics

- battery or vehicle power
- mobile or semi-mobile installation
- participation in the `ops` channel by default
- optional participation in `sensor` when equipment telemetry is needed

## Configuration Guidelines

- keep the default channel set minimal
- install only the channels required by the role
- use the 4-character device code for labels and operational naming
- document antenna, power, and mounting decisions in private deployment records

## GPS Considerations

Mobile radios intended for personnel or asset location should include a position source appropriate to the environment.

Examples:

- integrated GPS-capable radio configuration
- attached GPS module
- paired client device for temporary field use

Unattended radios should not depend on a phone for position reporting.

## Non-Goals

General radios should not:

- act as the primary inter-site gateway
- host automation policies
- control high-current hardware directly
- carry private deployment credentials beyond what is required for their on-air channel membership
