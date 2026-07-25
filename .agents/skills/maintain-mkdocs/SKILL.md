---
name: maintain-mkdocs
description: Maintain the MkDocs presentation layer, including theme, overrides, CSS, JavaScript, hooks, responsive navigation, numbering, search, and localized chrome. Use when changing site layout or browser behavior. Do not use for prose, translation generation, provider configuration, or code-only changes.
---

# Maintain the MkDocs site

## Preserve behavior, not selectors

- Read [the site behavior contract](references/site-contract.md) only when
  changing navigation, numbering, theme colors, language behavior, or titles.
- Inspect `mkdocs.yml`, `overrides/`, `docs/stylesheets/extra.css`,
  `docs/javascripts/`, and both MkDocs hooks before choosing an implementation.
- Keep CSS and JavaScript coupled only through explicit classes and attributes.
  Prefer Material variables over scattered hard-coded component colors.
- Preserve searchability and stable URLs even when a navigation section is
  conditionally hidden.

## Plan the presentation change

1. State which surfaces change: global header, primary navigation, page
   outline, content, admonitions, search, footer, or language selector.
2. Check English, Simplified Chinese, and one generated locale because site
   chrome can follow different localization paths.
3. Check light, dark, and system-preference palette behavior.
4. Separate desktop requirements from mobile behavior. Do not let desktop
   expansion state leak into the mobile drawer.
5. Identify hook, CSS, JavaScript, redirect, and fragment-ID effects before
   editing Markdown.

## Implement narrowly

- Handle prose edits as a separate canonical English/Chinese document phase.
- Never hand-edit machine-locale Markdown for a presentation change.
- Keep stored headings descriptive and unnumbered. Implement visible numbering
  in the build hook or navigation layer without changing canonical fragments.
- Keep JavaScript usable after Material instant-navigation page swaps and
  viewport changes.
- Preserve accessible labels and state; decorative numbering must be hidden
  from assistive technology.
- Update the query-string cache key in `mkdocs.yml` after changing a referenced
  custom CSS or JavaScript asset.

## Verify the result

Run the focused site-contract tests first:

```bash
uv run pytest -q tests/test_translate_docs.py
```

Then run:

```bash
uv run python scripts/audit_docs.py --machine-mode allow-stale
uv run mkdocs build --strict
```

Preview with `uv run mkdocs serve`. Inspect a representative page at desktop
and mobile widths in both palettes. Exercise active-section defaults, manual
expand/collapse, language switching, search, copied fragment URLs, and
back/forward navigation.

Treat locale registration, catalogs, translation notices, source routing, and
generation automation as a separate infrastructure phase.
