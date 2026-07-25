---
name: design-pplx-change
description: Plan and impact-map a pplx-tools change without implementing it. Use when preparing architecture, refactor, compatibility, migration, or accepted-finding fix designs. Do not use for implementation or other repository mutations; this skill is planning-only.
---

# Design a pplx-tools change

Read [references/change-design-checklist.md](references/change-design-checklist.md)
only when planning complex, cross-component, or migration work, and apply only
the relevant sections.

## Workflow

1. Inspect current code, callers, tests, documentation, and workflows that own
   the behavior. Separate verified facts from assumptions.
2. Define the goal, non-goals, user-visible behavior, and acceptance criteria.
3. Map the smallest coherent change set:
   - source-of-truth and data-flow changes;
   - persistence, deletion, archive-fidelity, and idempotency boundaries;
   - compatibility, migration, and rollback behavior;
   - failure handling and observability;
   - tests, fixtures, documentation, i18n, CI, and deployment impact.
4. Compare viable approaches when their tradeoffs materially differ. Recommend
   one and explain why it best preserves existing contracts.
5. Produce an ordered implementation plan with file-level change points,
   verification commands, risks, and explicit decisions still needed.

## Boundaries

- Do not edit files, generate translations, change Git state, or mutate
  external systems while using this skill.
- Do not hard-code volatile repository state such as model names, action SHAs,
  test counts, branch protection, or run identifiers; identify the live config
  or workflow that owns each value.
- Treat translation API cost as an impact to assess, not permission to call the
  API.
- After the user approves implementation, hand testing, fixture, documentation,
  and quality work to their dedicated skills.
- If the same request already authorizes implementation, complete a
  proportionate design pass and continue without asking for duplicate
  approval. Stop only for an unresolved material decision or a scope expansion.
