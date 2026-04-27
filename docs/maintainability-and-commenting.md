# Maintainability And Commenting

## Purpose

This repository prefers documentation, clear naming, and targeted comments over line-by-line commentary.

## Comment Standard

Add comments when they explain something the code does not already make obvious:

- protocol or schema invariants
- failure-handling behavior
- lifecycle boundaries between broker, gateway, and radio concerns
- non-obvious data transformations
- safety or replay constraints

Do not add comments that simply restate the code:

- `# increment count`
- `# assign variable`
- `# return result`

Line-by-line comments on every statement create a larger maintenance burden than the code itself. They drift quickly, hide the real structure of the module, and make reviews harder.

## Preferred Approach

Use this order of preference:

1. choose clear names
2. split long functions into smaller ones
3. document the public contract in repository docs
4. add short comments only where the local control flow still needs explanation

## Repository Guidance

- architecture and operator behavior belong in `docs/`
- public schemas belong in the design documents
- setup and upgrade steps belong in operator guides
- code comments should stay close to the non-obvious logic they explain
