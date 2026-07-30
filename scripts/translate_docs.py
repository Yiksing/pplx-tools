#!/usr/bin/env python3
"""Generate and verify all configured machine-translated MkDocs pages."""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from markdown import Markdown
from markdown.extensions.toc import slugify_unicode

from scripts.i18n_config import (
    I18nConfig,
    Locale,
    canonical_default_documents,
    canonical_source_path,
    generated_document_path,
    load_i18n_config,
    sha256_bytes,
    sha256_file,
    translation_fingerprint,
)


_FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")
_HEADING_RE = re.compile(r"^[ ]{0,3}(#{1,6})[ \t]+")
_INLINE_CODE_RE = re.compile(r"(?<!`)`+[^`\n]+`+")
_LINK_TARGET_RE = re.compile(r"(?<=\]\()[^)\n]+(?=\))")
_REFERENCE_TARGET_RE = re.compile(
    r"(?m)(?<=\]:)[ \t]*(?:<[^>\n]+>|\S+)"
)
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>\n]*>")
_BARE_URL_RE = re.compile(r"https?://[^\s<>()]+")
_LOCK_RE = re.compile(r"⟦PPLX_LOCK_[0-9]{6}⟧")
_SOURCE_ANCHOR_RE = re.compile(
    r'(?m)^<a id="[^"]*" data-pplx-source-anchor="true"></a>\r?\n'
)
_TRANSLATION_META_KEYS = (
    "translation_kind",
    "translation_source_locale",
    "translation_source_path",
    "translation_source_sha256",
    "translation_model",
    "translation_prompt_version",
)
_CHECKPOINT_BRANCH_RE = re.compile(
    r"\Aautomation/i18n-checkpoints/(?P<base>[0-9a-f]{40})\Z"
)
_COMMIT_SHA_RE = re.compile(r"\A[0-9a-fA-F]{40}\Z")


class TranslationFailure(RuntimeError):
    """Raised when an API result cannot safely become a generated document."""


class CompletionClient(Protocol):
    def complete_json(
        self,
        *,
        system_prompt: str,
        request: Mapping[str, object],
    ) -> dict[str, Any]:
        """Return a parsed JSON completion."""


@dataclass(frozen=True)
class ProtectedMarkdown:
    text: str
    replacements: dict[str, str]
    link_tokens: frozenset[str]


@dataclass(frozen=True)
class DocumentTask:
    key: str
    default_path: Path
    source_path: Path
    output_path: Path
    target: Locale
    source_sha256: str
    fingerprint: str


@dataclass(frozen=True)
class CatalogTask:
    locale: Locale
    source_path: Path
    output_path: Path
    source_sha256: str
    fingerprint: str


@dataclass(frozen=True)
class GeneratedDocument:
    task: DocumentTask
    content: str
    warnings: list[dict[str, object]]


@dataclass(frozen=True)
class GeneratedCatalog:
    task: CatalogTask
    catalog: dict[str, object]
    warnings: list[dict[str, object]]


