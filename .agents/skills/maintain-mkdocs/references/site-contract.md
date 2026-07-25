# MkDocs site behavior contract

Use current repository files as the implementation source. This document names
the user-visible invariants that refactors must preserve.

## Identity, theme, and content blocks

- Resolve the English and Simplified Chinese site names and descriptions from
  `mkdocs.yml` and the two canonical catalogs. Machine-locale chrome comes from
  generated catalogs through `scripts/mkdocs_i18n.py`.
- Keep the product title free of “conversation history export” and
  “对话历史导出”; archive terminology may remain in descriptive body text.
- Keep the homepage subscription/API scope statement as a styled paragraph,
  not a heading.
- Preserve the system/light/dark palette cycle. Light mode uses the established
  green-and-beige visual language; dark mode uses the established
  Perplexity-inspired surfaces and teal accents.
- Theme admonitions, details, tables, code, links, and custom notes through
  palette variables so both schemes apply consistently.
- Keep every rendered H1-H6 heading bold in both palettes.

## Language preference

- On the first visit to the site root, match `navigator.languages` against the
  configured alternates and redirect only when a supported non-English locale
  is preferred.
- Persist a manual language selection locally and let it override later browser
  preferences. Do not redirect non-root pages.
- Give every custom JavaScript asset a query-string cache key in `mkdocs.yml`;
  update the key whenever the corresponding script changes.

## Primary navigation

- Treat User guide, Architecture, Web API reference, and Maintainer guide as
  path-aware top-level sections.
- On desktop, open the active top-level section by default, collapse inactive
  sections, and allow deliberate manual expansion.
- On mobile, open only the active path by default. Do not pre-expand every
  nested item or reuse desktop-open state.
- Hide the entire Web API reference branch outside that section while keeping
  every API page in MkDocs navigation, build input, links, and the search
  index.
- Re-run navigation setup after Material document swaps and viewport breakpoint
  changes. Remove or reuse event handlers instead of accumulating duplicates.

## Numbering and fragments

- Apply hierarchical decimal numbers in the left navigation only within User
  guide. Do not number the other primary-navigation sections.
- Apply lowercase alphabetic page-outline numbers to User guide H2-H6 headings.
  Keep the existing numeric page-outline behavior elsewhere.
- Keep H1 titles unnumbered.
- Mark left-navigation numbering as decorative with `aria-hidden`.
- Keep visible numbering out of Markdown source and out of fragment IDs.
  Preserve legacy published fragments via
  `i18n/legacy-heading-anchors.json`.

## Verification matrix

Check at minimum:

| Context | Required observation |
| --- | --- |
| Desktop, unrelated page | Inactive sections collapse; Web API is hidden |
| Desktop, section page | Active section opens to the current depth |
| Mobile, section landing | Only the active path opens |
| Manual interaction | Expand/collapse remains controllable |
| User guide | Left decimal and right lowercase-letter numbering |
| Other sections | Existing right numeric numbering; no left numbering |
| All locales | Navigation labels, search, and source links remain usable |
| Both palettes | Custom blocks inherit the selected color scheme |

Use `tests/test_translate_docs.py` as the executable repository contract, then
perform browser checks because CSS layout and responsive interaction cannot be
proven by text assertions alone.
