# Documentation translation automation contract

## Canonical and generated files

- `i18n/config.toml` is the language registry and routing authority.
- English and Simplified Chinese pages and catalogs are reviewed source.
- Every other configured locale is generated. East Asian versus other source
  routing is declared per locale in configuration; never infer it from text or
  duplicate that table elsewhere.
- `i18n/manifest.json` and machine-page front matter record inputs and output
  digests. Change them through translator behavior, not ad hoc edits.
- `i18n/glossary.json` and versioned prompts are translation inputs; changing
  either can intentionally make outputs stale.

## Cost and resumability

- Run `scripts/translate_docs.py --plan` before any live generation.
- Reuse valid outputs and manifest entries from a verified generated-only
  checkpoint branch. Generate stale units only unless the user explicitly
  requests a full rebuild.
- Use `--refresh-heading-anchors` for alias-only maintenance; it is offline.
- Preserve `--commit-each-locale` automation so each completed language is one
  resumable batch on a branch named from the exact base SHA. An interrupted run
  should not discard completed locales or place partial output on `main`.
- Avoid source-text churn for presentation-only numbering or navigation work.
  Put those concerns in MkDocs hooks, CSS, or JavaScript when appropriate.

## Provider, model, prompts, and secrets

- Read provider, endpoint, default model, prompt paths, limits, retries, and
  credential environment name from configuration.
- Keep model selection data-driven and compatible with the workflow variable or
  CLI override. Record the resolved model in generated metadata.
- Keep credentials in the repository secret consumed by the protected
  main-branch workflow. Inject the secret only into the generation step after
  an offline plan proves API-backed work is pending. Never commit, echo,
  serialize, or embed credential values.
- Protect front matter, code fences, inline code, link destinations, HTML tags,
  and URLs with reversible placeholders.
- Require structured output, heading-level parity, code-fence parity, and exact
  placeholder recovery. Reject partial or malformed responses.

## Workflow and deployment

- Keep `.github/workflows/quality.yml` independent of translation credentials
  and API calls.
- Trigger `.github/workflows/translate-docs.yml` automatically only after a
  successful push-triggered quality run on `main`, or by explicit manual
  dispatch. Checkout and verify the exact validated SHA rather than current
  branch state.
- Verify any resumed checkpoint is a linear descendant of its SHA-derived base
  and changes only generated locale documents, catalogs, and the manifest.
- After generation, require translator check, machine-mode-required docs audit,
  fixture residue check, complete pytest, and strict all-locale MkDocs build.
- Keep `main` unchanged until every check passes and it still matches the base
  SHA. Promote the checkpoint once by fast-forward, then upload Pages from that
  validated build and keep deployment dependent on it.
- Pin third-party Actions to immutable commit SHAs and use currently supported
  JavaScript-runtime releases.

## Change-specific checks

| Change | Required checks |
| --- | --- |
| Add or remove locale | Config, MkDocs registry, catalogs, routing, audit tests |
| Change model/default | Data-driven resolution, fingerprints, metadata, override tests |
| Change prompt/glossary | Protected tokens, structured response, staleness plan |
| Change manifest schema | Backward handling or migration, deterministic digests |
| Change checkpointing | SHA-derived branch, generated-only diff, one locale per commit, resume, single validated promotion |
| Change notice/catalog | Canonical catalogs, generated catalogs, source/report links |
| Change Action | Offline PR boundary, quality dependency, full post-generation gate |

Do not perform a live API call merely to prove code paths that can be covered
with fakes and committed simulated data.
