# h-mesh

Public design repository for a Meshtastic-based multi-site mesh deployment with internet-assisted site bridging, logging, and controlled automation.

## Documentation

- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Naming And Configuration](docs/naming-and-configuration.md)
- [Gateway Components](docs/component-gateway.md)
- [Radio Components](docs/component-radio.md)
- [Sensor Components](docs/component-sensor.md)
- [Cloud Components](docs/component-cloud.md)
- [Private Configuration](docs/private-configuration.md)

## Public Repo Rules

This repository is intended to be shared publicly.

- Keep topology, credentials, MQTT broker details, encryption material, and per-site deployment values out of source control.
- Commit examples, templates, and schemas only.
- Place real private values under `config/private/`, which is ignored by git.
