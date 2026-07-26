#!/usr/bin/env python3
"""Block-level bilingual comment/docstring audit (EN first, ZH second).

Usage:
  python pplx_audit.py [--repo PATH] [file ...]

  --repo PATH   repo root to audit (default: $PPLX_AUDIT_REPO or cwd)
  file ...      audit only these files (default: pplx_export/**/*.py + tests/**/*.py)

Rules checked (convention: English first, Chinese second):
  - A contiguous run of full-line comments at the same indent is one block.
    Every block must be: English line(s) first, then Chinese line(s).
    ZH-only block / EN-only block / EN-after-ZH are all violations.
  - Pragma comments (noqa/type: ignore/pylint/fmt/isort/shebang/coding) exempt.
  - Pure divider comments (no letters, no CJK) exempt.
  - Short trailing comments that are pure technical enumerations
    (e.g. `# DOC_FILE / SLIDES / ...`, no CJK) are exempt;
    trailing comments containing CJK are violations (hoist them above the line).
  - Docstrings must start with English; a docstring containing any CJK must not
    start with CJK; an English-only docstring is reported as a violation.

Exit code 0 = clean, 1 = violations found.
"""
import ast
import os
import re
import sys
import pathlib

CJK = re.compile(r'[\u3000-\u30FF\u3400-\u9FFF\uFF00-\uFFEF]')
ALPHA = re.compile(r'[A-Za-z]')
PRAGMA = re.compile(r'(noqa|type:\s*ignore|pylint|pragma|fmt:|isort|#!/|coding:|-\*-)')


def audit(p: pathlib.Path, repo: pathlib.Path):
    text = p.read_text(encoding='utf-8')
    lines = text.splitlines()
    probs = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith('#') and not PRAGMA.search(s):
            indent = len(ln) - len(ln.lstrip())
            j = i
            block = []
            while j < len(lines):
                l2 = lines[j]
                s2 = l2.strip()
                ind2 = len(l2) - len(l2.lstrip())
                if s2.startswith('#') and ind2 == indent and not PRAGMA.search(s2):
                    block.append((j + 1, s2))
                    j += 1
                else:
                    break
            han = [n for n, s2 in block if CJK.search(s2)]
            nonhan = [n for n, s2 in block if not CJK.search(s2) and ALPHA.search(s2)]
            if han and nonhan:
                if min(han) < min(nonhan):
                    probs.append(f'L{min(han)} block starts with ZH (or ZH before EN)')
                elif max(nonhan) > min(han):
                    probs.append(f'L{max(nonhan)} EN after ZH in block starting L{block[0][0]}')
            elif han and not nonhan:
                probs.append(f'L{min(han)} ZH-only comment block')
            elif nonhan and not han:
                probs.append(f'L{min(nonhan)} EN-only comment block')
            i = j
        else:
            i += 1
    # trailing comments containing CJK
    for n, ln in enumerate(lines, 1):
        m = re.search(r'\S\s+#(.*)', ln)
        if m and not ln.strip().startswith('#') and CJK.search(m.group(1)):
            probs.append(f'L{n} trailing ZH comment: {m.group(1).strip()[:40]!r}')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        probs.append('PARSE ERROR')
        return probs
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds is None or not ds.strip():
                continue
            first = ds.strip().splitlines()[0]
            lnno = getattr(node, 'lineno', 1)
            name = getattr(node, 'name', '<module>')
            if CJK.search(first):
                probs.append(f'L{lnno} docstring starts with ZH ({name})')
            elif not CJK.search(ds):
                probs.append(f'L{lnno} EN-only docstring ({name})')
    return probs


def main():
    args = sys.argv[1:]
    repo = pathlib.Path(os.environ.get('PPLX_AUDIT_REPO', '.')).resolve()
    if args[:1] == ['--repo']:
        repo = pathlib.Path(args[1]).resolve()
        args = args[2:]
    if args:
        files = [pathlib.Path(a) if pathlib.Path(a).is_absolute() else repo / a for a in args]
    else:
        files = sorted(list(repo.glob('pplx_export/**/*.py')) + list(repo.glob('tests/**/*.py')))
    bad = 0
    for p in files:
        probs = audit(p, repo)
        if probs:
            bad += 1
            rel = p.relative_to(repo) if p.is_relative_to(repo) else p
            print(f'{rel}: {len(probs)}')
            for x in probs:
                print(f'    {x}')
    if bad:
        print(f'\n{bad} file(s) with issues')
        sys.exit(1)
    print(f'CLEAN: {len(files)} file(s)')


if __name__ == '__main__':
    main()
