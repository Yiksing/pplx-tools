---
name: quality-gates
description: Maintain quality, translation, build, and Pages gates. Use when changing workflow topology, action revisions, permissions, concurrency, deployment blocking, or reproducing GitHub Actions locally. Do not use for an individual documentation audit rule or ordinary feature tests.
---

# Maintain quality gates

Preserve this order:

```text
quality validate -> translation + complete validation + strict build
                 -> validated Pages artifact -> Pages deployment
```

No failed or skipped prerequisite may produce a deployable artifact.

## Prerequisites

Read the current source of truth before changing the pipeline:

- `.github/workflows/quality.yml`
- `.github/workflows/translate-docs.yml`
- `scripts/audit_docs.py`, `scripts/translate_docs.py`, and
  `tests/scrub_fixtures.py`
- `tests/test_translate_docs.py` for workflow contract assertions
- `README.md` and `README.zh-CN.md` for the public description

Read [references/pipeline.md](references/pipeline.md) only when changing stage
topology, permissions, action pins, deployment, or the complete command matrix.

Read [references/ci-failure-playbook.md](references/ci-failure-playbook.md)
only when diagnosing a failed, unexpectedly skipped, or unchained Actions run.

## Workflow

1. Classify the task as local reproduction, validation-gate maintenance,
   translation/build maintenance, or Pages deployment diagnosis.
2. Reproduce every applicable check locally before editing YAML. Separate
   repository failures from runner, permission, secret, or Pages-environment
   failures.
3. Make the smallest dependency or permission change that preserves the
   pipeline order. Keep pull-request validation free of translation API calls.
4. For third-party and official actions, select a release compatible with the
   current GitHub-hosted runner JavaScript runtime, pin the action to a full
   commit SHA, and retain a human-readable release comment. Verify the release
   and SHA from the action's authoritative repository.
5. Keep top-level permissions minimal. Grant `contents: write` only to the job
   that pushes generated translations, and grant `pages: write` plus
   `id-token: write` only to the deployment job.
6. Add or update workflow contract tests when order, triggers, commands,
   permissions, generated commit behavior, or deployment dependencies change.
7. Run the local gate sequence and inspect the resulting workflow diff for
   untrusted-input expansion, secret exposure, accidental API use, or paths
   that can bypass validation.

## Red lines

- Never deploy a separately rebuilt or unvalidated `site/`; deploy the artifact
  produced by the validated strict build.
- Never let translation or Pages deployment run after a failed `quality`
  conclusion on `main`.
- Never expose translation credentials to pull-request code, logs, command-line
  arguments, generated files, manifests, or artifacts.
- Never use floating action tags. Do not solve runtime warnings by suppressing
  them or forcing a deprecated runtime globally.
- Never loosen `uv lock --check`, `uv sync --frozen`, fixture residue checks,
  the offline suite, or strict MkDocs build merely to turn a run green.
- Never force-push over a `main` advancement detected during generated
  checkpoint commits.
- Do not describe a successful workflow as branch protection. Repository
  rulesets are separate remote settings and must be verified independently.

## Stop signals

Stop and report the blocking boundary when:

- the required repository secret, Pages environment, token permission, or
  repository setting is unavailable;
- the authoritative action release or commit cannot be verified;
- `main` advances while generated commits are being prepared;
- a local success cannot reproduce a runner-only failure and the action log is
  unavailable;
- tests were interrupted, not collected, or skipped unexpectedly.

Do not convert these conditions into permissive fallbacks.

## Verification and output

Run the local equivalent of `quality`, in workflow order. The first command
mirrors the sensitive-path tracking gate and must produce no output; the audit
command mirrors CI by always passing an exact ancestor SHA as the changed base:

```bash
test -z "$(git ls-files | grep -E '(^|/)[.]cookies[.]json$|^web_archive/' || true)"
uv lock --check
uv sync --frozen
uv run python scripts/audit_docs.py --format github --machine-mode allow-stale \
  --changed-base "$(git merge-base origin/main HEAD)"
uv run python tests/scrub_fixtures.py --check
uv run pytest -q
uv run mkdocs build --strict
```

When generated outputs are in scope, also run:

```bash
uv run python scripts/translate_docs.py --check
uv run python scripts/audit_docs.py --format github --machine-mode required
```

Report each command and result, the first blocking stage, whether the failure is
local or remote-only, and whether deployment was prevented. After pushing,
inspect the actual run through `gh`; do not infer remote success from a local
pass.
