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

- Pass without checking: `00000000-*` placeholders and `5cbeef00-*` (the
  fixtures' uuid5 synthetic namespace).
- Every other full UUID: exact-match against the private archive when its
  checkout is available. The private archive location is derived from the
  user-level config's `archive_root` (or a sibling checkout path).

  **Efficient approach (recommended)**: index once, compare with `comm`.
  Avoid per-UUID `grep -r` — on large archives (>1000 threads) the per-UUID
  loop takes minutes; the two-pass `comm` approach finishes in seconds.

  1. Index all UUIDs from the private archive:

     ```bash
     PRIVATE="<archive_root>"
     grep -rohE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
       "$PRIVATE" 2>/dev/null | sort -u > /tmp/archive_uuids.txt
     ```

  2. Collect non-whitelisted UUIDs from the repository:

     ```bash
     git ls-files | tr '\n' '\0' | xargs -0 grep -ohE \
       '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
       | grep -v '00000000-\|5cbeef00-' | sort -u > /tmp/repo_uuids.txt
     ```

  3. Compare:

     ```bash
     comm -12 /tmp/repo_uuids.txt /tmp/archive_uuids.txt  # REAL (each must be investigated)
     comm -23 /tmp/repo_uuids.txt /tmp/archive_uuids.txt  # SYNTHETIC (safe)
     ```

  **Fallback (per-UUID, slow)**: when only a handful of UUIDs need checking:

  ```bash
  grep -rqlF "<full-uuid>" <private-archive>/web_archive/ && echo REAL || echo synthetic
  ```

  Prefix matching (`uuid[:8]`) false-positives on handwritten dummy values
  (`aaaaaaaa-…`); always compare the full string.
- Unavailable branch: without the private checkout a non-whitelisted UUID can
  never be cleared as synthetic. Mark the verification **not executed**, list
  every such UUID, and escalate per §6 — a v5-shaped or plausible-looking
  value is not evidence of being synthetic.

## 4. Bilingual-comment audit (bundled script)

`pplx_audit.py` in this directory: block-level check for "English comment
block first, Chinese second", docstring EN-then-ZH order, trailing Chinese
comments, and EN-only/ZH-only blocks. Usage:

```bash
python .agents/skills/privacy-release-gate/pplx_audit.py --repo .            # full scan (pplx_export/ + tests/)
python .agents/skills/privacy-release-gate/pplx_audit.py --repo . <file...>  # specific files
# exit code 0 = CLEAN; violations are reported as file:line plus a type
```

## 5. Pass & escalate

- Commit only when every scan is zero; before each commit, re-run the §1
  scans on the **staged** files (faster than repo-wide).
- Suspected leak: report to the user before acting; never rewrite semantics
  on your own. Replace real content with **descriptive synthetic text**
  ("example … (item 1)"), never with garbled characters.

## 6. Degraded mode: private checkout unavailable

When the sibling private archive checkout is absent or unreadable, the gate
runs degraded — it never silently passes.

Still **must run and pass** (zero hits / exit 0, no private input needed):

- §1 ban-word grep (patterns are inline above);
- §1 local-absolute-path grep (`/Users/<name>`, `C:\Users\<name>`,
  `/home/<name>`);
- §1 full-UUID census with the `00000000-*` / `5cbeef00-*` whitelist;
- §2 leak-spot review for items not requiring private data (paths, CLI
  help/epilog, embedded test strings, `_platform_context/` codenames);
- §4 bilingual-comment audit (`pplx_audit.py`).

Must be reported as **not executed** — never inferred, approximated, or
assumed passed:

- §1 identity-pattern grep (pattern source is the private `accounts.md`);
- §1 thread-UUID leak-prefix scan (registry is private-side only);
- §3 real-vs-synthetic verification of every non-whitelisted full UUID.

Escalation: before any commit, present the user with (a) the checks that ran
and passed, (b) the exact checks not executed and why, and (c) the
non-whitelisted UUIDs left unverified. The user then decides: provide the
private checkout, defer the commit, or explicitly accept the residual risk in
writing. Proceeding without one of these three decisions is forbidden.
