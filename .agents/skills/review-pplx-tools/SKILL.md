---
name: review-pplx-tools
description: Perform evidence-first, read-only review of archive fidelity, rendering, state, transport, tests, documentation contracts, and diffs. Use when auditing risk, hunting regressions, or analyzing a PR. Do not use to implement fixes without a separate change request.
---

# Review pplx-tools

Read [references/review-contract.md](references/review-contract.md) only when
assessing repository-wide evidence, severity, or archive fidelity.

## Workflow

1. Confirm the requested scope and inspect the worktree without changing it.
2. Trace current implementation, callers, persistence effects, tests, and
   public contracts. Treat current code and tests as factual authority; use
   historical discussion only as design context.
3. Search existing regression modules and resolved review lineage before
   reporting a finding. Do not repeat a fixed issue unless the current tree
   demonstrates a regression.
4. Reproduce or measure the impact when safe. Distinguish:
   - demonstrated current impact;
   - a reachable risk without an observed repository instance;
   - a theoretical concern without a demonstrated trigger.
5. Report only actionable findings, ordered by severity. Give each finding a
   tight `file:line` location, trigger, observable consequence, evidence,
   affected contract, and missing or inadequate regression coverage.
6. State residual uncertainty and the checks performed when no finding is
   confirmed.

## Boundaries

- Keep review read-only: do not edit, stage, commit, push, call mutating APIs,
  or regenerate artifacts.
- Do not inflate severity from hypothetical worst cases. Base severity on the
  demonstrated trigger, affected data, recoverability, and scope.
- For archive-fidelity claims, inspect the full raw-to-render and persistence
  path before concluding from one representation.
- If implementation is requested after review, end the read-only phase and
  route the accepted finding as a separate design or implementation phase.
  Existing authorization remains valid unless design exposes a material
  decision or scope expansion.