class DeepSeekClient:
    """Small standard-library client for DeepSeek's OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        thinking: str,
        max_tokens: int,
        max_retries: int,
        timeout_seconds: int,
    ) -> None:
        if not api_key:
            raise TranslationFailure("DeepSeek API key is empty")
        self.api_key = api_key
        self.url = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model
        self.temperature = temperature
        self.thinking = thinking
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self._usage_lock = threading.Lock()
        self.usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def _request(self, payload: dict[str, object]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "pplx-tools-doc-localizer/1",
            },
            method="POST",
        )
        with urllib.request.urlopen(  # noqa: S310 - configured HTTPS endpoint
            request,
            timeout=self.timeout_seconds,
        ) as response:
            raw = response.read()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TranslationFailure(
                "DeepSeek returned a non-JSON API response"
            ) from exc
        if not isinstance(result, dict):
            raise TranslationFailure("DeepSeek API response is not an object")
        return result

    def complete_json(
        self,
        *,
        system_prompt: str,
        request: Mapping[str, object],
    ) -> dict[str, Any]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(request, ensure_ascii=False),
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "thinking": {"type": self.thinking},
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._request(payload)
                choices = result.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise TranslationFailure("DeepSeek response has no choices")
                choice = choices[0]
                if not isinstance(choice, dict):
                    raise TranslationFailure("DeepSeek choice is not an object")
                finish_reason = choice.get("finish_reason")
                if finish_reason != "stop":
                    raise TranslationFailure(
                        f"DeepSeek completion did not stop normally: {finish_reason!r}"
                    )
                message = choice.get("message")
                if not isinstance(message, dict):
                    raise TranslationFailure("DeepSeek response has no message")
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise TranslationFailure(
                        "DeepSeek returned empty completion content"
                    )
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise TranslationFailure(
                        "DeepSeek completion is not valid JSON"
                    ) from exc
                if not isinstance(parsed, dict):
                    raise TranslationFailure(
                        "DeepSeek completion JSON is not an object"
                    )
                usage = result.get("usage")
                if isinstance(usage, dict):
                    with self._usage_lock:
                        for key in self.usage:
                            value = usage.get(key)
                            if isinstance(value, int):
                                self.usage[key] += value
                return parsed
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise TranslationFailure(
                        f"DeepSeek HTTP error {exc.code}; request is not retryable"
                    ) from exc
                last_error = exc
            except (
                urllib.error.URLError,
                TimeoutError,
                socket.timeout,
                TranslationFailure,
            ) as exc:
                last_error = exc

            if attempt < self.max_retries:
                delay = min(30.0, (2 ** (attempt - 1)) + random.random())
                time.sleep(delay)

        raise TranslationFailure(
            f"DeepSeek request failed after {self.max_retries} attempts: "
            f"{last_error}"
        ) from last_error


def _protect_fenced_blocks(
    text: str,
    protect: Callable[[str], str],
) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        match = _FENCE_RE.match(lines[index].rstrip("\r\n"))
        if match is None:
            output.append(lines[index])
            index += 1
            continue
        marker = match.group(1)
        block = [lines[index]]
        index += 1
        while index < len(lines):
            block.append(lines[index])
            closing = _FENCE_RE.match(lines[index].rstrip("\r\n"))
            index += 1
            if (
                closing is not None
                and closing.group(1)[0] == marker[0]
                and len(closing.group(1)) >= len(marker)
                and not closing.group(2).strip()
            ):
                break
        value = "".join(block)
        if value.endswith("\r\n"):
            output.append(protect(value[:-2]) + "\r\n")
        elif value.endswith("\n"):
            output.append(protect(value[:-1]) + "\n")
        else:
            output.append(protect(value))
    return "".join(output)


def protect_markdown(
    text: str,
    *,
    literal_terms: Sequence[str] = (),
) -> ProtectedMarkdown:
    """Replace translation-sensitive Markdown fragments with stable tokens."""
    replacements: dict[str, str] = {}
    link_tokens: set[str] = set()

    def protect(value: str, *, link: bool = False) -> str:
        token = f"⟦PPLX_LOCK_{len(replacements):06d}⟧"
        replacements[token] = value
        if link:
            link_tokens.add(token)
        return token

    protected = text
    if protected.startswith("---\n") or protected.startswith("---\r\n"):
        lines = protected.splitlines(keepends=True)
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                front_matter = "".join(lines[: index + 1])
                if front_matter.endswith("\r\n"):
                    locked = protect(front_matter[:-2]) + "\r\n"
                elif front_matter.endswith("\n"):
                    locked = protect(front_matter[:-1]) + "\n"
                else:
                    locked = protect(front_matter)
                protected = locked + "".join(lines[index + 1 :])
                break

    protected = _protect_fenced_blocks(protected, protect)
    protected = _INLINE_CODE_RE.sub(
        lambda match: protect(match.group(0)),
        protected,
    )
    for pattern in (_LINK_TARGET_RE, _REFERENCE_TARGET_RE):
        protected = pattern.sub(
            lambda match: protect(match.group(0), link=True),
            protected,
        )
    for term in sorted(set(literal_terms), key=len, reverse=True):
        if term:
            protected = re.sub(
                re.escape(term),
                lambda match: protect(match.group(0)),
                protected,
            )
    for pattern in (_HTML_TAG_RE, _BARE_URL_RE):
        protected = pattern.sub(
            lambda match: protect(match.group(0)),
            protected,
        )
    return ProtectedMarkdown(
        protected,
        replacements,
        frozenset(link_tokens),
    )


def normalize_source_locale_links(
    protected: ProtectedMarkdown,
    *,
    source_locale: str,
    default_locale: str,
) -> ProtectedMarkdown:
    """Make source-locale relative links resolvable in a derived-locale build."""
    if source_locale == default_locale:
        return protected
    localized_suffix = f".{source_locale}.md"
    replacements = dict(protected.replacements)
    for token in protected.link_tokens:
        raw = replacements[token]
        stripped = raw.strip()
        target = stripped
        if target.startswith("<") and ">" in target:
            target = target[1 : target.index(">")]
        else:
            target = target.split(maxsplit=1)[0] if target else ""
        split = urlsplit(target)
        if (
            not target
            or split.scheme
            or split.netloc
            or target.startswith(("#", "/"))
        ):
            continue
        replacements[token] = raw.replace(localized_suffix, ".md")
    return ProtectedMarkdown(
        protected.text,
        replacements,
        protected.link_tokens,
    )


def restore_markdown(protected: ProtectedMarkdown, translated: str) -> str:
    """Restore all protected fragments, rejecting loss, duplication, or invention."""
    expected = set(protected.replacements)
    found = _LOCK_RE.findall(translated)
    found_set = set(found)
    missing = sorted(expected - found_set)
    invented = sorted(found_set - expected)
    duplicated = sorted(token for token in expected if found.count(token) != 1)
    if missing or invented or duplicated:
        raise TranslationFailure(
            "protected-token contract failed: "
            f"missing={missing}, invented={invented}, duplicated={duplicated}"
        )
    restored = translated
    for token, value in protected.replacements.items():
        restored = restored.replace(token, value)
    if _LOCK_RE.search(restored):
        raise TranslationFailure("protected tokens remain after restoration")
    return restored


def markdown_signature(text: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Return heading levels and fenced-code languages for structural validation."""
    headings: list[int] = []
    fences: list[str] = []
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
            language = fence.group(2).strip().split(maxsplit=1)
            fences.append(language[0].lower() if language else "")
            fence_char = marker[0]
            fence_length = len(marker)
            continue
        heading = _HEADING_RE.match(line)
        if heading is not None:
            headings.append(len(heading.group(1)))
    return tuple(headings), tuple(fences)


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
                collect(
                    [
                        child
                        for child in children
                        if isinstance(child, dict)
                    ]
                )

    tokens = getattr(parser, "toc_tokens", [])
    if isinstance(tokens, list):
        collect([token for token in tokens if isinstance(token, dict)])
    return tuple(flattened)


