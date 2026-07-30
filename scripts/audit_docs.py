#!/usr/bin/env python3
"""Read-only, offline documentation contract audit.

Checks bilingual structure, repository-local links, source-line references,
test/fixture inventories, and the simulated-fixture provenance contract.

只读、离线的文档契约审计：检查双语结构、仓库内链接、源码行号引用、
测试/fixture 清单，以及模拟 fixture 来源契约。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Sequence
from urllib.parse import unquote, urlsplit

from scripts.i18n_config import (
    I18nConfig,
    I18nConfigError,
    canonical_default_documents,
    canonical_source_path,
    generated_document_path,
    load_i18n_config,
    sha256_file,
    split_locale_suffix,
)
from scripts.translate_docs import (
    add_source_heading_anchors,
    parse_translation_metadata,
)


Severity = Literal["error", "warning"]
MachineMode = Literal["ignore", "allow-stale", "required"]


class AuditInvocationError(RuntimeError):
    """Raised when requested audit inputs cannot be evaluated."""


EXPLICIT_PAIRS = (
    ("README.md", "README.zh-CN.md"),
    ("pplx_export/README.md", "pplx_export/README.zh-CN.md"),
    ("tests/fixtures/README.md", "tests/fixtures/README.zh-CN.md"),
)
UNPAIRED_DOCS = {"docs/README.md"}
MARKDOWN_EXTRAS = {
    "README.md",
    "README.zh-CN.md",
    "pplx_export/README.md",
    "pplx_export/README.zh-CN.md",
    "tests/fixtures/README.md",
    "tests/fixtures/README.zh-CN.md",
}
TEST_INVENTORY_DOCS = (
    "docs/development/testing.md",
    "docs/development/testing.zh-CN.md",
)
FIXTURE_INVENTORY_DOCS = (
    "docs/development/fixtures.md",
    "docs/development/fixtures.zh-CN.md",
    "tests/fixtures/README.md",
    "tests/fixtures/README.zh-CN.md",
)
SOURCE_DIRS = ("pplx_export", "tests", "scripts")
FIXTURE_CONTRACT = "<!-- audit:contract fixture-source=simulated -->"
OLD_PROVENANCE_PHRASES = (
    "Raw API captures of representative threads",
    "synthetic raw API captures",
    "raw data of representative threads copied from `web_archive/`",
    "代表性线程的原始 API 抓取",
    "合成原始 API 抓取",
    "从 `web_archive/` 复制的代表性线程原始数据",
)

_FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")
_HEADING_RE = re.compile(r"^[ ]{0,3}(#{1,6})[ \t]+(.+?)\s*$")
_MANUAL_OUTLINE_RE = re.compile(
    r"^\d{1,2}(?:\.\d+)*\.?[ \t]+"
)
_INLINE_LINK_RE = re.compile(
    r"!?\[[^\]]*\]\(\s*(?P<target><[^>\n]+>|[^)\s]+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
_REFERENCE_LINK_RE = re.compile(
    r"^[ ]{0,3}\[[^\]]+\]:\s*(?P<target><[^>\n]+>|\S+)"
)
_SOURCE_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.py)"
    r":(?P<ranges>\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)"
)
_EXACT_TEST_RE = re.compile(r"`(test_[A-Za-z0-9_]+\.py)`")
_EXACT_FIXTURE_RE = re.compile(
    r"`((?:[a-z0-9_]+_demo|scenario_[A-Za-z0-9_-]+))`"
)
_MARKER_RE_TEMPLATE = (
    r"<!--\s*audit:inventory\s+{name}\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*/audit:inventory\s+{name}\s*-->"
)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    path: str
    line: int | None
    message: str
    hint: str | None = None


@dataclass(frozen=True)
class AuditStats:
    bilingual_pairs: int = 0
    machine_locales: int = 0
    machine_documents: int = 0
    markdown_links: int = 0
    source_references: int = 0
    test_modules: int = 0
    fixture_directories: int = 0


@dataclass
class AuditReport:
    findings: list[Finding]
    stats: AuditStats

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


@dataclass(frozen=True)
class Fence:
    language: str
    line: int


@dataclass
class MarkdownInfo:
    headings: list[tuple[int, int]]
    manual_outline_lines: list[int]
    fences: list[Fence]
    links: list[tuple[int, str]]
    source_refs: list[tuple[int, str, str]]
    findings: list[Finding]


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _finding(
    code: str,
    path: str,
    line: int | None,
    message: str,
    *,
    severity: Severity = "error",
    hint: str | None = None,
) -> Finding:
    return Finding(code, severity, path, line, message, hint)


def _source_refs(line: str, line_number: int) -> list[tuple[int, str, str]]:
    return [
        (line_number, match.group("path"), match.group("ranges"))
        for match in _SOURCE_REF_RE.finditer(line)
    ]


def scan_markdown(path: Path, relative_path: str) -> MarkdownInfo:
    """Scan the Markdown subset needed by the repository audit."""
    headings: list[tuple[int, int]] = []
    manual_outline_lines: list[int] = []
    fences: list[Fence] = []
    links: list[tuple[int, str]] = []
    refs: list[tuple[int, str, str]] = []
    findings: list[Finding] = []
    fence_char: str | None = None
    fence_length = 0
    fence_language = ""
    fence_start = 0

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return MarkdownInfo(
            [], [], [], [], [],
            [_finding("DOC-READ-001", relative_path, None, f"cannot read UTF-8 text: {exc}")],
        )

    for line_number, line in enumerate(lines, 1):
        fence_match = _FENCE_RE.match(line)
        if fence_char is not None:
            if fence_match:
                token = fence_match.group(1)
                rest = fence_match.group(2)
                if (
                    token[0] == fence_char
                    and len(token) >= fence_length
                    and not rest.strip()
                ):
                    fence_char = None
                    fence_length = 0
                    fence_language = ""
                    fence_start = 0
                    continue
            if fence_language == "mermaid":
                refs.extend(_source_refs(line, line_number))
            continue

        if fence_match:
            token = fence_match.group(1)
            rest = fence_match.group(2).strip()
            language = rest.split(maxsplit=1)[0].lower() if rest else ""
            fences.append(Fence(language, line_number))
            fence_char = token[0]
            fence_length = len(token)
            fence_language = language
            fence_start = line_number
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            headings.append((len(heading_match.group(1)), line_number))
            if _MANUAL_OUTLINE_RE.match(heading_match.group(2)):
                manual_outline_lines.append(line_number)

        for match in _INLINE_LINK_RE.finditer(line):
            links.append((line_number, match.group("target")))
        reference_match = _REFERENCE_LINK_RE.match(line)
        if reference_match:
            links.append((line_number, reference_match.group("target")))
        refs.extend(_source_refs(line, line_number))

    if fence_char is not None:
        findings.append(
            _finding(
                "DOC-FENCE-001",
                relative_path,
                fence_start,
                "unclosed Markdown code fence",
            )
        )

    return MarkdownInfo(
        headings,
        manual_outline_lines,
        fences,
        links,
        refs,
        findings,
    )


def _docs_pairs(
    root: Path,
    i18n: I18nConfig | None = None,
) -> tuple[list[tuple[Path, Path]], list[Finding]]:
    findings: list[Finding] = []
    pairs: list[tuple[Path, Path]] = []
    docs_root = root / "docs"

    if docs_root.exists():
        for path in sorted(docs_root.rglob("*.md")):
            relative = _rel(root, path)
            if relative in UNPAIRED_DOCS:
                continue
            if i18n is not None:
                _, locale = split_locale_suffix(path, i18n)
                if locale != i18n.default_locale:
                    continue
            elif path.name.endswith(".zh-CN.md"):
                continue
            zh_path = path.with_name(f"{path.stem}.zh-CN.md")
            if not zh_path.exists():
                findings.append(
                    _finding(
                        "DOC-PAIR-001",
                        relative,
                        1,
                        f"missing Chinese pair: {_rel(root, zh_path)}",
                    )
                )
            else:
                pairs.append((path, zh_path))

        for zh_path in sorted(docs_root.rglob("*.zh-CN.md")):
            en_path = zh_path.with_name(zh_path.name.removesuffix(".zh-CN.md") + ".md")
            if not en_path.exists():
                findings.append(
                    _finding(
                        "DOC-PAIR-001",
                        _rel(root, zh_path),
                        1,
                        f"missing English pair: {_rel(root, en_path)}",
                    )
                )

    for en_rel, zh_rel in EXPLICIT_PAIRS:
        en_path, zh_path = root / en_rel, root / zh_rel
        if not en_path.exists():
            findings.append(
                _finding("DOC-PAIR-001", en_rel, 1, f"missing English document: {en_rel}")
            )
        if not zh_path.exists():
            findings.append(
                _finding("DOC-PAIR-001", zh_rel, 1, f"missing Chinese document: {zh_rel}")
            )
        if en_path.exists() and zh_path.exists():
            pairs.append((en_path, zh_path))

    return pairs, findings


def _markdown_files(root: Path) -> list[Path]:
    files = set((root / "docs").rglob("*.md")) if (root / "docs").exists() else set()
    files.update(root / relative for relative in MARKDOWN_EXTRAS if (root / relative).exists())
    return sorted(files)


def _normalize_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return unquote(target)


def _check_link(root: Path, source: Path, line: int, raw_target: str) -> Finding | None:
    target = _normalize_target(raw_target)
    split = urlsplit(target)
    if split.scheme or split.netloc or target.startswith(("#", "/")):
        return None
    path_part = split.path
    if not path_part:
        return None
    candidate = (source.parent / path_part).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return _finding(
            "DOC-LINK-002",
            _rel(root, source),
            line,
            f"local link escapes repository root: {raw_target}",
        )
    if not candidate.exists():
        return _finding(
            "DOC-LINK-001",
            _rel(root, source),
            line,
            f"local link target does not exist: {raw_target}",
        )
    return None


def _source_index(root: Path) -> tuple[list[Path], dict[str, list[Path]]]:
    paths: list[Path] = []
    by_name: dict[str, list[Path]] = {}
    for directory in SOURCE_DIRS:
        base = root / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            paths.append(path)
            by_name.setdefault(path.name, []).append(path)
    return paths, by_name


def _resolve_source(
    root: Path,
    token: str,
    paths: list[Path],
    by_name: dict[str, list[Path]],
) -> list[Path]:
    explicit = root / token
    if explicit.is_file():
        return [explicit]
    if "/" not in token:
        return by_name.get(token, [])
    suffix = "/" + token
    return [path for path in paths if _rel(root, path).endswith(suffix)]


def _parse_ranges(value: str) -> list[tuple[int, int]]:
    parsed: list[tuple[int, int]] = []
    for part in value.split(","):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            parsed.append((int(start_text), int(end_text)))
        else:
            number = int(part)
            parsed.append((number, number))
    return parsed


def _check_source_ref(
    root: Path,
    markdown_path: Path,
    line: int,
    token: str,
    ranges: str,
    source_paths: list[Path],
    by_name: dict[str, list[Path]],
) -> list[Finding]:
    relative_markdown = _rel(root, markdown_path)
    candidates = _resolve_source(root, token, source_paths, by_name)
    if not candidates:
        return [
            _finding(
                "DOC-SRC-001",
                relative_markdown,
                line,
                f"source reference cannot be resolved: {token}:{ranges}",
            )
        ]
    if len(candidates) > 1:
        choices = ", ".join(_rel(root, path) for path in candidates)
        return [
            _finding(
                "DOC-SRC-002",
                relative_markdown,
                line,
                f"ambiguous source reference {token}:{ranges}; candidates: {choices}",
            )
        ]

    source = candidates[0]
    try:
        line_count = len(source.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError) as exc:
        return [
            _finding(
                "DOC-SRC-001",
                relative_markdown,
                line,
                f"cannot read referenced source {_rel(root, source)}: {exc}",
            )
        ]

    findings: list[Finding] = []
    for start, end in _parse_ranges(ranges):
        if start < 1 or end < start:
            findings.append(
                _finding(
                    "DOC-SRC-004",
                    relative_markdown,
                    line,
                    f"invalid source range {token}:{start}-{end}",
                )
            )
        elif end > line_count:
            findings.append(
                _finding(
                    "DOC-SRC-003",
                    relative_markdown,
                    line,
                    f"{token}:{start}-{end} exceeds file length {line_count}",
                )
            )
    return findings


def _marker_body(
    text: str,
    marker_name: str,
    relative_path: str,
) -> tuple[str | None, list[Finding]]:
    pattern = re.compile(
        _MARKER_RE_TEMPLATE.format(name=re.escape(marker_name)),
        re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        return None, [
            _finding(
                "DOC-INV-001",
                relative_path,
                None,
                f"expected exactly one inventory marker pair for {marker_name}, found {len(matches)}",
            )
        ]
    return matches[0].group("body"), []


def _inventory_findings(
    root: Path,
    *,
    marker_name: str,
    documents: Sequence[str],
    actual: set[str],
    token_pattern: re.Pattern[str],
) -> list[Finding]:
    findings: list[Finding] = []
    for relative in documents:
        path = root / relative
        if not path.exists():
            findings.append(
                _finding("DOC-INV-001", relative, None, "inventory document is missing")
            )
            continue
        text = path.read_text(encoding="utf-8")
        body, marker_findings = _marker_body(text, marker_name, relative)
        findings.extend(marker_findings)
        if body is None:
            continue
        entries = token_pattern.findall(body)
        documented = set(entries)
        for duplicate in sorted({entry for entry in entries if entries.count(entry) > 1}):
            findings.append(
                _finding(
                    "DOC-INV-004",
                    relative,
                    None,
                    f"inventory entry is duplicated: {duplicate}",
                )
            )
        for missing in sorted(actual - documented):
            findings.append(
                _finding(
                    "DOC-INV-002",
                    relative,
                    None,
                    f"repository entry is missing from {marker_name}: {missing}",
                )
            )
        for stale in sorted(documented - actual):
            findings.append(
                _finding(
                    "DOC-INV-003",
                    relative,
                    None,
                    f"documented {marker_name} entry does not exist: {stale}",
                )
            )
    return findings


def _fixture_directories(root: Path) -> set[str]:
    base = root / "tests" / "fixtures"
    if not base.exists():
        return set()
    return {
        path.name
        for path in base.iterdir()
        if (
            path.is_dir()
            and not path.name.startswith(".")
            and path.name != "__pycache__"
            and ((path / "raw_entries.json").exists() or (path / "thread.json").exists())
        )
    }


def _provenance_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative in FIXTURE_INVENTORY_DOCS:
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        count = text.count(FIXTURE_CONTRACT)
        if count != 1:
            findings.append(
                _finding(
                    "DOC-CONTRACT-001",
                    relative,
                    None,
                    f"expected one simulated-fixture contract marker, found {count}",
                )
            )
        visible_term = "模拟数据" if relative.endswith(".zh-CN.md") else "simulated data"
        if visible_term.lower() not in text.lower():
            findings.append(
                _finding(
                    "DOC-CONTRACT-002",
                    relative,
                    None,
                    f"visible fixture source statement must contain {visible_term!r}",
                )
            )
        normalized = " ".join(text.split())
        for phrase in OLD_PROVENANCE_PHRASES:
            if phrase in normalized:
                findings.append(
                    _finding(
                        "DOC-CONTRACT-003",
                        relative,
                        None,
                        f"stale fixture provenance statement reappeared: {phrase}",
                    )
                )
    return findings


def _load_manifest_for_audit(
    root: Path,
    i18n: I18nConfig,
    machine_mode: MachineMode,
) -> tuple[dict[str, object] | None, list[Finding]]:
    if not i18n.manifest_path.exists():
        if machine_mode == "required":
            return None, [
                _finding(
                    "DOC-I18N-002",
                    _rel(root, i18n.manifest_path),
                    None,
                    "machine translation manifest is missing",
                )
            ]
        return None, []
    try:
        value = json.loads(i18n.manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [
            _finding(
                "DOC-I18N-002",
                _rel(root, i18n.manifest_path),
                None,
                f"cannot read machine translation manifest: {exc}",
            )
        ]
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or not isinstance(value.get("documents"), dict)
        or not isinstance(value.get("catalogs"), dict)
    ):
        return None, [
            _finding(
                "DOC-I18N-002",
                _rel(root, i18n.manifest_path),
                None,
                "machine translation manifest has an invalid schema",
            )
        ]
    return value, []


def _machine_translation_findings(
    root: Path,
    i18n: I18nConfig,
    scans: dict[Path, MarkdownInfo],
    machine_mode: MachineMode,
) -> tuple[list[Finding], int]:
    if machine_mode == "ignore":
        return [], 0
    findings: list[Finding] = []
    manifest, manifest_findings = _load_manifest_for_audit(
        root,
        i18n,
        machine_mode,
    )
    findings.extend(manifest_findings)
    document_entries = (
        manifest.get("documents", {})
        if isinstance(manifest, dict)
        else {}
    )
    catalog_entries = (
        manifest.get("catalogs", {})
        if isinstance(manifest, dict)
        else {}
    )
    assert isinstance(document_entries, dict)
    assert isinstance(catalog_entries, dict)
    resolved_model = (
        os.environ.get("DEEPSEEK_TRANSLATION_MODEL")
        or i18n.translation.model
    )
    machine_documents = 0

    for default_path in canonical_default_documents(i18n):
        for locale in i18n.machine_locales:
            assert locale.source is not None
            source_path = canonical_source_path(
                default_path,
                locale.source,
                i18n,
            )
            output_path = generated_document_path(
                default_path,
                locale.code,
                i18n,
            )
            output_relative = _rel(root, output_path)
            key = (
                f"{default_path.relative_to(root).as_posix()}::{locale.code}"
            )
            if not output_path.is_file():
                if machine_mode == "required":
                    findings.append(
                        _finding(
                            "DOC-I18N-001",
                            output_relative,
                            1,
                            f"missing machine translation from "
                            f"{_rel(root, source_path)}",
                        )
                    )
                continue
            machine_documents += 1
            entry = document_entries.get(key)
            source_hash = sha256_file(source_path)
            source_info = scans.get(source_path) or scan_markdown(
                source_path,
                _rel(root, source_path),
            )
            output_info = scans.get(output_path) or scan_markdown(
                output_path,
                output_relative,
            )
            source_headings = [level for level, _ in source_info.headings]
            output_headings = [level for level, _ in output_info.headings]
            source_fences = [fence.language for fence in source_info.fences]
            output_fences = [fence.language for fence in output_info.fences]
            source_was_current = (
                isinstance(entry, dict)
                and entry.get("source_sha256") == source_hash
            )
            check_current_shape = (
                (machine_mode == "required" and locale.frozen_since is None)
                or source_was_current
            )
            if check_current_shape and source_headings != output_headings:
                findings.append(
                    _finding(
                        "DOC-I18N-006",
                        output_relative,
                        1,
                        f"machine heading sequence differs from "
                        f"{_rel(root, source_path)}: "
                        f"{output_headings} != {source_headings}",
                    )
                )
            if check_current_shape and source_fences != output_fences:
                findings.append(
                    _finding(
                        "DOC-I18N-006",
                        output_relative,
                        1,
                        f"machine code-fence sequence differs from "
                        f"{_rel(root, source_path)}: "
                        f"{output_fences} != {source_fences}",
                    )
                )
            if machine_mode == "required" and locale.frozen_since is None:
                source_text = source_path.read_text(encoding="utf-8")
                output_text = output_path.read_text(encoding="utf-8")
                if add_source_heading_anchors(
                    source_text,
                    output_text,
                ) != output_text:
                    findings.append(
                        _finding(
                            "DOC-I18N-008",
                            output_relative,
                            1,
                            "machine translation lacks stable canonical "
                            "heading anchors",
                        )
                    )

            metadata = parse_translation_metadata(
                output_path.read_text(encoding="utf-8")
            )
            expected_metadata = {
                "translation_kind": "machine",
                "translation_source_locale": locale.source,
                "translation_source_path": _rel(root, source_path),
            }
            for metadata_key, expected in expected_metadata.items():
                if metadata.get(metadata_key) != expected:
                    findings.append(
                        _finding(
                            "DOC-I18N-005",
                            output_relative,
                            1,
                            f"{metadata_key} must be {expected!r}",
                        )
                    )
            if not isinstance(entry, dict):
                findings.append(
                    _finding(
                        "DOC-I18N-002",
                        output_relative,
                        1,
                        f"manifest entry is missing: {key}",
                    )
                )
                continue
            if (
                metadata.get("translation_source_sha256")
                != entry.get("source_sha256")
            ):
                findings.append(
                    _finding(
                        "DOC-I18N-005",
                        output_relative,
                        1,
                        "front-matter source digest differs from manifest",
                    )
                )
            output_hash = sha256_file(output_path)
            if entry.get("output_sha256") != output_hash:
                findings.append(
                    _finding(
                        "DOC-I18N-004",
                        output_relative,
                        1,
                        "generated output digest differs from manifest",
                    )
                )
            if machine_mode == "required" and locale.frozen_since is None:
                if (
                    entry.get("source_sha256") != source_hash
                    or metadata.get("translation_source_sha256") != source_hash
                ):
                    findings.append(
                        _finding(
                            "DOC-I18N-003",
                            output_relative,
                            1,
                            f"machine translation is stale relative to "
                            f"{_rel(root, source_path)}",
                        )
                    )
                if (
                    entry.get("model") != resolved_model
                    or metadata.get("translation_model") != resolved_model
                    or metadata.get("translation_prompt_version")
                    != i18n.translation.prompt_version
                ):
                    findings.append(
                        _finding(
                            "DOC-I18N-003",
                            output_relative,
                            1,
                            "machine translation model or prompt version is stale",
                        )
                    )

    for locale in i18n.machine_locales:
        output_path = i18n.generated_catalog_dir / f"{locale.code}.json"
        relative = _rel(root, output_path)
        if not output_path.is_file():
            if machine_mode == "required":
                findings.append(
                    _finding(
                        "DOC-I18N-001",
                        relative,
                        None,
                        "localized site catalog is missing",
                    )
                )
            continue
        entry = catalog_entries.get(locale.code)
        if not isinstance(entry, dict):
            findings.append(
                _finding(
                    "DOC-I18N-002",
                    relative,
                    None,
                    "localized catalog manifest entry is missing",
                )
            )
            continue
        if entry.get("output_sha256") != sha256_file(output_path):
            findings.append(
                _finding(
                    "DOC-I18N-004",
                    relative,
                    None,
                    "localized catalog digest differs from manifest",
                )
            )
        if machine_mode == "required" and locale.frozen_since is None:
            assert locale.source is not None
            source_path = i18n.canonical_catalogs[locale.source]
            if (
                entry.get("source_sha256") != sha256_file(source_path)
                or entry.get("model") != resolved_model
            ):
                findings.append(
                    _finding(
                        "DOC-I18N-003",
                        relative,
                        None,
                        "localized catalog is stale",
                    )
                )
    return findings, machine_documents


def _i18n_registry_findings(
    root: Path,
    i18n: I18nConfig,
) -> list[Finding]:
    mkdocs_path = root / "mkdocs.yml"
    try:
        text = mkdocs_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [
            _finding(
                "DOC-I18N-007",
                "mkdocs.yml",
                None,
                f"cannot read MkDocs locale registry: {exc}",
            )
        ]
    mkdocs_locales = set(
        re.findall(
            r"^[ ]+- locale: ([a-z]{2}(?:-[A-Za-z]{2,4})?)$",
            text,
            re.MULTILINE,
        )
    )
    configured = set(i18n.locales)
    if mkdocs_locales == configured:
        return []
    return [
        _finding(
            "DOC-I18N-007",
            "mkdocs.yml",
            None,
            "MkDocs and translation locale registries differ: "
            f"missing={sorted(configured - mkdocs_locales)}, "
            f"unexpected={sorted(mkdocs_locales - configured)}",
        )
    ]


def _changed_pair_findings(
    root: Path,
    i18n: I18nConfig,
    base_ref: str,
) -> list[Finding]:
    commands = (
        (
            "committed range",
            [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=ACMRD",
                f"{base_ref}...HEAD",
                "--",
            ],
        ),
        (
            "staged worktree",
            [
                "git",
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=ACMRD",
                "--",
            ],
        ),
        (
            "unstaged worktree",
            [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=ACMRD",
                "--",
            ],
        ),
        (
            "untracked worktree",
            [
                "git",
                "ls-files",
                "--others",
                "--exclude-standard",
                "--",
            ],
        ),
    )
    changed: set[Path] = set()
    for context, command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = (
                exc.stderr.strip()
                if isinstance(exc, subprocess.CalledProcessError)
                and isinstance(exc.stderr, str)
                and exc.stderr.strip()
                else str(exc)
            )
            raise AuditInvocationError(
                "cannot determine changed canonical documents "
                f"from {context}: {detail}"
            ) from exc
        changed.update(
            Path(line)
            for line in result.stdout.splitlines()
            if line.strip()
        )
    findings: list[Finding] = []
    checked: set[tuple[Path, Path]] = set()
    docs_relative = i18n.docs_dir.relative_to(root)
    for path in sorted(changed):
        if path.suffix != ".md":
            continue
        try:
            path.relative_to(docs_relative)
        except ValueError:
            continue
        absolute = root / path
        default_path, locale = split_locale_suffix(absolute, i18n)
        if locale not in i18n.canonical_locales:
            continue
        default_relative = default_path.relative_to(root)
        if default_path.relative_to(i18n.docs_dir).as_posix() in set(
            i18n.excluded_docs
        ):
            continue
        zh_relative = default_path.with_name(
            f"{default_path.stem}.zh-CN.md"
        ).relative_to(root)
        pair = (default_relative, zh_relative)
        if pair in checked:
            continue
        checked.add(pair)
        touched = {candidate for candidate in pair if candidate in changed}
        if len(touched) == 1:
            changed_path = next(iter(touched))
            missing = zh_relative if changed_path == default_relative else default_relative
            findings.append(
                _finding(
                    "DOC-PAIR-002",
                    changed_path.as_posix(),
                    1,
                    f"canonical counterpart must change in the same PR: "
                    f"{missing.as_posix()}",
                )
            )

    for en_relative, zh_relative_text in EXPLICIT_PAIRS:
        pair = (Path(en_relative), Path(zh_relative_text))
        touched = {candidate for candidate in pair if candidate in changed}
        if len(touched) == 1:
            changed_path = next(iter(touched))
            missing = pair[1] if changed_path == pair[0] else pair[0]
            findings.append(
                _finding(
                    "DOC-PAIR-002",
                    changed_path.as_posix(),
                    1,
                    f"canonical counterpart must change in the same PR: "
                    f"{missing.as_posix()}",
                )
            )
    return findings


def audit_repository(
    root: Path,
    *,
    machine_mode: MachineMode = "allow-stale",
    changed_base: str | None = None,
) -> AuditReport:
    """Audit repository documentation without mutating any file."""
    root = root.resolve()
    findings: list[Finding] = []
    i18n: I18nConfig | None = None
    config_path = root / "i18n" / "config.toml"
    if config_path.exists():
        try:
            i18n = load_i18n_config(root)
        except I18nConfigError as exc:
            findings.append(
                _finding(
                    "DOC-I18N-000",
                    _rel(root, config_path),
                    None,
                    f"invalid i18n configuration: {exc}",
                )
            )
    pairs, pair_findings = _docs_pairs(root, i18n)
    findings.extend(pair_findings)
    markdown_paths = _markdown_files(root)
    scans: dict[Path, MarkdownInfo] = {}

    for path in markdown_paths:
        info = scan_markdown(path, _rel(root, path))
        scans[path] = info
        findings.extend(info.findings)
        enforce_source_headings = path.is_relative_to(root / "docs")
        if i18n is not None and enforce_source_headings:
            _, locale = split_locale_suffix(path, i18n)
            enforce_source_headings = (
                locale in i18n.canonical_locales
                or machine_mode == "required"
            )
        if enforce_source_headings:
            findings.extend(
                _finding(
                    "DOC-HEAD-002",
                    _rel(root, path),
                    line,
                    "manual outline number in Markdown heading",
                    hint=(
                        "remove the stored number; MkDocs adds page-local "
                        "numbers during rendering"
                    ),
                )
                for line in info.manual_outline_lines
            )

    for en_path, zh_path in pairs:
        en_info = scans.get(en_path) or scan_markdown(en_path, _rel(root, en_path))
        zh_info = scans.get(zh_path) or scan_markdown(zh_path, _rel(root, zh_path))
        en_levels = [level for level, _ in en_info.headings]
        zh_levels = [level for level, _ in zh_info.headings]
        if en_levels != zh_levels:
            findings.append(
                _finding(
                    "DOC-HEAD-001",
                    _rel(root, en_path),
                    1,
                    f"heading-level sequence differs from {_rel(root, zh_path)}: "
                    f"{en_levels} != {zh_levels}",
                )
            )
        en_languages = [fence.language for fence in en_info.fences]
        zh_languages = [fence.language for fence in zh_info.fences]
        if en_languages != zh_languages:
            findings.append(
                _finding(
                    "DOC-FENCE-002",
                    _rel(root, en_path),
                    1,
                    f"code-fence language sequence differs from {_rel(root, zh_path)}: "
                    f"{en_languages} != {zh_languages}",
                )
            )

    source_paths, by_name = _source_index(root)
    link_count = 0
    source_ref_count = 0
    for markdown_path, info in scans.items():
        if i18n is not None and machine_mode == "allow-stale":
            _, locale = split_locale_suffix(markdown_path, i18n)
            if locale not in i18n.canonical_locales:
                continue
        for line, target in info.links:
            link_count += 1
            finding = _check_link(root, markdown_path, line, target)
            if finding:
                findings.append(finding)
        for line, token, ranges in info.source_refs:
            source_ref_count += 1
            findings.extend(
                _check_source_ref(
                    root,
                    markdown_path,
                    line,
                    token,
                    ranges,
                    source_paths,
                    by_name,
                )
            )

    test_modules = {
        path.name for path in (root / "tests").glob("test_*.py")
    } if (root / "tests").exists() else set()
    fixture_directories = _fixture_directories(root)
    findings.extend(
        _inventory_findings(
            root,
            marker_name="test-modules",
            documents=TEST_INVENTORY_DOCS,
            actual=test_modules,
            token_pattern=_EXACT_TEST_RE,
        )
    )
    findings.extend(
        _inventory_findings(
            root,
            marker_name="fixture-directories",
            documents=FIXTURE_INVENTORY_DOCS,
            actual=fixture_directories,
            token_pattern=_EXACT_FIXTURE_RE,
        )
    )
    findings.extend(_provenance_findings(root))
    machine_documents = 0
    if i18n is not None:
        findings.extend(_i18n_registry_findings(root, i18n))
        machine_findings, machine_documents = _machine_translation_findings(
            root,
            i18n,
            scans,
            machine_mode,
        )
        findings.extend(machine_findings)
        if changed_base is not None:
            findings.extend(_changed_pair_findings(root, i18n, changed_base))

    findings.sort(
        key=lambda item: (
            item.path,
            item.line if item.line is not None else -1,
            item.code,
            item.message,
        )
    )
    return AuditReport(
        findings=findings,
        stats=AuditStats(
            bilingual_pairs=len(pairs),
            machine_locales=len(i18n.machine_locales) if i18n else 0,
            machine_documents=machine_documents,
            markdown_links=link_count,
            source_references=source_ref_count,
            test_modules=len(test_modules),
            fixture_directories=len(fixture_directories),
        ),
    )


def _summary(report: AuditReport) -> tuple[int, int]:
    errors = sum(finding.severity == "error" for finding in report.findings)
    warnings = sum(finding.severity == "warning" for finding in report.findings)
    return errors, warnings


def format_text(report: AuditReport) -> str:
    chunks: list[str] = []
    for finding in report.findings:
        location = finding.path
        if finding.line is not None:
            location += f":{finding.line}"
        chunks.append(
            f"{finding.severity.upper()} {finding.code} {location}\n"
            f"  {finding.message}"
        )
        if finding.hint:
            chunks[-1] += f"\n  hint: {finding.hint}"
    errors, warnings = _summary(report)
    status = "passed" if errors == 0 else "failed"
    chunks.append(
        f"docs audit {status}: {errors} errors, {warnings} warnings\n"
        f"checked: {report.stats.bilingual_pairs} bilingual pairs, "
        f"{report.stats.machine_documents} machine documents across "
        f"{report.stats.machine_locales} machine locales, "
        f"{report.stats.markdown_links} local/reference links, "
        f"{report.stats.source_references} source references, "
        f"{report.stats.test_modules} test modules, "
        f"{report.stats.fixture_directories} fixture directories"
    )
    return "\n\n".join(chunks)


def format_json(report: AuditReport) -> str:
    errors, warnings = _summary(report)
    payload = {
        "ok": report.ok,
        "summary": {"errors": errors, "warnings": warnings},
        "stats": asdict(report.stats),
        "findings": [asdict(finding) for finding in report.findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _github_escape(value: str) -> str:
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def format_github(report: AuditReport) -> str:
    lines: list[str] = []
    for finding in report.findings:
        command = "error" if finding.severity == "error" else "warning"
        attributes = [
            f"file={_github_escape(finding.path)}",
            f"title={_github_escape(finding.code)}",
        ]
        if finding.line is not None:
            attributes.append(f"line={finding.line}")
        message = finding.message
        if finding.hint:
            message += f" Hint: {finding.hint}"
        lines.append(
            f"::{command} {','.join(attributes)}::{_github_escape(message)}"
        )
    lines.append(format_text(report).split("\n\n")[-1])
    return "\n".join(lines)


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only offline documentation audit / 只读离线文档审计"
    )
    parser.add_argument("--root", type=Path, default=_default_root())
    parser.add_argument(
        "--format",
        choices=("text", "json", "github"),
        default="text",
        dest="output_format",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning"),
        default="error",
    )
    parser.add_argument(
        "--machine-mode",
        choices=("ignore", "allow-stale", "required"),
        default="allow-stale",
        help=(
            "ignore generated locales, validate existing generated files while "
            "allowing stale/missing outputs, or require every output to be current"
        ),
    )
    parser.add_argument(
        "--changed-base",
        help=(
            "git base revision used to require paired English/Chinese changes"
        ),
    )
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"repository root is not a directory: {args.root}")

    try:
        report = audit_repository(
            args.root,
            machine_mode=args.machine_mode,
            changed_base=args.changed_base,
        )
    except AuditInvocationError as exc:
        print(f"docs audit invocation error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - last-resort CLI boundary
        print(f"docs audit internal error: {exc}", file=sys.stderr)
        return 2

    if args.output_format == "json":
        print(format_json(report))
    elif args.output_format == "github":
        print(format_github(report))
    else:
        print(format_text(report))

    errors, warnings = _summary(report)
    if errors or (args.fail_on == "warning" and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
