# Architecture reading map

Mechanism-level reference for pplx-tools (`pplx-export` / `pplx-ask`):
dependencies, pipelines, state machines, data contracts, and reliability
boundaries. For task-oriented usage, start with the [User guide](../guide/index.md).

!!! note "Scope and source of truth"

    These pages explain the architecture of `pplx_export/` for agents and
    engineers maintaining the project. Line references use `file.py:NN`,
    relative to `pplx_export/`. The descriptions were checked against the
    repository on 2026-07-23 (`__version__ = "0.1.0"`,
    `pplx_export/__init__.py:31`); current code and tests remain authoritative.

## Start with the system map

- [Architecture overview](overview.md) — layers, module responsibilities, and
  the import-level dependency graph.

## Follow a runtime flow

- [Export pipeline](export-pipeline.md) — fetching, raw-response retention,
  mode detection, and Markdown rendering.
- [Sub-agents and interruptions](subagents-interruptions.md) — payload
  attribution and interruption/resume semantics.
- [pplx-ask and accounts](ask-and-accounts.md) — streaming queries and
  multi-account cookie switching.

## Understand data and reliability

- [Data model and directory contract](data-model.md) — models, write
  boundaries, and the on-disk archive contract.
- [Rate limiting and error handling](rate-limiting-errors.md) — throttling,
  backoff, terminal states, and error routing.
- [Offline operations](offline-operations.md) — zero-network re-render,
  relation rebuilding, and local maintenance pipelines.

## Related references

- [Web API reference](../reference/api/index.md) — observed REST/GraphQL contracts,
  response semantics, and discovery notes.
- [Maintainer guide](../development/index.md) — test architecture, contributor
  workflow, and simulated fixture contracts.
