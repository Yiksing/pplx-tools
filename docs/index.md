# Perplexity CLI toolkit

<p class="homepage-scope-note" role="note">
  <strong>NOT for pay-as-go API</strong>
</p>

Perplexity conversation archive & interactive query toolkit (`pplx-export` / `pplx-ask`).

It talks directly to the Perplexity REST/GraphQL API using your browser's logged-in
cookies, and archives conversations — steps, citations, deep-research reports,
computer-mode assets, and sub-agent workflows — as local Markdown + JSON. Successful
exports retain the raw API responses alongside the rendered artifacts, so rendering
can be re-run offline at any time.

## Introduction

Beyond archiving historical conversations, this project primarily aims to give
local agents — closer to the data and often backed by more compute — a measure
of Perplexity Computer's capabilities. By letting them access reports produced
by Perplexity Deep Research directly within their working loop, they can use
high-quality information to tune key parameters in code more precisely while
making fuller use of an existing Perplexity Max subscription.

> As of July 20, Perplexity did not offer an official CLI for Unix-like
> environments. On July 23, Perplexity publicly released the `pplx` tool used
> in Computer mode, but that tool still uses pay-as-you-go billing.

It is not a full replacement for Computer mode. Two abilities remain out of reach:

- the Deep Research skill's freedom to pick an arbitrary model;
- the Council skill's ability to run deep research with several user-specified models,
  produce reports, and compare them side by side.

The [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context)
directory includes archived system prompts and operating rules that may help
approximate parts of the Computer workflow locally, including Deep Research mode
selection and sub-agent model selection.

## Features

### `pplx-export` — archive your library

- Library index and space index
- Single-thread / batch export with incremental early-stop + resumable checkpoints
- Asset backfill and credit-usage backfill
- Conversation relation graph
- Offline re-render (`re-render`, zero network)
- Periodic-incremental cron snippet

### `pplx-ask` — query Perplexity from the shell

- SSE streaming queries in four modes: search / deep-research / council / study
- Auto-move into a BOT space on completion, read receipts
- Automatic archiving of every thread it creates — built so other agents can call it
  to fetch real-time information

Per-mode artifact boundaries (citations / reports / assets / sub-agents): see
[Modes](guide/modes.md); rendering-fidelity principles: see
[Export pipeline](architecture/export-pipeline.md).

!!! note "Documentation provenance"

    Most pages in this MkDocs site were generated or reconstructed from the current
    code and tests. Some pages also retain design context, observations, and
    decisions from earlier discussions with agents. When a documentation statement
    and the implementation differ, treat the current code and tests as the source
    of truth.

## Where to next

- **Use the tools** — follow the task-oriented [User guide](guide/index.md).
- **Understand the implementation** — use the
  [Architecture reading map](architecture/index.md).
- **Work with the observed web interface** — consult the
  [Web API reference](reference/api/index.md).
- **Change the project safely** — follow the [Maintainer guide](development/index.md).
