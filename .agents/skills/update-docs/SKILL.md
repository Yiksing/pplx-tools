---
name: update-docs
description: Update reviewed English and Simplified Chinese documentation while preserving code accuracy and bilingual structure. Use when changing READMEs or canonical prose, examples, headings, links, and citations. Do not use for site behavior, translation automation, generated locales, code-only changes, or read-only audits.
---

# Update canonical documentation

## Keep the source boundary

- Treat English and Simplified Chinese as one reviewed canonical pair.
- Update both counterparts in the same change, even when the request names only
  one language.
- Do not edit any other locale suffix. GitHub Actions generates those files
  after `main` passes quality validation.
- Treat implementation and tests as the factual source of truth. Preserve
  discussion-derived rationale only while it remains compatible with them.
- Read [the content contract](references/content-contract.md) only when
  changing product titles, the homepage, Web API claims, external CLI
  observations, or historical wording.

## Locate the pair

1. Identify every affected canonical page and its adjacent `.zh-CN.md` twin.
2. Include `README.md` and `README.zh-CN.md` when repository-facing behavior or
   contributor workflow changes.
3. Inspect the implementation, tests, workflows, and configuration named by
   the page. Do not infer current behavior from commit messages alone.
4. Check nearby canonical pages for terminology and link conventions before
   drafting.

## Make the change

1. Write the English and Chinese versions as independently readable prose with
   equivalent claims, structure, code, links, and limitations.
2. Preserve command names, paths, identifiers, code fences, URLs, and exact
   values unless the underlying contract changed.
3. Use descriptive source headings without stored outline numbers. MkDocs adds
   presentation numbering at build time.
4. Prefer stable source references. Recheck line-specific citations after code
   movement.
5. Describe observed external or Web API behavior as observation, not as a
   vendor guarantee.
6. Keep generated locale files and `i18n/manifest.json` untouched.

## Externally-copied skills

When a canonical change touches the CLI invocation contract, runtime or
backoff expectations, archive layout, or `pplx-ask` flags, review the two
skills under `_recommended_skills/skills/` in the same change and sync them
when affected. They are English-only (no `.zh-CN.md` twin) and are copied
into external agent environments, so their links must be absolute public-site
URLs, never repository-relative paths.

## Validate proportionally

Run the offline canonical audit:

```bash
uv run python scripts/audit_docs.py --machine-mode allow-stale
uv run python scripts/translate_docs.py --plan
```

When comparing a branch or commit range, also pass `--changed-base <revision>`
so paired canonical changes are enforced. Report the pending document and
catalog counts from `--plan`; it performs no API calls.

Do not generate machine locales locally. After a canonical change,
`translate_docs.py --check` is expected to report stale generated outputs until
the validated main-branch Action updates them.

Run focused tests for the documented behavior, then build every configured
locale:

```bash
uv run mkdocs build --strict
```

If the work changes audit policy, site presentation, or translation machinery,
stop and route that change as a separate phase.
