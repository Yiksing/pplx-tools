# CI failure playbook (field lessons)

Failures of the quality / translate-docs workflows, recorded as
symptom → cause → fix.

1. **quality red after a force push (changed-base check)**: the push event's
   before-SHA is the discarded pre-rewrite commit, so the "base must be an
   available ancestor of HEAD" check fails (`git cat-file`: not a valid
   object name). Fix: `gh workflow run quality.yml -f changed_base=<real-ancestor-sha>`
   (the last shared ancestor). One-off side effect; never recurs on normal
   pushes.
2. **A manual quality run does not chain into translate-docs**: translate's
   trigger requires quality success **and** the quality event being `push`
   (`workflow_dispatch` does not qualify) — after manually re-running
   quality, also `gh workflow run translate-docs.yml` yourself. Not a bug.
3. **paths-filtered workflows do not fire after an unrelated-history push**:
   a push whose new history shares no ancestor with the old one defeats the
   `docs/**` path filter → deploy the docs manually once with
   `uv run mkdocs gh-deploy --force`.
4. **New test modules must be registered in the same commit**:
   `scripts/audit_docs.py` requires every `tests/*.py` to appear in
   `docs/development/testing.md` (+ zh-CN), otherwise quality fails with
   "repository entry is missing from test-modules". When adding a test file,
   edit the bilingual inventory row in the same commit and verify locally
   with `uv run python scripts/audit_docs.py --machine-mode allow-stale`.
5. **Do not touch config on a one-off secret error**: translate failing with
   `DEEKSEEK_API_KEY is not configured` while the secret exists
   (`gh secret list`) and adjacent runs succeed is a transient
   secret-delivery fault. Order of action: verify with `gh secret list` →
   re-run `gh workflow run translate-docs.yml`; only if it still fails,
   inspect the secret's content/scope.

Generic moves: `gh run list --workflow <w>` for status,
`gh run view <id> --log-failed` for failure logs, `gh workflow run <w>` to
re-run manually. When CI goes red, first classify "real defect vs
trigger-context side effect" — after any force operation (push / gh-deploy),
suspect the latter first.
