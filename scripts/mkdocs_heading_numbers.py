#!/usr/bin/env python3
"""Add semantic page-local heading numbers without storing them in Markdown."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from markdown import Markdown
from markdown.extensions.toc import slugify_unicode


_ROOT = Path(__file__).resolve().parents[1]
_LEGACY_PATH = _ROOT / "i18n" / "legacy-heading-anchors.json"
_FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")
_HEADING_RE = re.compile(
    r"^(?P<indent>[ ]{0,3})(?P<marks>#{1,6})"
    r"(?P<space>[ \t]+)(?P<title>.+?)(?P<newline>\r?\n)?$"
)
_MANUAL_PREFIX_RE = re.compile(
    r"^(?P<prefix>\d{1,2}(?:\.\d+)*\.?)[ \t]+"
)
_ATTR_LIST_RE = re.compile(r"(?P<space>[ \t]+)\{(?P<attrs>[^{}\n]*)\}[ \t]*$")
_EXPLICIT_ID_RE = re.compile(r"(?:^|[ \t])#(?P<id>[A-Za-z0-9_:.-]+)(?=$|[ \t])")


def _load_legacy_anchors(
    path: Path = _LEGACY_PATH,
) -> dict[str, list[dict[str, object]]]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    documents = value.get("documents") if isinstance(value, dict) else None
    if not isinstance(documents, dict):
        raise ValueError(f"invalid legacy heading map: {path}")
    return {
        str(key): entries
        for key, entries in documents.items()
        if isinstance(entries, list)
    }


def _heading_ids(text: str) -> tuple[tuple[int, str], ...]:
    parser = Markdown(
        extensions=["fenced_code", "attr_list", "toc"],
        extension_configs={"toc": {"slugify": slugify_unicode}},
    )
    parser.convert(text)
    flattened: list[tuple[int, str]] = []

    def collect(tokens: Sequence[Mapping[str, object]]) -> None:
        for token in tokens:
            level = token.get("level")
            identifier = token.get("id")
            if isinstance(level, int) and isinstance(identifier, str):
                flattened.append((level, identifier))
            children = token.get("children")
            if isinstance(children, list):
                collect([child for child in children if isinstance(child, dict)])

    tokens = getattr(parser, "toc_tokens", [])
    if isinstance(tokens, list):
        collect([token for token in tokens if isinstance(token, dict)])
    return tuple(flattened)


def _rewrite_headings(
    markdown: str,
    legacy_entries: Sequence[Mapping[str, object]],
) -> tuple[str, list[tuple[int, str | None]]]:
    """Remove only recorded legacy prefixes and retain heading order metadata."""
    entries = {
        int(entry["heading_index"]): entry
        for entry in legacy_entries
        if isinstance(entry.get("heading_index"), int)
    }
    output: list[str] = []
    heading_meta: list[tuple[int, str | None]] = []
    fence_char: str | None = None
    fence_length = 0
    heading_index = 0

    for line in markdown.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        fence = _FENCE_RE.match(bare)
        if fence_char is not None:
            output.append(line)
            if (
                fence is not None
                and fence.group(1)[0] == fence_char
                and len(fence.group(1)) >= fence_length
                and not fence.group(2).strip()
            ):
                fence_char = None
                fence_length = 0
            continue
        if fence is not None:
            marker = fence.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            output.append(line)
            continue

        heading = _HEADING_RE.match(line)
        if heading is None:
            output.append(line)
            continue

        level = len(heading.group("marks"))
        title = heading.group("title")
        legacy_id: str | None = None
        entry = entries.get(heading_index)
        if entry is not None:
            expected_level = entry.get("level")
            prefix = entry.get("prefix")
            identifier = entry.get("id")
            if expected_level != level:
                raise ValueError(
                    f"legacy heading level mismatch at heading {heading_index}"
                )
            if isinstance(prefix, str):
                match = _MANUAL_PREFIX_RE.match(title)
                if match is not None and match.group("prefix") == prefix:
                    title = title[match.end():]
            if isinstance(identifier, str):
                legacy_id = identifier
        output.append(
            f"{heading.group('indent')}{heading.group('marks')}"
            f"{heading.group('space')}{title}{heading.group('newline') or ''}"
        )
        heading_meta.append((level, legacy_id))
        heading_index += 1

    return "".join(output), heading_meta


def _with_explicit_id(line: str, identifier: str) -> str:
    newline = (
        "\r\n"
        if line.endswith("\r\n")
        else "\n"
        if line.endswith("\n")
        else ""
    )
    bare = line[: -len(newline)] if newline else line
    heading = _HEADING_RE.match(bare)
    if heading is None:
        return line
    title = heading.group("title")
    attrs = _ATTR_LIST_RE.search(title)
    if attrs is None:
        title = f"{title} {{#{identifier}}}"
    elif _EXPLICIT_ID_RE.search(attrs.group("attrs")) is None:
        replacement = f"{attrs.group('space')}{{#{identifier} {attrs.group('attrs')}}}"
        title = title[: attrs.start()] + replacement
    return (
        f"{heading.group('indent')}{heading.group('marks')}"
        f"{heading.group('space')}{title}{newline}"
    )


def _lower_alpha(value: int) -> str:
    """Render a positive integer as a, b, ..., z, aa, ab, ... ."""
    if value < 1:
        raise ValueError("alphabetic outline counters must be positive")
    output: list[str] = []
    while value:
        value, remainder = divmod(value - 1, 26)
        output.append(chr(ord("a") + remainder))
    return "".join(reversed(output))


def number_page_markdown(
    markdown: str,
    *,
    source_path: str,
    legacy_documents: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
) -> str:
    """Number H2-H6 per page while keeping stable, unnumbered fragment IDs."""
    legacy_documents = legacy_documents or {}
    normalized, heading_meta = _rewrite_headings(
        markdown,
        legacy_documents.get(source_path, ()),
    )
    identifiers = _heading_ids(normalized)
    levels = [level for level, _ in heading_meta]
    if levels != [level for level, _ in identifiers]:
        raise ValueError(f"cannot reconcile Markdown headings for {source_path}")

    output: list[str] = []
    counters = [0, 0, 0, 0, 0]
    alphabetic_outline = (
        source_path.replace("\\", "/").lstrip("./").startswith("guide/")
    )
    heading_index = 0
    fence_char: str | None = None
    fence_length = 0
    for line in normalized.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        fence = _FENCE_RE.match(bare)
        if fence_char is not None:
            output.append(line)
            if (
                fence is not None
                and fence.group(1)[0] == fence_char
                and len(fence.group(1)) >= fence_length
                and not fence.group(2).strip()
            ):
                fence_char = None
                fence_length = 0
            continue
        if fence is not None:
            marker = fence.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            output.append(line)
            continue

        heading = _HEADING_RE.match(line)
        if heading is None:
            output.append(line)
            continue

        level, identifier = identifiers[heading_index]
        _, legacy_id = heading_meta[heading_index]
        heading_index += 1
        if legacy_id and legacy_id != identifier:
            output.append(
                f'<a id="{html.escape(legacy_id, quote=True)}" '
                'data-pplx-legacy-heading-anchor="true"></a>\n'
            )
        if level == 1:
            output.append(_with_explicit_id(line, identifier))
            continue

        position = level - 2
        counters[position] += 1
        for index in range(position + 1, len(counters)):
            counters[index] = 0
        values = counters[: position + 1]
        if alphabetic_outline:
            number = _lower_alpha(values[0])
            if len(values) > 1:
                number = (
                    f"{number}.{'.'.join(str(value) for value in values[1:])}"
                )
        else:
            number = ".".join(str(value) for value in values)
        label = f"{number}." if level == 2 else number
        numbered = _with_explicit_id(line, identifier)
        match = _HEADING_RE.match(numbered)
        if match is None:
            raise ValueError(f"cannot number Markdown heading in {source_path}")
        output.append(
            f"{match.group('indent')}{match.group('marks')}{match.group('space')}"
            f"{label} {match.group('title')}{match.group('newline') or ''}"
        )
    return "".join(output)


_LEGACY_DOCUMENTS = _load_legacy_anchors()


def on_page_markdown(markdown: str, page: Any, config: Any, files: Any) -> str:
    """MkDocs hook entry point."""
    del config, files
    return number_page_markdown(
        markdown,
        source_path=str(page.file.src_path),
        legacy_documents=_LEGACY_DOCUMENTS,
    )


def capture_legacy_anchors(docs_dir: Path) -> dict[str, object]:
    """Capture current numbered fragments before source numbers are removed."""
    documents: dict[str, list[dict[str, object]]] = {}
    for path in sorted(docs_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        identifiers = _heading_ids(text)
        entries: list[dict[str, object]] = []
        heading_index = 0
        fence_char: str | None = None
        fence_length = 0
        for line in text.splitlines():
            fence = _FENCE_RE.match(line)
            if fence_char is not None:
                if (
                    fence is not None
                    and fence.group(1)[0] == fence_char
                    and len(fence.group(1)) >= fence_length
                    and not fence.group(2).strip()
                ):
                    fence_char = None
                    fence_length = 0
                continue
            if fence is not None:
                marker = fence.group(1)
                fence_char = marker[0]
                fence_length = len(marker)
                continue
            heading = _HEADING_RE.match(line)
            if heading is None:
                continue
            prefix = _MANUAL_PREFIX_RE.match(heading.group("title"))
            if prefix is not None:
                level, identifier = identifiers[heading_index]
                entries.append(
                    {
                        "heading_index": heading_index,
                        "level": level,
                        "prefix": prefix.group("prefix"),
                        "id": identifier,
                    }
                )
            heading_index += 1
        if entries:
            documents[path.relative_to(docs_dir).as_posix()] = entries
    return {"schema_version": 1, "documents": documents}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capture-legacy",
        action="store_true",
        help="print a legacy-anchor snapshot for the current docs tree",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the snapshot to this path instead of stdout",
    )
    args = parser.parse_args()
    if not args.capture_legacy:
        parser.error("--capture-legacy is required")
    serialized = (
        json.dumps(
            capture_legacy_anchors(_ROOT / "docs"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if args.output is None:
        print(serialized, end="")
    else:
        args.output.write_text(serialized, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
