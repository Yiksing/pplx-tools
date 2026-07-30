# 6. Degraded mode: private checkout unavailable

Part of the privacy-release-gate skill. Loaded when the sibling private
archive checkout is absent or unreadable.

When the sibling private archive checkout is absent or unreadable, the gate
runs degraded — it never silently passes.

Still **must run and pass** (zero hits / exit 0, no private input needed):

- §1 ban-word grep (patterns are inline in SKILL.md §1);
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
