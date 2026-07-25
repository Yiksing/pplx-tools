# Review contract

## Evidence checklist

- Resolve the exact branch, worktree state, requested paths, and comparison
  base.
- Read the implementation and all callers that can reach the suspected path.
- Inspect persistence mutations, retries, migrations, cleanup, and recovery.
- Search topical tests and `test_fix_*.py` lineage for the same condition.
- For rendering or archive fidelity, compare raw inputs, normalized structures,
  thread metadata, rendered artifacts, manifests, and repeat-run behavior as
  applicable.
- Use full-repository counts only when they are needed and freshly measured;
  otherwise state that impact is local or unmeasured.

## Finding standard

A finding should identify:

1. the defect at the smallest useful `file:line` range;
2. a concrete trigger or reachable path;
3. the observed or logically necessary consequence;
4. the affected user, archive, state, or public contract;
5. why existing tests do not prevent it; and
6. a severity justified by likelihood, scope, data loss, and recoverability.

Label unobserved risk explicitly. Keep speculative hardening suggestions
separate from confirmed defects.

## Project priorities

Give special scrutiny to:

- preservation of raw and rendered archive content;
- stable thread-directory routing and migration;
- idempotent re-render, backfill, and repeated commands;
- manifest and count semantics;
- terminal-state classification and retry boundaries;
- the rule that maintenance operations do not delete local archives;
- fixture isolation and documentation claims about observed external behavior.

Do not report a historical finding as current unless it still reproduces in the
reviewed tree.
