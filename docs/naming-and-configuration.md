# Naming And Configuration

## Device Code Format

Every managed device receives a 4-character code:

`[site][type][serial-hi][serial-lo]`

Examples:

- `ag01`
- `br1f`
- `dsa2`
- `cgf0`

## Character Definitions

### Character 1: Site

- `a`, `b`, `d`, `e`, and other letters identify physical sites
- `c` is reserved for cloud-hosted components

### Character 2: Device Type

- `g` = gateway
- `r` = radio
- `s` = sensor

### Characters 3-4: Serial

- Two hexadecimal characters from `00` through `ff`
- The 2-character serial suffix is globally unique across the full deployment
- A serial suffix is assigned once and never reused for another device

This means only one device in the fleet may use `01`, regardless of site or type. The full code remains human-readable while the suffix acts as the fleet-wide asset number.

## Naming Rules

- Use lowercase letters for the device code
- Keep the device code stable for the life of the device
- Reflect the same code in labels, inventory, and documentation
- Prefer the device code as the Meshtastic operational name where supported

## Intended Config Mapping

The device code should map into Meshtastic-facing metadata and inventory records:

- short operational name: the 4-character code
- long operational name: a descriptive label such as `Site A Gateway North Barn`
- inventory record: hardware type, antenna, install location, and owner

The exact Meshtastic fields used for this mapping should be confirmed during implementation, but the 4-character code is the canonical identifier in this repository.

## Channel Assignment Model

Not every device joins every channel.

### Typical Membership

- Gateways: `ops`, `sensor`, `control`
- General radios: `ops`
- Equipment radios: `ops`, optionally `sensor`
- Sensor nodes: `sensor`, optionally `control` for acknowledgements only

### Primary Rule

Use one channel as the general-purpose default for field devices and install secondary channels only where required by function.

## Public vs Private Configuration

Public repository content may include:

- config schemas
- sample YAML, JSON, or env files
- deployment checklists
- redacted example topologies

Private deployment content must stay outside git history:

- broker hostnames and credentials
- channel keys and pre-shared keys
- exact site coordinates
- alert endpoints
- per-site network details
- operator contact information

## Suggested Repository Layout

```text
config/
  examples/
    site.env.example
    gateway-policy.example.yaml
    channels.example.yaml
  private/
    a/
    b/
    cloud/
```

`config/private/` is intentionally gitignored.
