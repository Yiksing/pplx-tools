---
name: audit-docs
description: Maintain the repository's offline documentation auditor and isolated tests. Use when changing scripts/audit_docs.py, finding or exit contracts, bilingual pairing, inventories, links, provenance, or generated-output validation. Do not use for ordinary prose edits or translation generation.
---

# Audit documentation

Keep the audit deterministic, offline, read-only, and suitable for both local
diagnostics and GitHub annotations.

## Prerequisites

Work from the repository root. Before changing behavior, read:

- `scripts/audit_docs.py` for the executable contract
- `tests/test_audit_docs.py` for isolated behavior examples
- `i18n/config.toml` and `scripts/i18n_config.py` for locale ownership
- `.github/workflows/quality.yml` and
  `.github/workflows/translate-docs.yml` for the two audit modes

Read [references/contracts.md](references/contracts.md) only when adding or
diagnosing a check, finding code, output format, or exit condition.

## Workflow

1. Reproduce the behavior with the narrowest applicable command:

   ```bash
   uv run python scripts/audit_docs.py
   uv run python scripts/audit_docs.py --format github --machine-mode allow-stale
   uv run python scripts/audit_docs.py --machine-mode required
   ```

   Add `--changed-base <revision>` only when validating paired canonical
   changes against a real Git base.

2. Trace the finding to the current implementation and repository contract.
   Treat code, tests, and `i18n/config.toml` as authoritative when prose has
   drifted.
3. Add or change one focused check. Return a stable finding code, repository-
   relative path, line when meaningful, actionable message, and optional hint.
4. Cover the behavior in `tests/test_audit_docs.py` using the `tmp_path`
   miniature repository. Include a passing control and the smallest failing
   mutation. Test formatting or exit status separately when those contracts
   change.
5. Run the isolated tests, the auditor, and then the full repository gates
   proportionate to the change.

## Red lines

- Never make the auditor modify documents, manifests, fixtures, Git state, or
  user configuration.
- Never add network access or depend on live APIs, external pages, timestamps,
  locale, or the real checkout contents in isolated unit tests.
- Do not weaken a valid contract merely to make an existing checkout pass.
- Do not edit generated-language Markdown to resolve a canonical-document
  failure. Ordinary source changes update English and Simplified Chinese;
  automation owns other locales.
- Do not use `ignore` or `allow-stale` as a substitute for `required` after
  machine translation has run.
- Preserve deterministic finding order and machine-readable output.

## Stop signals

Stop and report the evidence before changing code when:

- the requested check requires mutation or network access;
- a failure is caused by an invalid Git base, missing generated prerequisite,
  or unavailable repository setting rather than audit logic;
- the intended source of truth conflicts with `i18n/config.toml`, fixture
  contracts, or current production behavior;
- an interrupted or uncollected test run leaves the result unknown.

If `uv` fails only because its default cache is outside the sandbox, retry with
a writable task-specific `UV_CACHE_DIR`; do not diagnose that as a repository
defect.

## Verification and output

Run at minimum:

```bash
uv run pytest -q tests/test_audit_docs.py
uv run python scripts/audit_docs.py --machine-mode allow-stale
```

For workflow-facing changes, also run:

```bash
uv lock --check
uv run python tests/scrub_fixtures.py --check
uv run pytest -q
uv run mkdocs build --strict
```

Report the command, exit status, finding code and location, root cause, and
verification performed. Exit `0` means the selected policy passed; exit `1`
means findings reached the configured failure threshold; exit `2` means
argument or internal CLI failure. An interrupted run is not a pass.
