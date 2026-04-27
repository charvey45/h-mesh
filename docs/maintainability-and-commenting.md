# Maintainability And Commenting

## Purpose

This repository prefers clear naming and strong structure, but it now intentionally leans toward verbose explanatory comments in operational code, scripts, and example configuration files.

The reason is practical: this project is expected to be operated, modified, and debugged by humans working across radios, Raspberry Pis, brokers, Docker stacks, and cloud infrastructure. In that kind of system, local explanation has real value.

## Comment Standard

Add comments generously when they explain something the code does not already make obvious:

- protocol or schema invariants
- failure-handling behavior
- lifecycle boundaries between broker, gateway, and radio concerns
- non-obvious data transformations
- safety or replay constraints
- why a deployment setting or compose dependency exists
- what an example config value means operationally
- how an operator should think about a script or command path

Verbose comments are especially encouraged in:

- runtime entrypoints
- service orchestration code
- storage and replay code
- Docker compose files
- example `.env` and YAML config files
- bootstrap and operator-facing scripts

Do not add comments that simply restate the code:

- `# increment count`
- `# assign variable`
- `# return result`

This is not a ban on detailed comments. It is a guardrail against low-value noise. The standard for this repository is "verbose and useful," not "minimal at all costs."

## Preferred Approach

Use this order of preference:

1. choose clear names
2. split long functions into smaller ones
3. document the public contract in repository docs
4. add local comments that explain intent, flow, and operational meaning
5. add config comments that help operators avoid misuse

## Repository Guidance

- architecture and operator behavior belong in `docs/`
- public schemas belong in the design documents
- setup and upgrade steps belong in operator guides
- code comments should stay close to the logic they explain
- scripts should explain what each phase is doing and why
- example config files should explain each setting well enough that an operator can edit them with confidence
