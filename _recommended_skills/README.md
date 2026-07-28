# Recommended agent skills

This directory contains agent skills recommended for users of `pplx-tools`
after reviewing the tool implementation, its archive contract, and observed
research workflows.

It is distinct from `_platform_context`:

- `_platform_context` preserves snapshots of skills and tools supplied by the
  Perplexity Computer environment.
- `_recommended_skills` contains maintained recommendations for using the
  public CLI tools from an external agent.

## Skills

- `delegate-pplx-deep-research` — delegate an evidence-heavy investigation to
  a subagent, have that subagent run `pplx-ask` in deep-research mode, and
  return the archived report together with its complete returned-source
  inventory.
- `search-with-pplx` — let the main agent run focused `pplx-ask` searches and
  integrate the archived answer and sources.

Each skill is self-contained under `skills/`. Install or copy only the skill
needed for a task.

## Design principles

- Keep automatic archiving enabled.
- Treat archived reports and returned-source inventories as deliverables, not
  disposable execution traces.
- Use detailed, task-specific research briefs instead of a universal output
  table.
- Prefer source authority and relevance over arbitrary publication-date
  windows.
- Budget wall-clock time for transport backoff (waits of up to 300 s per
  retry); treat long silences as backoff, never wrap calls in short hard
  timeouts.
- Minimize private context before sending a prompt to an external service.
- Distinguish sources returned by the platform, sources materially cited in a
  report, and sources independently opened and verified by the agent.
