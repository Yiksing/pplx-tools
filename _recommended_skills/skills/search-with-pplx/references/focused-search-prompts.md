# Focused search prompt patterns

Use one pattern when a direct question needs a stronger evidence contract.
Replace every placeholder and remove irrelevant instructions.

## Authoritative fact lookup

```markdown
Find the most authoritative answer to this question:

[QUESTION]

This will be used for [PURPOSE]. Prefer [PRIMARY OR OFFICIAL SOURCE TYPE].
Give the exact value, definition, scope, and units where relevant. Link the
original source and identify the supporting section, table, page, or data
field when available.

If authoritative sources disagree, explain the difference. If the requested
fact cannot be verified, say so instead of filling the gap with a plausible
estimate. Apply a date boundary only if the fact is time-dependent.
```

## Bounded claim verification

```markdown
Verify this claim:

[CLAIM]

Break it into atomic subclaims if needed. Prefer original publications,
official records, standards, or first-party documentation. For each material
subclaim, return:

- SUPPORTED, PARTIALLY SUPPORTED, REFUTED, or UNVERIFIABLE;
- the strongest source;
- the exact supporting or contradicting evidence location when available;
- a short explanation;
- cautious replacement wording if the original claim overstates the evidence.

Do not treat repeated secondary claims or search snippets as independent
verification.
```

## Targeted literature discovery

Use this pattern to find a bounded source set for later local reading. Switch
to deep research when synthesis or exhaustive coverage is required.

```markdown
Locate authoritative literature on:

[NARROW TOPIC OR METHOD]

Find [APPROXIMATE NUMBER OR NATURAL BOUND] pivotal or especially relevant
works. Include foundational work and later evidence according to relevance;
do not impose a publication-date window unless the question requires one.

For each work, provide:

- title and authors;
- publication venue;
- DOI or canonical URL;
- why it is relevant to [PURPOSE];
- the specific method, result, or claim worth checking in the full text.

Exclude items whose existence or bibliographic metadata cannot be verified.
This is source discovery, not a substitute for reading or synthesizing the
papers.
```

## Current-state check

Use only when the answer may have changed.

```markdown
Determine the current status of:

[QUESTION]

Prefer the responsible organization's current documentation, official
announcement, filing, release notes, or maintained repository. Distinguish
the date of the underlying event from the publication date of the source.
Identify superseded information and state the effective date of the answer.
```
