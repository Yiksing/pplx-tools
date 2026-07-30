---
name: privacy-release-gate
description: Privacy red-line gate for content entering this public repository. Use when publishing commits, after bulk fixture or documentation changes, or when a privacy leak is suspected. Do not use for routine feature development or test-only changes.
---

# Privacy release gate

Run this gate before committing anything destined for the public remote.
Hard-learned lesson: every round that felt "already clean" still produced a
leak.

## 1. Red-line patterns (zero hits is the only pass)

Identity values are **not stored in this repository**. Build the identity grep
pattern at scan time from the private side's account registry (the sibling
private archive's `accounts.md`, when that checkout is available); never paste
the values themselves into any file here. Unavailable branch: without the
private checkout the identity grep cannot be built — mark it **not executed**
and escalate per §6; never treat it as passed. Supplementary pattern classes
(all real past leaks):

- Real thread UUID prefixes — the registry of known leak prefixes lives in the
  private side's copy of this gate; add every newly discovered prefix there,
  never here. Unavailable branch: without the private checkout this prefix
  scan is **not executed** and must be escalated per §6;
- Local absolute paths from contributor machines (`/Users/<name>`,
  `C:\Users\<name>`, `/home/<name>` outside tooling output);
- Real query text and real project codenames (research topics, private repo
  names — previously found in fixtures, in the scrub tool's own configured
  constants, in test-embedded strings, in CLI help epilog examples, and in
  `_platform_context/` snapshots);
- Positioning ban words (user red line):
  `脱敏|sanitiz|公开版|可扩展.{0,6}框架|首个适配站点|多网站`
  (the `_sanitize` function name is exempt).

Scan command set (run at this repository root; `.agents/` is excluded because
this skill's own directory legitimately carries the pattern list):

```bash
# Ban words + identity pattern built at scan time
grep -rniE --exclude-dir=.agents '脱敏|公开版|可扩展.{0,6}框架|首个适配站点|多网站' .
grep -rniE --exclude-dir=.agents '<identity-pattern-built-at-scan-time>' .
# Full-UUID census: whitelist 00000000-* placeholders and 5cbeef00-* (fixtures uuid5 marker)
git ls-files | tr '\n' '\0' | xargs -0 grep -noE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
  | grep -v '00000000-\|5cbeef00-' | awk -F: '{print $3}' | sort -u
```

## 2. Leak spots (ordered by past incidents — check each)

1. `tests/fixtures/**` (real report bodies in golden/raw, author names in
   citation metadata);
2. **The maintenance tools themselves**: scrub/generator scripts' configured
   constants and comments (once held entire real queries);
3. Test `.py` embedded data strings (real topic words used as
   normalize/cluster samples);
4. CLI help/epilog examples (a real query was once the demo);
5. Platform snapshots `_platform_context/` (real project codenames, private
   repo names, proxy paths);
6. Real UUIDs inside doc sample JSON/prose (a v5-shaped UUID is not proof of
   being synthetic — verify per §3);
7. Domains/URLs containing a personal handle (custom domains judged case by
   case; a domain the owner explicitly chose to publish is exempt).

## 3. Synthetic-vs-real UUID verification

Quick pass: `00000000-*` placeholders and `5cbeef00-*` (the fixtures' uuid5
synthetic namespace) pass without checking. When the §1 full-UUID census
returns any other UUID, read
[UUID verification](references/uuid-verification.md) for the exact-match
procedure against the private archive and the unavailable branch (a v5-shaped
value is never evidence of being synthetic).

## 4. Bilingual-comment audit (bundled script)

When running the bundled `pplx_audit.py` audit (block-level EN-then-ZH
comment/docstring checks), read
[Bilingual-comment audit](references/bilingual-comment-audit.md) for usage
and the exit-code contract.

## 5. Pass & escalate

- Commit only when every scan is zero; before each commit, re-run the §1
  scans on the **staged** files (faster than repo-wide).
- Suspected leak: report to the user before acting; never rewrite semantics
  on your own. Replace real content with **descriptive synthetic text**
  ("example … (item 1)"), never with garbled characters.

## 6. Degraded mode: private checkout unavailable

The gate never silently passes without the sibling private archive checkout.
When that checkout is absent or unreadable, read
[Degraded mode](references/degraded-mode.md) for the full lists of checks
that still must run and pass, the checks that must be reported as **not
executed**, and the mandatory escalation decision the user must make before
any commit.
