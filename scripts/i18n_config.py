"""Shared configuration helpers for documentation localization."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path


class I18nConfigError(ValueError):
    """Raised when the committed i18n configuration is inconsistent."""


@dataclass(frozen=True)
class TranslationSettings:
    provider: str
    base_url: str
    model: str
    api_key_env: str
    prompt_path: Path
    catalog_prompt_path: Path
    prompt_version: str
    temperature: float
    thinking: str
    max_tokens: int
    max_concurrency: int
    max_retries: int
    request_timeout_seconds: int


@dataclass(frozen=True)
class Locale:
    code: str
    name: str
    source: str | None
    theme_language: str
    machine: bool
    frozen_since: str | None


@dataclass(frozen=True)
class I18nConfig:
    root: Path
    docs_dir: Path
    manifest_path: Path
    generated_catalog_dir: Path
    canonical_catalogs: dict[str, Path]
    default_locale: str
    canonical_locales: tuple[str, ...]
    excluded_docs: tuple[str, ...]
    locales: dict[str, Locale]
    translation: TranslationSettings

    @property
    def machine_locales(self) -> tuple[Locale, ...]:
        return tuple(
            locale
            for locale in self.locales.values()
            if locale.machine
        )

    @property
    def active_machine_locales(self) -> tuple[Locale, ...]:
        return tuple(
            locale
            for locale in self.machine_locales
            if locale.frozen_since is None
        )

    @property
    def locale_suffixes(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                (code for code in self.locales if code != self.default_locale),
                key=len,
                reverse=True,
            )
        )


def _required(
    mapping: dict[str, object],
    key: str,
    expected_type: type,
    context: str,
) -> object:
    value = mapping.get(key)
    if not isinstance(value, expected_type):
        raise I18nConfigError(
            f"{context}.{key} must be {expected_type.__name__}"
        )
    return value


def load_i18n_config(root: Path) -> I18nConfig:
    """Load and validate ``i18n/config.toml`` from a repository root."""
    root = root.resolve()
    config_path = root / "i18n" / "config.toml"
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise I18nConfigError(f"missing i18n configuration: {config_path}") from exc
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise I18nConfigError(f"cannot read {config_path}: {exc}") from exc

    if raw.get("schema_version") != 1:
        raise I18nConfigError("i18n.config schema_version must be 1")

    default_locale = str(_required(raw, "default_locale", str, "config"))
    canonical_raw = _required(raw, "canonical_locales", list, "config")
    if not canonical_raw or not all(isinstance(item, str) for item in canonical_raw):
        raise I18nConfigError("config.canonical_locales must contain locale strings")
    canonical_locales = tuple(canonical_raw)

    excluded_raw = raw.get("excluded_docs", [])
    if not isinstance(excluded_raw, list) or not all(
        isinstance(item, str) for item in excluded_raw
    ):
        raise I18nConfigError("config.excluded_docs must contain relative paths")

    translation_raw = _required(raw, "translation", dict, "config")
    translation = TranslationSettings(
        provider=str(_required(translation_raw, "provider", str, "translation")),
        base_url=str(_required(translation_raw, "base_url", str, "translation")),
        model=str(_required(translation_raw, "model", str, "translation")),
        api_key_env=str(
            _required(translation_raw, "api_key_env", str, "translation")
        ),
        prompt_path=root
        / str(_required(translation_raw, "prompt_path", str, "translation")),
        catalog_prompt_path=root
        / str(
            _required(
                translation_raw,
                "catalog_prompt_path",
                str,
                "translation",
            )
        ),
        prompt_version=str(
            _required(translation_raw, "prompt_version", str, "translation")
        ),
        temperature=float(translation_raw.get("temperature", 0.1)),
        thinking=str(translation_raw.get("thinking", "disabled")),
        max_tokens=int(translation_raw.get("max_tokens", 131_072)),
        max_concurrency=int(translation_raw.get("max_concurrency", 8)),
        max_retries=int(translation_raw.get("max_retries", 3)),
        request_timeout_seconds=int(
            translation_raw.get("request_timeout_seconds", 600)
        ),
    )
    if translation.provider != "deepseek":
        raise I18nConfigError(
            f"unsupported translation provider: {translation.provider}"
        )
    if translation.thinking not in {"enabled", "disabled"}:
        raise I18nConfigError("translation.thinking must be enabled or disabled")
    if min(
        translation.max_tokens,
        translation.max_concurrency,
        translation.max_retries,
        translation.request_timeout_seconds,
    ) < 1:
        raise I18nConfigError("translation numeric limits must be positive")
    for prompt_path in (
        translation.prompt_path,
        translation.catalog_prompt_path,
    ):
        if not prompt_path.is_file():
            raise I18nConfigError(f"missing translation prompt: {prompt_path}")

    locale_raw = _required(raw, "locales", dict, "config")
    locales: dict[str, Locale] = {}
    for code, item in locale_raw.items():
        if not isinstance(code, str) or not isinstance(item, dict):
            raise I18nConfigError("each config.locales entry must be a table")
        machine = bool(item.get("machine", True))
        source_value = item.get("source")
        source = str(source_value) if source_value is not None else None
        locales[code] = Locale(
            code=code,
            name=str(_required(item, "name", str, f"locales.{code}")),
            source=source,
            theme_language=str(
                item.get("theme_language", code)
            ),
            machine=machine,
            frozen_since=(
                str(item["frozen_since"])
                if item.get("frozen_since") is not None
                else None
            ),
        )

    if default_locale not in locales:
        raise I18nConfigError(
            f"default locale {default_locale!r} is not registered"
        )
    if set(canonical_locales) != {
        code for code, locale in locales.items() if not locale.machine
    }:
        raise I18nConfigError(
            "canonical_locales must exactly match non-machine locale entries"
        )
    for canonical in canonical_locales:
        if locales[canonical].source is not None:
            raise I18nConfigError(
                f"canonical locale {canonical} must not declare a source"
            )
    for locale in locales.values():
        if locale.machine and locale.source not in canonical_locales:
            raise I18nConfigError(
                f"machine locale {locale.code} has invalid source {locale.source!r}"
            )

    catalog_raw = _required(raw, "canonical_catalogs", dict, "config")
    canonical_catalogs = {
        code: root / str(relative)
        for code, relative in catalog_raw.items()
        if isinstance(code, str) and isinstance(relative, str)
    }
    if set(canonical_catalogs) != set(canonical_locales):
        raise I18nConfigError(
            "canonical_catalogs must define every canonical locale exactly once"
        )
    for code, path in canonical_catalogs.items():
        if not path.is_file():
            raise I18nConfigError(
                f"missing canonical catalog for {code}: {path}"
            )

    return I18nConfig(
        root=root,
        docs_dir=root / str(raw.get("docs_dir", "docs")),
        manifest_path=root
        / str(raw.get("manifest_path", "i18n/manifest.json")),
        generated_catalog_dir=root
        / str(raw.get("generated_catalog_dir", "i18n/generated")),
        canonical_catalogs=canonical_catalogs,
        default_locale=default_locale,
        canonical_locales=canonical_locales,
        excluded_docs=tuple(excluded_raw),
        locales=locales,
        translation=translation,
    )


def split_locale_suffix(path: Path, config: I18nConfig) -> tuple[Path, str]:
    """Return the default-locale path and locale represented by a Markdown path."""
    name = path.name
    for locale in config.locale_suffixes:
        suffix = f".{locale}.md"
        if name.endswith(suffix):
            base = path.with_name(name.removesuffix(suffix) + ".md")
            return base, locale
    return path, config.default_locale


def localized_path(default_path: Path, locale: str, config: I18nConfig) -> Path:
    """Return a localized suffix-mode Markdown path."""
    if locale == config.default_locale:
        return default_path
    return default_path.with_name(f"{default_path.stem}.{locale}.md")


def canonical_default_documents(config: I18nConfig) -> tuple[Path, ...]:
    """List default-locale MkDocs pages, excluding derived and ignored documents."""
    excluded = set(config.excluded_docs)
    documents: list[Path] = []
    for path in sorted(config.docs_dir.rglob("*.md")):
        relative_docs = path.relative_to(config.docs_dir).as_posix()
        base, locale = split_locale_suffix(path, config)
        if locale != config.default_locale or base != path:
            continue
        if relative_docs in excluded:
            continue
        documents.append(path)
    return tuple(documents)


def canonical_source_path(
    default_path: Path,
    source_locale: str,
    config: I18nConfig,
) -> Path:
    if source_locale not in config.canonical_locales:
        raise I18nConfigError(f"not a canonical locale: {source_locale}")
    return localized_path(default_path, source_locale, config)


def generated_document_path(
    default_path: Path,
    target_locale: str,
    config: I18nConfig,
) -> Path:
    locale = config.locales.get(target_locale)
    if locale is None or not locale.machine:
        raise I18nConfigError(f"not a machine locale: {target_locale}")
    return localized_path(default_path, target_locale, config)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def translation_fingerprint(config: I18nConfig, *, catalog: bool = False) -> str:
    """Hash all inputs whose change should invalidate generated translations."""
    settings = config.translation
    prompt = (
        settings.catalog_prompt_path
        if catalog
        else settings.prompt_path
    ).read_bytes()
    glossary_path = config.root / "i18n" / "glossary.json"
    glossary = glossary_path.read_bytes() if glossary_path.exists() else b""
    material = b"\0".join(
        (
            settings.provider.encode(),
            settings.base_url.encode(),
            settings.model.encode(),
            settings.prompt_version.encode(),
            prompt,
            glossary,
        )
    )
    return sha256_bytes(material)