def add_source_heading_anchors(source: str, translated: str) -> str:
    """Preserve canonical heading fragments as aliases in translated Markdown."""
    clean = _SOURCE_ANCHOR_RE.sub("", translated)
    source_headings = _heading_ids(source)
    translated_headings = _heading_ids(clean)
    if [level for level, _ in source_headings] != [
        level for level, _ in translated_headings
    ]:
        raise TranslationFailure(
            "cannot add source anchors to structurally different Markdown"
        )

    aliases = [
        source_id if source_id != translated_id else None
        for (_, source_id), (_, translated_id) in zip(
            source_headings,
            translated_headings,
            strict=True,
        )
    ]
    lines = clean.splitlines(keepends=True)
    output: list[str] = []
    heading_index = 0
    fence_char: str | None = None
    fence_length = 0
    for line in lines:
        fence = _FENCE_RE.match(line.rstrip("\r\n"))
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
        if heading is not None:
            alias = aliases[heading_index]
            heading_index += 1
            if alias is not None:
                output.append(
                    f'<a id="{html.escape(alias, quote=True)}" '
                    'data-pplx-source-anchor="true"></a>\n'
                )
        output.append(line)
    return "".join(output)


def add_translation_metadata(
    markdown: str,
    task: DocumentTask,
    *,
    root: Path,
    model: str,
    prompt_version: str,
) -> str:
    """Add deterministic machine-provenance front matter."""
    values = {
        "translation_kind": "machine",
        "translation_source_locale": task.target.source or "",
        "translation_source_path": task.source_path.relative_to(root).as_posix(),
        "translation_source_sha256": task.source_sha256,
        "translation_model": model,
        "translation_prompt_version": prompt_version,
    }
    metadata = [
        f"{key}: {json.dumps(value, ensure_ascii=False)}"
        for key, value in values.items()
    ]
    if markdown.startswith("---\n") or markdown.startswith("---\r\n"):
        lines = markdown.splitlines(keepends=True)
        newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
        return lines[0] + "".join(line + newline for line in metadata) + "".join(
            lines[1:]
        )
    body = markdown.lstrip("\r\n")
    return "---\n" + "\n".join(metadata) + "\n---\n\n" + body


def parse_translation_metadata(text: str) -> dict[str, str]:
    """Parse only the deterministic scalar front matter emitted above."""
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return {}
    lines = text.splitlines()
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            break
        key, separator, raw_value = line.partition(":")
        if not separator or key not in _TRANSLATION_META_KEYS:
            continue
        try:
            value = json.loads(raw_value.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(value, str):
            result[key] = value
    return result


def _recursive_shape(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _recursive_shape(child)
            for key, child in sorted(value.items())
        }
    if isinstance(value, list):
        return [_recursive_shape(child) for child in value]
    return type(value).__name__


def _validate_warnings(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, dict) for item in value
    ):
        raise TranslationFailure("completion warnings must be a list of objects")
    return value


def _preserved_glossary_terms(glossary: dict[str, object]) -> tuple[str, ...]:
    return tuple(
        term
        for term, settings in glossary.items()
        if (
            isinstance(term, str)
            and isinstance(settings, dict)
            and settings.get("preserve") is True
        )
    )


def _validate_catalog_strings(
    source: object,
    translated: object,
    *,
    preserved_terms: Sequence[str],
    path: str = "$",
) -> None:
    if isinstance(source, dict) and isinstance(translated, dict):
        for key in source:
            _validate_catalog_strings(
                source[key],
                translated[key],
                preserved_terms=preserved_terms,
                path=f"{path}.{key}",
            )
        return
    if isinstance(source, list) and isinstance(translated, list):
        for index, (source_item, translated_item) in enumerate(
            zip(source, translated, strict=True)
        ):
            _validate_catalog_strings(
                source_item,
                translated_item,
                preserved_terms=preserved_terms,
                path=f"{path}[{index}]",
            )
        return
    if isinstance(source, str) and isinstance(translated, str):
        if not translated.strip():
            raise TranslationFailure(
                f"translated catalog value is empty at {path}"
            )
        for term in preserved_terms:
            if term in source and term not in translated:
                raise TranslationFailure(
                    f"translated catalog lost preserved term {term!r} at {path}"
                )


def translate_document(
    task: DocumentTask,
    *,
    client: CompletionClient,
    config: I18nConfig,
    model: str,
    glossary: dict[str, object],
) -> GeneratedDocument:
    source = task.source_path.read_text(encoding="utf-8")
    protected = protect_markdown(
        source,
        literal_terms=_preserved_glossary_terms(glossary),
    )
    protected = normalize_source_locale_links(
        protected,
        source_locale=task.target.source or config.default_locale,
        default_locale=config.default_locale,
    )
    translation_id = f"{task.key}-{task.source_sha256[:12]}"
    response = client.complete_json(
        system_prompt=config.translation.prompt_path.read_text(encoding="utf-8"),
        request={
            "translation_id": translation_id,
            "source_path": task.source_path.relative_to(config.root).as_posix(),
            "source_sha256": task.source_sha256,
            "source_locale": task.target.source,
            "target_locale": task.target.code,
            "target_language_name": task.target.name,
            "target_style": "Professional technical documentation",
            "glossary": glossary,
            "protected_tokens": list(protected.replacements),
            "markdown": protected.text,
        },
    )
    if response.get("translation_id") != translation_id:
        raise TranslationFailure(
            f"{task.key}: completion changed translation_id"
        )
    translated = response.get("translated_markdown")
    if not isinstance(translated, str) or not translated.strip():
        raise TranslationFailure(
            f"{task.key}: completion has no translated_markdown"
        )
    restored = restore_markdown(protected, translated)
    if markdown_signature(source) != markdown_signature(restored):
        raise TranslationFailure(
            f"{task.key}: translated Markdown structure differs from source"
        )
    restored = add_source_heading_anchors(source, restored)
    content = add_translation_metadata(
        restored,
        task,
        root=config.root,
        model=model,
        prompt_version=config.translation.prompt_version,
    )
    if not content.endswith("\n"):
        content += "\n"
    return GeneratedDocument(
        task=task,
        content=content,
        warnings=_validate_warnings(response.get("warnings")),
    )


