# Repository agent routing

Use progressive disclosure for repository skills:

- Route from skill names and descriptions before reading any `SKILL.md`.
- A normal task loads zero or one primary repository skill.
- Load a second repository skill only when the user-authorized change genuinely
  crosses two ownership surfaces.
- Do not enumerate or preload every file under `.agents/skills/`.
- Running tests, validation, review handoff, or Git handoff does not by itself
  trigger another skill.
- Treat review, design, implementation, validation, and documentation as
  sequential phases. Re-route between phases instead of loading every phase at
  once.
- Read a linked reference only when the triggering condition beside that link
  applies. Do not recursively load references.
- Explicitly named user skills take precedence over these routing defaults.

Resolve the repository root with `git rev-parse --show-toplevel`. Run commands
with that directory as the tool `workdir` (or use an equivalent explicit
project/root option); never assume the agent started in the repository root.
