# Change-design checklist

Use the applicable prompts; omit irrelevant sections.

## Problem and scope

- What observable problem or opportunity is being addressed?
- What is explicitly out of scope?
- Which current code, test, document, or workflow is authoritative?
- Which assumptions still need evidence or a user decision?

## Contracts and data flow

- What calls what, and where is the value transformed or persisted?
- Which public CLI, archive schema, API-shaped input, rendering, or navigation
  contract changes?
- Can the change lose, duplicate, truncate, relocate, or delete archive data?
- Must repeated or interrupted execution remain idempotent and resumable?

## Compatibility and failure

- Are existing archives, configs, manifests, links, fragments, or generated
  pages compatible?
- Is migration needed, and what makes it safe to retry?
- How is partial failure surfaced and recovered?
- What is the rollback boundary?

## Verification impact

- Which topical unit or component tests should change?
- Is a simulated fixture and regenerated golden required?
- Which English and Chinese documents must change together?
- Will canonical text, glossary, prompt, model, or locale routing create
  translation work? Check with the repository plan command before any API use.
- Which local and CI gates prove completion?

## Deliverable

Return:

1. verified current behavior;
2. recommended design and alternatives considered;
3. file-level change points in dependency order;
4. regression and acceptance matrix;
5. migration, rollout, rollback, and documentation impact; and
6. unresolved decisions.
