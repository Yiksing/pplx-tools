# 3. Synthetic-vs-real UUID verification

Part of the privacy-release-gate skill. Loaded when a non-whitelisted full
UUID appears in the §1 full-UUID census.

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
