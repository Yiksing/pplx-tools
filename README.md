# Perplexity CLI toolkit (NOT for pay-as-go API)

[中文文档](README.zh-CN.md)

Perplexity conversation archive & interactive query toolkit (`pplx-export` /
`pplx-ask`). It talks directly to the Perplexity REST/GraphQL API using your
browser's logged-in cookies, and archives conversations — steps, citations,
deep-research reports, computer-mode assets, and sub-agent workflows — as local
Markdown + JSON. Successful exports retain the raw API responses alongside the
rendered artifacts, so rendering can be re-run offline at any time.

## Purpose

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
- the Council skill's ability to run deep research with several user-specified models, produce reports, and compare them side by side.

The [`_platform_context/`](_platform_context/README.md) directory includes
archived system prompts and operating rules that may help approximate parts of
the Computer workflow locally, including Deep Research mode selection and
sub-agent model selection. Users can review this material with their local
agents and adapt it into a similar workflow.

## Features

- **`pplx-export`**: library index, single-thread / batch export (incremental
  early-stop + resumable checkpoints), asset & credit backfill, offline
  re-render (zero network).
- **`pplx-ask`**: SSE streaming queries in four modes (search / deep-research /
  council / study), with automatic archiving on completion.
- **Raw-preserving archives**: successful exports retain raw API responses, so
  rendered artifacts can be regenerated offline without re-fetching.

## Installation

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

From a local clone:

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

## User-level configuration (accounts / BOT space)

The account registry and BOT space live in an external TOML file (template:
[`config.example.toml`](config.example.toml)):

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

Load priority: `--config PATH` > `PPLX_EXPORT_CONFIG` environment variable >
the default `~/.config/pplx-export/config.toml`.

Alternatively, `pplx-export init` can generate the config automatically: it
discovers your signed-in accounts from the browser's session cookies, matches
the BOT space by title, and writes the TOML with owner-only permissions.
Flags: `--force` (overwrite an existing file), `--create-bot-space [TITLE]` (create
the space when no title matches, optionally with an explicit title),
`--bot-title TITLE` (space title used for matching/creation, default `BOT`).

## Quick start

```bash
pplx-export index --account <username>    # fetch the library index
pplx-export export <thread_url>           # export a single thread
pplx-export batch --account <username>    # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run           # offline re-render, zero network
pplx-ask ask "<prompt>"                   # streaming query with automatic archiving
```

## Documentation

Full documentation (usage guide, design documents, development notes):

- Local preview: `uv run mkdocs serve`
- Sources: [`docs/`](docs/README.md)

Most pages in the MkDocs site were generated or reconstructed from the current
code and tests. Some pages also retain design context, observations, and
decisions from earlier discussions with agents. When a documentation statement
and the implementation differ, treat the current code and tests as the source
of truth.

## Quality gates and automation

Every pull request and ordinary push to `main` that triggers Actions runs
[`quality.yml`](.github/workflows/quality.yml). Its `validate` job checks the
dependency lock, audits documentation contracts, checks simulated fixtures for
sensitive residue, runs the offline test suite, and strictly builds every
configured MkDocs locale. On pull requests, documentation findings are also
reported as GitHub annotations against the proposed changes. Pull requests,
pushes, and manual quality runs all supply an explicit commit base for
English/Chinese changed-pair enforcement.

[`scripts/audit_docs.py`](scripts/audit_docs.py) provides the repository's
deterministic documentation review: it checks bilingual parity, local links and
source references, test and fixture inventories, simulated-fixture provenance,
and machine-translation configuration and manifests. The auditor and
translation pipeline have isolated unit tests in `tests/test_audit_docs.py` and
`tests/test_translate_docs.py`.

After `quality` succeeds on `main`,
[`translate-docs.yml`](.github/workflows/translate-docs.yml) incrementally
refreshes generated languages through the configured DeepSeek model and
checkpoints each completed locale in its own commit on a generated-only branch.
It then repeats the manifest check, required-mode documentation audit, fixture
scrub, tests, and strict multilingual build. Only that fully validated branch
may fast-forward `main`, after which the same built artifact is uploaded and
deployed. A failure preserves completed locale checkpoints for retry without
placing a partial translation batch on `main`.

Bot promotion commits are already covered by the translation workflow's full
validation and intentionally do not start a recursive quality/translation run.

> `main` currently has no branch protection or repository ruleset. These are
> workflow gates rather than a restriction on authorized direct pushes;
> protection can be enabled later without changing the validation commands.

## Testing

```bash
uv run pytest        # fully offline (snapshot fixtures are committed; zero network)
```

## License

[GPL-3.0](LICENSE)
