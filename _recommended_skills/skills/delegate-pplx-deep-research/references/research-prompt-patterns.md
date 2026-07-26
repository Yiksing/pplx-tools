# Research prompt patterns

Use these patterns as modular research briefs. Keep the sections that improve
the task, replace every placeholder, and remove irrelevant instructions.

## Contents

- [Main agent to subagent](#main-agent-to-subagent)
- [Base Perplexity research prompt](#base-perplexity-research-prompt)
- [Literature investigation addendum](#literature-investigation-addendum)
- [Fact verification addendum](#fact-verification-addendum)
- [Research-gap addendum](#research-gap-addendum)

## Main agent to subagent

```markdown
You own a read-only deep-research workstream for the parent agent.

## Mission

Investigate: [RESEARCH QUESTION]

Use `pplx-ask` in deep-research mode and return an evidence-backed research
package. The expected result may be a substantial research report. Do not
compress it into a summary table unless the subject itself is best expressed
as a comparison or claim-by-claim audit.

The parent agent needs this research to:
[DECISION, DRAFT, REVIEW, OR VERIFICATION THAT THE RESEARCH WILL SUPPORT]

## Background and why this matters

[RELEVANT BACKGROUND]

Known facts, prior findings, or disagreements:

- [KNOWN POINT]
- [CONFLICTING CLAIM OR RESULT]
- [IMPORTANT UNCERTAINTY]

Treat these as context to test, not conclusions to repeat.

## Local materials

Read:

- [LOCAL MATERIAL]
- [LOCAL MATERIAL]

Use them to understand terminology, existing evidence, and disputed claims.
Do not treat an existing draft as authoritative merely because it is local.

Before calling an external service, minimize the transmitted context. Do not
send credentials, cookies, account identifiers, private conversation text,
unnecessary local paths, unpublished confidential material, or unrelated
personal information. If essential material cannot be transmitted safely,
stop and report the boundary.

## Questions to resolve

### Highest priority

1. [QUESTION]
2. [QUESTION]

### Additional questions

3. [QUESTION]
4. [QUESTION]

Use priority labels only when they help allocate research attention. Do not
drop lower-priority questions silently.

## Evidence standard

- Prefer original papers, official documentation, standards, datasets,
  regulatory filings, institutional reports, and other primary sources.
- Follow citations to the original source instead of relying on snippets,
  aggregators, or unattributed summaries.
- For material claims, locate the exact section, page, table, figure,
  equation, dataset field, or official statement whenever available.
- Distinguish direct evidence, strong inference, plausible interpretation,
  and unresolved uncertainty.
- Where sources disagree, explain the disagreement rather than selecting one
  silently.
- For novelty, absence, or research-gap claims, actively search for
  counterexamples and adjacent terminology.
- Do not invent bibliographic metadata, quotations, page numbers, DOI values,
  or source support.
- Do not impose an arbitrary publication-date window. Include foundational
  and later work according to relevance and authority. Apply recency or a date
  cutoff only when the question is explicitly time-sensitive or historically
  bounded.

## Execution

Build a detailed Perplexity-facing prompt from this task and the applicable
pattern in `references/research-prompt-patterns.md`.

Run:

`pplx-ask --out "$PPLX_ARCHIVE_ROOT" ask "$PPLX_RESEARCH_PROMPT" --mode deep-research --no-telemetry`

Keep automatic export enabled. Capture the returned thread identity, locate
the archive by exact identity, and verify `thread.json`.

## Completion contract

Read the full archived report and source artifacts. Return:

1. a concise synthesis of the strongest findings;
2. the verified archive directory and primary report path;
3. the `sources.json` and `sources.md` paths and returned-source count;
4. a small claim-to-source map for the conclusions most important to the
   parent;
5. material disagreements, inaccessible primary sources, weak evidence, and
   unresolved questions;
6. any generated assets that require inspection.

Do not paste the full report or a very large source list into the handoff
unless asked. Preserve and point to the complete archive instead. Do not claim
that every returned source was independently verified unless you opened and
checked every source.
```

## Base Perplexity research prompt

```markdown
# Role

Act as an expert research analyst in [DOMAIN].

# Research mission

Investigate [RESEARCH QUESTION] to support [INTENDED USE].

Produce a substantive, evidence-dense research report. Synthesize and evaluate
the evidence rather than merely listing search results or reducing the
investigation to a small table.

# Background

[CONCISE BACKGROUND]

The following points are already known or disputed:

- [POINT]
- [DISAGREEMENT]
- [UNCERTAINTY]

Do not simply repeat these assumptions. Test them against the available
evidence and identify where they are incomplete or wrong.

# Questions to answer

1. [CORE QUESTION]
2. [CORE QUESTION]
3. [SECONDARY QUESTION]
4. [SECONDARY QUESTION]

Identify additional issues that are necessary to answer the mission but were
omitted from this list.

# Research and verification requirements

- Prefer primary and authoritative sources.
- Locate original publications or official records whenever possible.
- Use secondary sources mainly for discovery, context, or clearly attributed
  interpretation.
- Trace important claims to exact supporting passages, sections, pages,
  tables, figures, equations, datasets, or official statements when
  available.
- Give DOI values or canonical URLs for scholarly works when available.
- Preserve meaningful quantitative details, including units, definitions,
  denominators, uncertainty, and study conditions.
- Distinguish what a source directly demonstrates from what is inferred.
- Investigate contradictory evidence and explain plausible reasons for the
  disagreement.
- State clearly when a primary source is inaccessible or a claim cannot be
  verified.
- Actively test strong claims such as "first," "none," "no prior work,"
  "always," or "proven" by searching for counterexamples and alternative
  terminology.
- Do not impose a date range unless the research question requires one.
  Select foundational and later evidence for relevance and authority.

# Deliverable

Write a full report in [LANGUAGE].

Organize the report according to the research problem. A useful structure may
include:

- executive findings;
- background and definitions;
- evidence synthesis for each core question;
- methods or mechanisms where relevant;
- quantitative findings and study conditions;
- areas of agreement and disagreement;
- limitations and unresolved questions;
- implications for [INTENDED USE];
- references.

Adapt this structure when another organization better fits the subject.

Use tables only where they materially improve comparison, such as claim-level
verification, study characteristics, competing equations, or conflicting
numerical estimates. Tables should complement the analysis rather than
replace the report.

Cite evidence at the point of use. Include a references section containing
the sources materially relied upon, with enough bibliographic information to
identify and retrieve each source.

End with a clear account of:

- the most defensible conclusions;
- claims that remain uncertain;
- evidence that would most improve confidence.
```

## Literature investigation addendum

Append when the task is a literature review, methodological survey, or
evidence synthesis:

```markdown
# Literature-investigation requirements

- Identify foundational works, major methodological developments, and the
  strongest representative evidence without assuming a fixed publication
  window.
- For pivotal studies, recover the research question, data or experiment,
  method, principal result, relevant magnitude or uncertainty, limitations,
  and the exact claim the study can support.
- Follow backward and forward citation relationships where useful.
- Separate broad scholarly agreement from results that depend on a
  particular dataset, location, model, population, or experimental design.
- Synthesize the literature instead of producing an annotated list of papers.
- Treat proposed research gaps as hypotheses and search actively for
  counterexamples, adjacent terminology, and earlier formulations.
```

## Fact verification addendum

Append when the task audits factual, numerical, bibliographic, or
methodological claims:

```markdown
# Fact-verification requirements

- Decompose compound statements into atomic claims.
- For each material claim, assign one of: SUPPORTED, PARTIALLY SUPPORTED,
  REFUTED, or UNVERIFIABLE.
- Give the strongest primary source, the exact evidence location when
  available, and a short explanation of why it supports or fails to support
  the claim.
- Do not mark a claim as supported merely because it is plausible or repeated
  by multiple secondary sources.
- Reconcile conflicting figures by checking definitions, units, coverage,
  revisions, and measurement periods.
- Provide publication-ready replacement wording for claims that are
  overstated or insufficiently supported.
- A claim-level table is appropriate, but accompany it with narrative
  analysis of conflicts, caveats, and overall implications.
```

## Research-gap addendum

Append when evaluating novelty or an asserted absence of prior work:

```markdown
# Research-gap verification

- Treat every absence or novelty statement as a claim requiring an active
  counterexample search.
- Search synonyms, older terminology, adjacent disciplines, related methods,
  and citations from the most relevant papers.
- Distinguish "no prior work exists" from narrower and more defensible
  statements such as "no study was located that combines these specific
  conditions."
- Report the search boundary and plausible reasons relevant work may have
  been missed.
- Propose cautious replacement wording that remains accurate under peer
  review.
```
