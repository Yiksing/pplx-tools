---
name: maintain-docs-i18n
description: Maintain documentation translation infrastructure, prompts, catalogs, manifests, routing, and automation. Use when changing locales, provider or model configuration, prompt contracts, generated metadata, checkpointing, or multilingual Actions. Do not use for canonical prose; machine locales remain Action-generated.
---

# Maintain documentation i18n

## Respect ownership

- Keep English and Simplified Chinese as the only reviewed canonical sources.
- Never turn an ordinary prose change into a manual edit of generated locale
  Markdown, generated catalogs, or manifest entries.
- Read [the automation contract](references/automation-contract.md) only when
  changing configuration, prompts, source routing, translator behavior, or the
  workflow.
- Read current values from `i18n/config.toml`; do not duplicate model names,
  locale lists, limits, or routing tables in code or this skill.
- Never place an API key or credential value in source, commands, logs,
  generated files, artifacts, or skill content.

## Trace the change

1. Identify the authoritative layer:
   - registry and defaults: `i18n/config.toml`;
   - parsing and routing: `scripts/i18n_config.py`;
   - generation and manifest: `scripts/translate_docs.py`;
   - Markdown and catalog prompts: `i18n/prompts/`;
   - site chrome and notices: catalogs plus `scripts/mkdocs_i18n.py`;
   - orchestration and deployment: `.github/workflows/translate-docs.yml`.
2. Inspect `tests/test_translate_docs.py` and `tests/test_audit_docs.py` before
   modifying the contract.
3. Map compatibility effects on existing generated pages, fingerprints,
   canonical heading aliases, and resumable locale commits.
4. Prefer a migration or offline refresh path over forcing paid regeneration.

## Preserve the automation flow

- Keep pull-request validation offline; never expose translation credentials to
  untrusted PR code.
- Start automatic generation only from the exact SHA of a successful
  push-triggered quality run on `main`; abort if `origin/main` has advanced.
- Plan incrementally, translate only stale units, and retain one checkpoint
  commit per completed locale on a generated-only branch.
- Validate the manifest, audit required machine outputs, run all tests, and
  build strictly before fast-forwarding `main`, uploading, and deploying.
- Inject the translation secret only into a generation step whose offline plan
  reports pending API-backed units.
- Keep deployment dependent on the validated translation/build job.
- Keep the configured model replaceable through configuration or the supported
  workflow override; never branch on a literal model name.

## Verify without spending first

Run:

```bash
uv run python scripts/translate_docs.py --plan
uv run python scripts/translate_docs.py --check
uv run python scripts/audit_docs.py --machine-mode allow-stale
uv run pytest -q tests/test_translate_docs.py tests/test_audit_docs.py
uv run mkdocs build --strict
```

`--plan`, `--check`, and `--refresh-heading-anchors` make no translation API
calls. Generated outputs, including refreshed anchors, remain Action-owned.
Keep refresh, live generation, and `--force` in the protected Action after
reviewing the plan and expected paid scope.

For normal canonical prose work, stop; it belongs to a separate
canonical-document phase.
