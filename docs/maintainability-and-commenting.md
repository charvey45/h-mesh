# Maintainability And Commenting

## Purpose

This repository prefers clear naming and strong structure, while still preserving enough local explanation for humans and AI systems to understand operational intent.

The practical rule is:

- Python code should follow a `PEP 8` layout and `PEP 257` docstring style.
- Heavy explanation in Python should primarily live in module, class, and function docstrings.
- Inline comments should remain for non-obvious local logic only.
- Config files, Docker files, and operator-facing examples can stay heavily commented.

## Comment Standard

Add explanation generously when it helps, but use the Python-native form for Python files:

- module docstrings for system role and design context
- class docstrings for ownership, invariants, and boundaries
- function or method docstrings for behavior, inputs, outputs, and failure modes
- inline comments only when the local control flow is still non-obvious

Useful explanation targets include:

- protocol or schema invariants
- failure-handling behavior
- lifecycle boundaries between broker, gateway, and radio concerns
- non-obvious data transformations
- safety or replay constraints
- why a deployment setting or compose dependency exists
- what an example config value means operationally
- how an operator should think about a script or command path

Heavy explanation is especially encouraged in:

- runtime entrypoints
- service orchestration code
- storage and replay code
- Docker compose files
- example `.env` and YAML config files
- bootstrap and operator-facing scripts

Do not add comments or docstrings that simply restate the code:

- `# increment count`
- `# assign variable`
- `# return result`

This is not a ban on detail. It is a guardrail against low-value noise. The standard for Python is "docstring-heavy and useful," not "narrative comments on every block."

## Preferred Approach

Use this order of preference:

1. choose clear names
2. split long functions into smaller ones
3. document the public contract in repository docs
4. use docstrings to explain module, class, and function intent
5. add local inline comments only where logic is subtle
6. add config comments that help operators avoid misuse

## Repository Guidance

- architecture and operator behavior belong in `docs/`
- public schemas belong in the design documents
- setup and upgrade steps belong in operator guides
- Python modules should prefer docstrings over narrative block comments
- inline comments should stay close to the logic they explain
- scripts should explain what each phase is doing and why
- example config files should explain each setting well enough that an operator can edit them with confidence
