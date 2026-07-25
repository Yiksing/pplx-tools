# Quality and deployment pipeline

## `quality.yml`

Triggers on pull requests, pushes to `main`, and manual dispatch. Its validation
job runs:

1. full-history checkout, needed for changed-base comparisons;
2. locked dependency verification and frozen synchronization;
3. documentation audit in `allow-stale` mode, always with an exact changed
   base: pull-request base SHA, push `before` SHA, or required manual input;
4. simulated-fixture residue check;
5. the complete offline test suite;
6. strict MkDocs build for every configured locale.

The workflow needs read-only repository contents. Pull-request annotations use
the audit's GitHub output format. No translation credential or external model
call belongs here.

## `translate-docs.yml`

The automatic path is eligible only after a successful push-triggered `quality`
run whose head branch is `main`. Manual dispatch remains an explicit
maintainer operation.

The build job:

1. checks out the exact quality-validated SHA and confirms it is still
   `origin/main`;
2. checks the dependency lock and synchronizes the frozen environment;
3. creates or verifies a generated-only checkpoint branch named from that SHA;
4. refreshes stable heading aliases and shows the incremental plan without
   credentials;
5. injects the repository credential only when the plan contains API-backed
   units, generating one commit per completed locale on the checkpoint branch;
6. verifies the manifest, audits with `--machine-mode required`, checks fixture
   residue, runs the full tests, and builds every locale strictly;
7. confirms both main and the remote checkpoint still match the validated
   history, then fast-forwards main once;
8. removes the promoted checkpoint branch and uploads the validated `site/`
   artifact.

Failed or cancelled runs may leave a generated-only checkpoint branch for
validated resume, but may not place partial locale batches on `main`.

The deployment job must `need` that build job and only deploy its artifact.
Keep Pages and OIDC permissions on this job rather than workflow-wide.

## Change matrix

| Change | Minimum targeted verification |
|---|---|
| Validation command/order | workflow contract tests plus the complete local `quality` sequence |
| Audit mode or base comparison | `tests/test_audit_docs.py`, workflow contract tests, and both canonical-document change cases |
| Translation trigger or generated commits | `tests/test_translate_docs.py`, offline `--plan`/`--check`, and concurrency/fast-forward review |
| Action release/runtime | authoritative release and commit verification, YAML diff, then inspection of a real Actions run |
| Workflow permissions or secrets | event-trust analysis and job-level permission review; never print a credential |
| Pages artifact/dependency | strict local build, artifact producer/consumer review, then deployment-run inspection |

Use a writable task-specific `UV_CACHE_DIR` only when the execution sandbox
cannot access uv's default cache. That is an environment workaround, not a
workflow change.
