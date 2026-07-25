# Documentation audit contracts

Use this map before changing a finding family:

| Family | Contract |
|---|---|
| `DOC-PAIR-*` | English and Simplified Chinese canonical files exist together; `--changed-base` requires both sides across the commit range plus staged, unstaged, and untracked worktree changes. An unusable Git base is invocation failure exit `2`, not a finding. |
| `DOC-HEAD-*`, `DOC-FENCE-*` | Canonical heading levels and fence languages remain structurally aligned; stored headings do not contain manual outline numbers. |
| `DOC-LINK-*` | Repository-local links resolve and cannot escape the repository root. External URLs and page fragments are not fetched. |
| `DOC-SRC-*` | Python source references resolve unambiguously and requested line ranges exist. |
| `DOC-INV-*` | Marked test-module and fixture-directory inventories match the filesystem without omissions, stale entries, or duplicates. |
| `DOC-CONTRACT-*` | Fixture documentation explicitly identifies the committed fixture source as simulated data and rejects obsolete provenance claims. |
| `DOC-I18N-*` | Locale configuration, generated metadata, manifests, hashes, heading/fence shape, and source-heading aliases agree at the strictness selected by `--machine-mode`. |

## Machine modes

- `ignore`: omit generated-locale validation. Reserve for deliberately scoped
  diagnostics.
- `allow-stale`: validate canonical documents and any safe existing generated
  structure without requiring every generated output to be current. Use in the
  pull-request and pre-translation quality gate.
- `required`: require all configured machine outputs, catalogs, metadata,
  hashes, model/prompt records, and aliases to be present and current. Use
  after translation and before deployment.

## Unit-test shape

Build all audit scenarios in a temporary miniature repository. Populate only
the files the contract requires, mutate one property, call
`audit_repository(...)` or `main(...)`, and assert the exact code plus the
important path/message field. Avoid asserting an entire formatted report
unless formatting itself is under test.

For a new contract, cover:

1. a clean repository that remains clean;
2. the smallest violation;
3. a nearby valid form that prevents a false positive;
4. output escaping and exit behavior if diagnostics changed;
5. proof that the audit leaves every input byte unchanged when new I/O is
   introduced.

Keep the public CLI in `main`, repository traversal in
`audit_repository`, and parsing/checking in focused helpers. Do not catch broad
exceptions below the last-resort CLI boundary.
