# 4. Bilingual-comment audit (bundled script)

Part of the privacy-release-gate skill. Loaded when running the bundled
`pplx_audit.py` bilingual-comment audit.

`pplx_audit.py` in this skill's directory: block-level check for "English
comment block first, Chinese second", docstring EN-then-ZH order, trailing
Chinese comments, and EN-only/ZH-only blocks. Usage:

```bash
python .agents/skills/privacy-release-gate/pplx_audit.py --repo .            # full scan (pplx_export/ + tests/)
python .agents/skills/privacy-release-gate/pplx_audit.py --repo . <file...>  # specific files
# exit code 0 = CLEAN; violations are reported as file:line plus a type
```