def translate_catalog(
    task: CatalogTask,
    *,
    client: CompletionClient,
    config: I18nConfig,
    glossary: dict[str, object],
) -> GeneratedCatalog:
    source = json.loads(task.source_path.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise TranslationFailure(f"{task.source_path} is not a JSON object")
    translation_id = f"catalog-{task.locale.code}-{task.source_sha256[:12]}"
    response = client.complete_json(
        system_prompt=config.translation.catalog_prompt_path.read_text(
            encoding="utf-8"
        ),
        request={
            "translation_id": translation_id,
            "source_locale": task.locale.source,
            "target_locale": task.locale.code,
            "target_language_name": task.locale.name,
            "glossary": glossary,
            "catalog": source,
        },
    )
    if response.get("translation_id") != translation_id:
        raise TranslationFailure(
            f"catalog {task.locale.code}: completion changed translation_id"
        )
    translated = response.get("translated_catalog")
    if not isinstance(translated, dict):
        raise TranslationFailure(
            f"catalog {task.locale.code}: completion has no translated_catalog"
        )
    if _recursive_shape(source) != _recursive_shape(translated):
        raise TranslationFailure(
            f"catalog {task.locale.code}: translated key/type shape differs"
        )
    _validate_catalog_strings(
        source,
        translated,
        preserved_terms=_preserved_glossary_terms(glossary),
    )
    return GeneratedCatalog(
        task=task,
        catalog=translated,
        warnings=_validate_warnings(response.get("warnings")),
    )


def _translate_document_resilient(
    task: DocumentTask,
    *,
    client: CompletionClient,
    config: I18nConfig,
    model: str,
    glossary: dict[str, object],
) -> GeneratedDocument:
    attempts = (
        config.translation.max_retries
        if isinstance(client, DeepSeekClient)
        else 1
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return translate_document(
                task,
                client=client,
                config=config,
                model=model,
                glossary=glossary,
            )
        except TranslationFailure as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(10.0, attempt + random.random()))
    raise TranslationFailure(
        f"{task.key}: validation failed after {attempts} attempts: {last_error}"
    ) from last_error


def _translate_catalog_resilient(
    task: CatalogTask,
    *,
    client: CompletionClient,
    config: I18nConfig,
    glossary: dict[str, object],
) -> GeneratedCatalog:
    attempts = (
        config.translation.max_retries
        if isinstance(client, DeepSeekClient)
        else 1
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return translate_catalog(
                task,
                client=client,
                config=config,
                glossary=glossary,
            )
        except TranslationFailure as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(10.0, attempt + random.random()))
    raise TranslationFailure(
        f"catalog {task.locale.code}: validation failed after {attempts} "
        f"attempts: {last_error}"
    ) from last_error


def load_manifest(config: I18nConfig) -> dict[str, object]:
    if not config.manifest_path.exists():
        return {"schema_version": 1, "documents": {}, "catalogs": {}}
    try:
        value = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TranslationFailure(
            f"cannot read translation manifest: {exc}"
        ) from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise TranslationFailure("translation manifest schema_version must be 1")
    if not isinstance(value.get("documents"), dict) or not isinstance(
        value.get("catalogs"), dict
    ):
        raise TranslationFailure("translation manifest sections must be objects")
    return value


def _document_key(
    default_path: Path,
    locale: str,
    config: I18nConfig,
) -> str:
    return f"{default_path.relative_to(config.root).as_posix()}::{locale}"


def _entry_current(
    entry: object,
    *,
    source_sha256: str,
    output_path: Path,
    fingerprint: str,
    model: str,
) -> bool:
    if not isinstance(entry, dict) or not output_path.is_file():
        return False
    return (
        entry.get("source_sha256") == source_sha256
        and entry.get("translation_fingerprint") == fingerprint
        and entry.get("model") == model
        and entry.get("output_sha256") == sha256_file(output_path)
    )


def build_plan(
    config: I18nConfig,
    manifest: dict[str, object],
    *,
    model: str,
    force: bool,
) -> tuple[list[DocumentTask], list[CatalogTask], set[str], set[str]]:
    documents = manifest["documents"]
    catalogs = manifest["catalogs"]
    assert isinstance(documents, dict)
    assert isinstance(catalogs, dict)
    document_fingerprint = sha256_bytes(
        (
            translation_fingerprint(config)
            + "\0"
            + model
        ).encode()
    )
    catalog_fingerprint = sha256_bytes(
        (
            translation_fingerprint(config, catalog=True)
            + "\0"
            + model
        ).encode()
    )
    document_tasks: list[DocumentTask] = []
    catalog_tasks: list[CatalogTask] = []
    expected_document_keys: set[str] = set()
    expected_catalog_keys: set[str] = set()

    for default_path in canonical_default_documents(config):
        for locale in config.machine_locales:
            assert locale.source is not None
            source_path = canonical_source_path(
                default_path,
                locale.source,
                config,
            )
            if not source_path.is_file():
                raise TranslationFailure(
                    f"missing canonical source for {locale.code}: "
                    f"{source_path.relative_to(config.root)}"
                )
            output_path = generated_document_path(
                default_path,
                locale.code,
                config,
            )
            key = _document_key(default_path, locale.code, config)
            expected_document_keys.add(key)
            if locale.frozen_since is not None:
                continue
            source_hash = sha256_file(source_path)
            if force or not _entry_current(
                documents.get(key),
                source_sha256=source_hash,
                output_path=output_path,
                fingerprint=document_fingerprint,
                model=model,
            ):
                document_tasks.append(
                    DocumentTask(
                        key=key,
                        default_path=default_path,
                        source_path=source_path,
                        output_path=output_path,
                        target=locale,
                        source_sha256=source_hash,
                        fingerprint=document_fingerprint,
                    )
                )

    for locale in config.machine_locales:
        assert locale.source is not None
        source_path = config.canonical_catalogs[locale.source]
        output_path = config.generated_catalog_dir / f"{locale.code}.json"
        expected_catalog_keys.add(locale.code)
        if locale.frozen_since is not None:
            continue
        source_hash = sha256_file(source_path)
        if force or not _entry_current(
            catalogs.get(locale.code),
            source_sha256=source_hash,
            output_path=output_path,
            fingerprint=catalog_fingerprint,
            model=model,
        ):
            catalog_tasks.append(
                CatalogTask(
                    locale=locale,
                    source_path=source_path,
                    output_path=output_path,
                    source_sha256=source_hash,
                    fingerprint=catalog_fingerprint,
                )
            )

    return (
        document_tasks,
        catalog_tasks,
        expected_document_keys,
        expected_catalog_keys,
    )


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json_atomic(path: Path, value: object) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _commit_locale_checkpoint(
    *,
    root: Path,
    manifest_path: Path,
    locale: str,
    output_paths: tuple[Path, ...],
    checkpoint_branch: str,
) -> None:
    """Commit and push one completed locale without staging unrelated changes."""
    root = root.resolve()
    _validate_checkpoint_branch(
        root=root,
        checkpoint_branch=checkpoint_branch,
    )
    relative_paths: list[str] = []
    for path in (*output_paths, manifest_path):
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise TranslationFailure(
                f"checkpoint path is outside the repository: {path}"
            ) from exc
        if relative not in relative_paths:
            relative_paths.append(relative)

    subprocess.run(
        ["git", "add", "--", *relative_paths],
        cwd=root,
        check=True,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", *relative_paths],
        cwd=root,
        check=False,
    )
    if staged.returncode == 0:
        return
    if staged.returncode != 1:
        raise TranslationFailure(
            f"cannot inspect staged translation checkpoint for {locale}"
        )

    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            f"chore(i18n): translate {locale} [skip ci]",
            "--",
            *relative_paths,
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "push",
            "origin",
            f"HEAD:refs/heads/{checkpoint_branch}",
        ],
        cwd=root,
        check=True,
    )


