"""MkDocs hooks for generated locale catalogs and machine-translation notices."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from scripts.i18n_config import load_i18n_config, split_locale_suffix


_ROOT = Path(__file__).resolve().parents[1]
_I18N = load_i18n_config(_ROOT)
_ISSUE_URL = "https://github.com/Yiksing/pplx-tools/issues/new"


def _catalog(locale: str) -> dict[str, Any] | None:
    path = _I18N.generated_catalog_dir / f"{locale}.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _translate_nav(items: list[Any], translations: dict[str, str]) -> None:
    for item in items:
        title = getattr(item, "title", None)
        if isinstance(title, str) and title in translations:
            item.title = translations[title]
        children = getattr(item, "children", None)
        if isinstance(children, list):
            _translate_nav(children, translations)


def on_nav(nav: Any, config: Any, files: Any) -> Any:
    """Apply generated site strings after static-i18n selects a locale."""
    del files
    theme_language = str(config.theme.get("language", "en"))
    locale = _I18N.locales.get(theme_language)
    if locale is None or not locale.machine:
        return nav
    catalog = _catalog(locale.code)
    if catalog is None:
        return nav
    site_name = catalog.get("site_name")
    site_description = catalog.get("site_description")
    if isinstance(site_name, str):
        config.site_name = site_name
    if isinstance(site_description, str):
        config.site_description = site_description
    translations = catalog.get("nav")
    if isinstance(translations, dict) and all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in translations.items()
    ):
        _translate_nav(nav.items, translations)
    return nav


def _source_url(source_path: str, source_locale: str) -> str:
    path = Path(source_path)
    if path.parts and path.parts[0] == "docs":
        path = Path(*path.parts[1:])
    default_path, _ = split_locale_suffix(_I18N.docs_dir / path, _I18N)
    relative = default_path.relative_to(_I18N.docs_dir)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts.pop()
    prefix = [] if source_locale == _I18N.default_locale else [source_locale]
    return "/" + "/".join(prefix + parts) + ("/" if prefix or parts else "")


def on_page_markdown(
    markdown: str,
    page: Any,
    config: Any,
    files: Any,
) -> str:
    """Prepend a localized, non-TOC machine-translation notice."""
    del config, files
    metadata = getattr(page, "meta", {})
    if metadata.get("translation_kind") != "machine":
        return markdown
    source_locale = str(metadata.get("translation_source_locale", "en"))
    source_path = str(metadata.get("translation_source_path", "docs/index.md"))
    _, target_locale = split_locale_suffix(
        _I18N.docs_dir / str(page.file.src_path),
        _I18N,
    )
    target = _I18N.locales.get(target_locale)
    source_catalog = json.loads(
        _I18N.canonical_catalogs[source_locale].read_text(encoding="utf-8")
    )
    catalog = _catalog(target_locale) or source_catalog
    if target is not None and target.frozen_since is not None:
        title = str(
            source_catalog.get(
                "frozen_notice_title",
                "Translation no longer maintained",
            )
        )
        notice = str(
            source_catalog.get(
                "frozen_notice_text",
                "For cost reasons, this translation is no longer maintained "
                "as of {date}. Refer to the source language version.",
            )
        ).format(date=target.frozen_since)
        source_label = str(
            source_catalog.get("source_link_label", "Source")
        )
        report_label = ""
    else:
        title = str(catalog.get("machine_notice_title", "Machine translation"))
        notice = str(
            catalog.get(
                "machine_notice_text",
                "This page was translated automatically by AI and may contain errors.",
            )
        )
        source_label = str(catalog.get("source_link_label", "Source"))
        report_label = str(
            catalog.get("report_link_label", "Report a translation issue")
        )
    source_url = _source_url(source_path, source_locale)
    issue_query = urlencode(
        {
            "title": f"Machine translation: {page.file.src_path}",
            "body": (
                f"Target locale: {target_locale}\n"
                f"Source: {source_path}\n\n"
                "Please describe the translation problem."
            ),
        }
    )
    safe_title = title.replace('"', r"\"")
    issue_url = f"{_ISSUE_URL}?{issue_query}"
    links = (
        f'    <a href="{html.escape(source_url, quote=True)}">'
        f"{html.escape(source_label)}</a>"
    )
    if report_label:
        links += (
            " · "
            f'<a href="{html.escape(issue_url, quote=True)}">'
            f"{html.escape(report_label)}</a>"
        )
    banner = (
        f'!!! warning "{safe_title}"\n'
        f"    {html.escape(notice)}\n\n"
        f"{links}\n\n"
    )
    return banner + markdown
