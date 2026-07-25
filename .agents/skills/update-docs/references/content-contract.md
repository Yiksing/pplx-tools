# Canonical content contract

## Authority and scope

- Derive operational and API descriptions from current code, tests,
  configuration, and committed simulated fixtures.
- Treat `docs/` as mostly reconstructed from those sources. Retain useful
  design context from prior agent discussions only when it is clearly framed
  and still agrees with observable behavior.
- Use `docs/development/i18n.md` for the current canonical/generated boundary
  and `docs/README.md` for the current information architecture.
- Do not expose credentials, private archive content, real account details, or
  live API responses in examples.

## Titles and homepage

- Do not use “conversation history export” or “对话历史导出” in README or MkDocs
  page titles. Those descriptions may appear in body text when accurate.
- Keep the MkDocs homepage pay-as-you-go scope warning as ordinary
  `.homepage-scope-note` content, not a heading or table-of-contents entry.
- Take the current product names and localized navigation labels from
  `mkdocs.yml`, `i18n/catalog.en.json`, and `i18n/catalog.zh-CN.json`; do not
  create a second hard-coded naming source.

## Observed external behavior

- Attribute dated external CLI facts to what the project observed on that date
  (“项目于该日观察到”), rather than presenting them as timeless vendor policy.
- Preserve this existing Chinese passage exactly unless the user explicitly
  requests a factual correction:

  > 截止至7月20日，Perplexity 并未提供类Unix环境中的官方 CLI
  >
  > 我们注意到官方于7月23日提供了Computer模式中所使用的pplx工具的公开发布版本；但该工具仍是按量计费的

- Keep the English counterpart semantically equivalent without silently
  strengthening or weakening either claim.
- In the Web API reference, distinguish repository observations from official
  Perplexity documentation and include the observation date where material.

## Structural invariants

- Keep one English source page and one `.zh-CN.md` counterpart for every
  published canonical page.
- Keep heading levels and fenced-code structure aligned across the pair.
- Do not add manual numeric or alphabetic outline prefixes to Markdown
  headings. `scripts/mkdocs_heading_numbers.py` owns visible numbering and
  `i18n/legacy-heading-anchors.json` owns published-fragment compatibility.
- Preserve local-link targets, anchor meaning, and cited source paths in both
  languages.

## Review questions

- Can every current-behavior claim be traced to code, tests, configuration, or
  an explicitly dated observation?
- Did both canonical languages change together?
- Did the change avoid every generated locale?
- Are limitations and uncertainty equally visible in both versions?
- Would moving or translating a heading leave links and fragments valid?