def _validate_checkpoint_branch(
    *,
    root: Path,
    checkpoint_branch: str,
    base_sha: str | None = None,
) -> None:
    match = _CHECKPOINT_BRANCH_RE.fullmatch(checkpoint_branch)
    if match is None:
        raise TranslationFailure(
            "checkpoint branch must be "
            "automation/i18n-checkpoints/<40-character-base-sha>"
        )
    if base_sha is not None:
        if _COMMIT_SHA_RE.fullmatch(base_sha) is None:
            raise TranslationFailure(
                "checkpoint base must be a 40-character commit SHA"
            )
        if match.group("base") != base_sha.lower():
            raise TranslationFailure(
                "checkpoint branch does not match the requested base SHA"
            )
    subprocess.run(
        ["git", "check-ref-format", "--branch", checkpoint_branch],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _checkpoint_path_is_generated(
    path: Path,
    config: I18nConfig,
) -> bool:
    try:
        relative_manifest = config.manifest_path.relative_to(config.root)
        relative_catalog_dir = config.generated_catalog_dir.relative_to(
            config.root
        )
        relative_docs_dir = config.docs_dir.relative_to(config.root)
    except ValueError as exc:  # pragma: no cover - validated config boundary
        raise TranslationFailure(
            "translation paths must be inside the repository"
        ) from exc

    if path == relative_manifest:
        return True
    if path.parent == relative_catalog_dir:
        return path.name in {
            f"{locale.code}.json" for locale in config.machine_locales
        }
    try:
        relative_doc = path.relative_to(relative_docs_dir)
    except ValueError:
        return False
    return any(
        relative_doc.name.endswith(f".{locale.code}.md")
        for locale in config.machine_locales
    )


def verify_checkpoint_branch(
    *,
    root: Path,
    base_sha: str,
    checkpoint_branch: str,
) -> int:
    """Verify a resumable checkpoint before checking out its generated files."""
    root = root.resolve()
    config = load_i18n_config(root)
    _validate_checkpoint_branch(
        root=root,
        checkpoint_branch=checkpoint_branch,
        base_sha=base_sha,
    )
    checkpoint_ref = f"refs/remotes/origin/{checkpoint_branch}"
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_sha, checkpoint_ref],
        cwd=root,
        check=False,
    )
    if ancestor.returncode != 0:
        raise TranslationFailure(
            "checkpoint is not a linear descendant of its base SHA"
        )

    changed_result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRD",
            f"{base_sha}..{checkpoint_ref}",
            "--",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    changed_paths = tuple(
        Path(line)
        for line in changed_result.stdout.splitlines()
        if line.strip()
    )
    unexpected = [
        path
        for path in changed_paths
        if not _checkpoint_path_is_generated(path, config)
    ]
    if unexpected:
        raise TranslationFailure(
            "checkpoint changes non-generated paths: "
            + ", ".join(path.as_posix() for path in unexpected)
        )

    for path in changed_paths:
        tree_result = subprocess.run(
            ["git", "ls-tree", checkpoint_ref, "--", path.as_posix()],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        if not tree_result.stdout:
            continue
        mode = tree_result.stdout.split(maxsplit=1)[0]
        if mode != "100644":
            raise TranslationFailure(
                f"checkpoint generated path has unsafe Git mode {mode}: {path}"
            )

    print(f"verified checkpoint branch: {len(changed_paths)} generated paths")
    return 0


def apply_results(
    *,
    config: I18nConfig,
    manifest: dict[str, object],
    documents: list[GeneratedDocument],
    catalogs: list[GeneratedCatalog],
    expected_document_keys: set[str],
    expected_catalog_keys: set[str],
    model: str,
) -> None:
    document_entries = manifest["documents"]
    catalog_entries = manifest["catalogs"]
    assert isinstance(document_entries, dict)
    assert isinstance(catalog_entries, dict)

    obsolete_document_keys = set(document_entries) - expected_document_keys
    obsolete_catalog_keys = set(catalog_entries) - expected_catalog_keys
    for key in sorted(obsolete_document_keys):
        entry = document_entries.get(key)
        relative = entry.get("output_path") if isinstance(entry, dict) else None
        if not isinstance(relative, str):
            continue
        output_path = (config.root / relative).resolve()
        try:
            output_path.relative_to(config.docs_dir.resolve())
        except ValueError:
            raise TranslationFailure(
                f"refusing to prune generated path outside docs: {relative}"
            )
        if output_path.suffix == ".md" and output_path.is_file():
            output_path.unlink()

    for key in sorted(obsolete_catalog_keys):
        entry = catalog_entries.get(key)
        relative = entry.get("output_path") if isinstance(entry, dict) else None
        if not isinstance(relative, str):
            continue
        output_path = (config.root / relative).resolve()
        try:
            output_path.relative_to(config.generated_catalog_dir.resolve())
        except ValueError:
            raise TranslationFailure(
                f"refusing to prune generated catalog outside its directory: "
                f"{relative}"
            )
        if output_path.suffix == ".json" and output_path.is_file():
            output_path.unlink()

    for result in documents:
        _write_text_atomic(result.task.output_path, result.content)
        document_entries[result.task.key] = {
            "source_locale": result.task.target.source,
            "source_path": result.task.source_path.relative_to(
                config.root
            ).as_posix(),
            "source_sha256": result.task.source_sha256,
            "output_path": result.task.output_path.relative_to(
                config.root
            ).as_posix(),
            "output_sha256": sha256_bytes(result.content.encode("utf-8")),
            "model": model,
            "prompt_version": config.translation.prompt_version,
            "translation_fingerprint": result.task.fingerprint,
            "warnings": result.warnings,
        }

    for result in catalogs:
        rendered = (
            json.dumps(
                result.catalog,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        _write_text_atomic(result.task.output_path, rendered)
        catalog_entries[result.task.locale.code] = {
            "source_locale": result.task.locale.source,
            "source_path": result.task.source_path.relative_to(
                config.root
            ).as_posix(),
            "source_sha256": result.task.source_sha256,
            "output_path": result.task.output_path.relative_to(
                config.root
            ).as_posix(),
            "output_sha256": sha256_bytes(rendered.encode("utf-8")),
            "model": model,
            "prompt_version": config.translation.prompt_version,
            "translation_fingerprint": result.task.fingerprint,
            "warnings": result.warnings,
        }

    manifest["documents"] = {
        key: document_entries[key]
        for key in sorted(expected_document_keys)
        if key in document_entries
    }
    manifest["catalogs"] = {
        key: catalog_entries[key]
        for key in sorted(expected_catalog_keys)
        if key in catalog_entries
    }
    manifest["schema_version"] = 1
    manifest["generator"] = {
        "provider": config.translation.provider,
        "model": model,
        "prompt_version": config.translation.prompt_version,
    }
    _write_json_atomic(config.manifest_path, manifest)


def refresh_heading_anchors(
    *,
    config: I18nConfig,
    manifest: dict[str, object],
    checkpoint_locale: (
        Callable[[str, tuple[Path, ...]], None] | None
    ) = None,
) -> int:
    """Refresh stable canonical heading aliases without making API requests."""
    document_entries = manifest["documents"]
    assert isinstance(document_entries, dict)
    updated = 0
    for locale in config.machine_locales:
        assert locale.source is not None
        changed_paths: list[Path] = []
        for default_path in canonical_default_documents(config):
            output_path = generated_document_path(
                default_path,
                locale.code,
                config,
            )
            key = _document_key(default_path, locale.code, config)
            entry = document_entries.get(key)
            if not output_path.is_file() or not isinstance(entry, dict):
                continue
            source_path = canonical_source_path(
                default_path,
                locale.source,
                config,
            )
            if entry.get("source_sha256") != sha256_file(source_path):
                # The output is stale and will be replaced by translation.
                # Refreshing aliases here would create a pointless checkpoint.
                continue
            current = output_path.read_text(encoding="utf-8")
            refreshed = add_source_heading_anchors(
                source_path.read_text(encoding="utf-8"),
                current,
            )
            if refreshed == current:
                continue
            _write_text_atomic(output_path, refreshed)
            entry["output_sha256"] = sha256_bytes(
                refreshed.encode("utf-8")
            )
            changed_paths.append(output_path)

        if not changed_paths:
            continue
        _write_json_atomic(config.manifest_path, manifest)
        if checkpoint_locale is not None:
            checkpoint_locale(locale.code, tuple(changed_paths))
        updated += len(changed_paths)
        print(
            f"refreshed source heading anchors for {locale.code}: "
            f"{len(changed_paths)} documents"
        )
    print(f"updated source heading anchors: {updated} documents")
    return 0


def _resolved_model(config: I18nConfig, command_line_model: str | None) -> str:
    return (
        command_line_model
        or os.environ.get("DEEPSEEK_TRANSLATION_MODEL")
        or config.translation.model
    )


def run(
    *,
    root: Path,
    check: bool,
    plan_only: bool,
    force: bool,
    jobs: int | None,
    model_override: str | None,
    client: CompletionClient | None = None,
    checkpoint_locale: (
        Callable[[str, tuple[Path, ...]], None] | None
    ) = None,
) -> int:
    config = load_i18n_config(root)
    model = _resolved_model(config, model_override)
    manifest = load_manifest(config)
    (
        document_tasks,
        catalog_tasks,
        expected_document_keys,
        expected_catalog_keys,
    ) = build_plan(config, manifest, model=model, force=force)
    plan = {
        "model": model,
        "machine_locales": len(config.machine_locales),
        "frozen_machine_locales": sum(
            1 for locale in config.machine_locales
            if locale.frozen_since is not None
        ),
        "canonical_documents": len(canonical_default_documents(config)),
        "document_translations_total": len(expected_document_keys),
        "document_translations_pending": len(document_tasks),
        "catalog_translations_total": len(expected_catalog_keys),
        "catalog_translations_pending": len(catalog_tasks),
        "obsolete_document_translations": len(
            set(manifest["documents"]) - expected_document_keys
        ),
        "obsolete_catalog_translations": len(
            set(manifest["catalogs"]) - expected_catalog_keys
        ),
    }
    if plan_only:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    if check:
        if (
            document_tasks
            or catalog_tasks
            or plan["obsolete_document_translations"]
            or plan["obsolete_catalog_translations"]
        ):
            print(
                "machine translations are missing or stale: "
                f"{len(document_tasks)} documents, "
                f"{len(catalog_tasks)} catalogs, "
                f"{plan['obsolete_document_translations']} obsolete documents, "
                f"{plan['obsolete_catalog_translations']} obsolete catalogs",
                file=sys.stderr,
            )
            return 1
        print(
            "machine translations current: "
            f"{len(expected_document_keys)} documents, "
            f"{len(expected_catalog_keys)} catalogs, model={model}"
        )
        return 0
    if (
        not document_tasks
        and not catalog_tasks
        and not plan["obsolete_document_translations"]
        and not plan["obsolete_catalog_translations"]
    ):
        print(
            "machine translations already current: "
            f"{len(expected_document_keys)} documents, "
            f"{len(expected_catalog_keys)} catalogs"
        )
        return 0

    if (document_tasks or catalog_tasks) and client is None:
        api_key = os.environ.get(config.translation.api_key_env, "")
        if not api_key:
            raise TranslationFailure(
                f"required environment variable "
                f"{config.translation.api_key_env} is not set"
            )
        client = DeepSeekClient(
            api_key=api_key,
            base_url=config.translation.base_url,
            model=model,
            temperature=config.translation.temperature,
            thinking=config.translation.thinking,
            max_tokens=config.translation.max_tokens,
            max_retries=config.translation.max_retries,
            timeout_seconds=config.translation.request_timeout_seconds,
        )

    glossary: dict[str, object] = {}
    if document_tasks or catalog_tasks:
        loaded_glossary = json.loads(
            (config.root / "i18n" / "glossary.json").read_text(
                encoding="utf-8"
            )
        )
        if not isinstance(loaded_glossary, dict):
            raise TranslationFailure(
                "i18n/glossary.json must contain an object"
            )
        glossary = loaded_glossary

    generated_documents: list[GeneratedDocument] = []
    generated_catalogs: list[GeneratedCatalog] = []
    failures: list[str] = []
    failed_locales: set[str] = set()
    workers = jobs or config.translation.max_concurrency
    if workers < 1:
        raise TranslationFailure("jobs must be positive")

    locale_remaining = {
        locale.code: sum(
            task.target.code == locale.code for task in document_tasks
        )
        + sum(
            task.locale.code == locale.code for task in catalog_tasks
        )
        for locale in config.machine_locales
    }
    locale_documents: dict[str, list[GeneratedDocument]] = {
        code: [] for code in locale_remaining
    }
    locale_catalogs: dict[str, list[GeneratedCatalog]] = {
        code: [] for code in locale_remaining
    }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        if checkpoint_locale is None:
            locale_task_groups = [
                (
                    document_tasks,
                    catalog_tasks,
                )
            ]
        else:
            locale_task_groups = [
                (
                    [
                        task
                        for task in document_tasks
                        if task.target.code == locale.code
                    ],
                    [
                        task
                        for task in catalog_tasks
                        if task.locale.code == locale.code
                    ],
                )
                for locale in config.machine_locales
            ]

        for document_group, catalog_group in locale_task_groups:
            for task in document_group:
                future = executor.submit(
                    _translate_document_resilient,
                    task,
                    client=client,
                    config=config,
                    model=model,
                    glossary=glossary,
                )
                futures[future] = (
                    "document",
                    task.key,
                    task.target.code,
                )
            for task in catalog_group:
                future = executor.submit(
                    _translate_catalog_resilient,
                    task,
                    client=client,
                    config=config,
                    glossary=glossary,
                )
                futures[future] = (
                    "catalog",
                    task.locale.code,
                    task.locale.code,
                )
        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            kind, key, locale_code = futures[future]
            completed += 1
            try:
                result = future.result()
                if isinstance(result, GeneratedDocument):
                    generated_documents.append(result)
                    locale_documents[locale_code].append(result)
                else:
                    generated_catalogs.append(result)
                    locale_catalogs[locale_code].append(result)
                print(f"[{completed}/{total}] translated {kind} {key}")
            except Exception as exc:  # collect all concurrent failures
                failures.append(f"{kind} {key}: {exc}")
                failed_locales.add(locale_code)
                print(
                    f"[{completed}/{total}] failed {kind} {key}: {exc}",
                    file=sys.stderr,
                )
            finally:
                locale_remaining[locale_code] -= 1

            if (
                checkpoint_locale is not None
                and locale_remaining[locale_code] == 0
                and locale_code not in failed_locales
            ):
                documents = locale_documents[locale_code]
                catalogs = locale_catalogs[locale_code]
                apply_results(
                    config=config,
                    manifest=manifest,
                    documents=documents,
                    catalogs=catalogs,
                    expected_document_keys=expected_document_keys,
                    expected_catalog_keys=expected_catalog_keys,
                    model=model,
                )
                output_paths = tuple(
                    result.task.output_path
                    for result in [*documents, *catalogs]
                )
                checkpoint_locale(locale_code, output_paths)
                print(
                    f"checkpointed locale {locale_code}: "
                    f"{len(documents)} documents, {len(catalogs)} catalogs"
                )

    if failures:
        retention = (
            "; completed locale batches were retained"
            if checkpoint_locale is not None
            else "; no outputs were written"
        )
        raise TranslationFailure(
            f"{len(failures)} translation tasks failed{retention}\n"
            + "\n".join(failures)
        )

    if checkpoint_locale is None:
        apply_results(
            config=config,
            manifest=manifest,
            documents=generated_documents,
            catalogs=generated_catalogs,
            expected_document_keys=expected_document_keys,
            expected_catalog_keys=expected_catalog_keys,
            model=model,
        )
    else:
        apply_results(
            config=config,
            manifest=manifest,
            documents=[],
            catalogs=[],
            expected_document_keys=expected_document_keys,
            expected_catalog_keys=expected_catalog_keys,
            model=model,
        )
    usage = getattr(client, "usage", None)
    print(
        "updated machine translations: "
        f"{len(generated_documents)} documents, "
        f"{len(generated_catalogs)} catalogs"
    )
    if isinstance(usage, dict):
        print("token usage: " + json.dumps(usage, sort_keys=True))
    return 0


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate and verify configured machine translations"
    )
    parser.add_argument("--root", type=Path, default=_default_root())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="fail if any configured translation is missing or stale",
    )
    mode.add_argument(
        "--plan",
        action="store_true",
        help="print the incremental translation plan without API calls",
    )
    mode.add_argument(
        "--refresh-heading-anchors",
        action="store_true",
        help="refresh canonical heading aliases without API calls",
    )
    mode.add_argument(
        "--verify-checkpoint",
        action="store_true",
        help="verify a remote checkpoint branch without checking it out",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="regenerate every configured machine translation",
    )
    parser.add_argument("--jobs", type=int)
    parser.add_argument(
        "--model",
        help="override the configured model for this run",
    )
    parser.add_argument(
        "--commit-each-locale",
        action="store_true",
        help="commit and push each completed locale as a resumable checkpoint",
    )
    parser.add_argument(
        "--checkpoint-branch",
        help=(
            "generated-only branch used by --commit-each-locale or "
            "--verify-checkpoint"
        ),
    )
    parser.add_argument(
        "--checkpoint-base",
        help="exact base SHA required by --verify-checkpoint",
    )
    args = parser.parse_args(argv)
    if args.commit_each_locale and (args.check or args.plan):
        parser.error(
            "--commit-each-locale cannot be combined with --check or --plan"
        )
    if args.commit_each_locale and not args.checkpoint_branch:
        parser.error("--commit-each-locale requires --checkpoint-branch")
    if args.verify_checkpoint and (
        not args.checkpoint_branch or not args.checkpoint_base
    ):
        parser.error(
            "--verify-checkpoint requires --checkpoint-branch and "
            "--checkpoint-base"
        )
    if (
        args.checkpoint_branch or args.checkpoint_base
    ) and not (args.commit_each_locale or args.verify_checkpoint):
        parser.error(
            "checkpoint options require --commit-each-locale or "
            "--verify-checkpoint"
        )
    try:
        if args.verify_checkpoint:
            return verify_checkpoint_branch(
                root=args.root,
                base_sha=args.checkpoint_base,
                checkpoint_branch=args.checkpoint_branch,
            )
        checkpoint_locale = None
        if args.commit_each_locale:
            config = load_i18n_config(args.root)

            def checkpoint_locale(
                locale: str,
                output_paths: tuple[Path, ...],
            ) -> None:
                _commit_locale_checkpoint(
                    root=config.root,
                    manifest_path=config.manifest_path,
                    locale=locale,
                    output_paths=output_paths,
                    checkpoint_branch=args.checkpoint_branch,
                )

        if args.refresh_heading_anchors:
            config = load_i18n_config(args.root)
            return refresh_heading_anchors(
                config=config,
                manifest=load_manifest(config),
                checkpoint_locale=checkpoint_locale,
            )
        return run(
            root=args.root,
            check=args.check,
            plan_only=args.plan,
            force=args.force,
            jobs=args.jobs,
            model_override=args.model,
            checkpoint_locale=checkpoint_locale,
        )
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"translation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
