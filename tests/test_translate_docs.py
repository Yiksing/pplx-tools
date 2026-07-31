"""Isolated tests for the documentation localization pipeline.

文档本地化流程的隔离测试。"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

import material
import pytest
import yaml

import scripts.mkdocs_i18n as mkdocs_i18n
from scripts.mkdocs_heading_numbers import number_page_markdown
from scripts.i18n_config import (
    canonical_default_documents,
    canonical_source_path,
    generated_document_path,
    load_i18n_config,
    sha256_file,
)
from scripts.translate_docs import (
    TranslationFailure,
    DeepSeekClient,
    _commit_locale_checkpoint,
    add_source_heading_anchors,
    normalize_source_locale_links,
    parse_translation_metadata,
    protect_markdown,
    restore_markdown,
    refresh_heading_anchors,
    run,
    verify_checkpoint_branch,
)


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _mini_config() -> str:
    return """
schema_version = 1
default_locale = "en"
canonical_locales = ["en", "zh-CN"]
docs_dir = "docs"
manifest_path = "i18n/manifest.json"
generated_catalog_dir = "i18n/generated"
excluded_docs = ["README.md"]

[canonical_catalogs]
en = "i18n/catalog.en.json"
zh-CN = "i18n/catalog.zh-CN.json"

[translation]
provider = "deepseek"
base_url = "https://api.deepseek.com"
model = "deepseek-v4-pro"
api_key_env = "DEEKSEEK_API_KEY"
prompt_path = "i18n/prompts/markdown.md"
catalog_prompt_path = "i18n/prompts/catalog.md"
prompt_version = "v1"
max_concurrency = 2
max_retries = 2
max_tokens = 4096
request_timeout_seconds = 30

[locales.en]
name = "English"
machine = false

[locales.zh-CN]
name = "简体中文"
theme_language = "zh"
machine = false

[locales.fr]
name = "français"
source = "en"

[locales.ja]
name = "日本語"
source = "zh-CN"
"""


@pytest.fixture()
def i18n_repo(tmp_path: Path) -> Path:
    _write(tmp_path, "i18n/config.toml", _mini_config())
    _write(tmp_path, "i18n/prompts/markdown.md", "Return JSON Markdown.")
    _write(tmp_path, "i18n/prompts/catalog.md", "Return JSON catalog.")
    _write(tmp_path, "i18n/glossary.json", '{"Perplexity":{"preserve":true}}\n')
    _write(
        tmp_path,
        "i18n/catalog.en.json",
        '{"site_name":"Docs","nav":{"Home":"Home"}}\n',
    )
    _write(
        tmp_path,
        "i18n/catalog.zh-CN.json",
        '{"site_name":"文档","nav":{"Home":"首页"}}\n',
    )
    _write(
        tmp_path,
        "docs/index.md",
        "# Docs\n\nSee [configuration](guide/configuration.md).\n\n"
        "```bash\npplx-export --help\n```\n",
    )
    _write(
        tmp_path,
        "docs/index.zh-CN.md",
        "# 文档\n\n请参阅[配置](guide/configuration.zh-CN.md)。\n\n"
        "```bash\npplx-export --help\n```\n",
    )
    return tmp_path


class EchoClient:
    def __init__(self) -> None:
        self.requests: list[Mapping[str, object]] = []

    def complete_json(
        self,
        *,
        system_prompt: str,
        request: Mapping[str, object],
    ) -> dict[str, Any]:
        assert "JSON" in system_prompt
        self.requests.append(request)
        if "markdown" in request:
            return {
                "translation_id": request["translation_id"],
                "translated_markdown": request["markdown"],
                "warnings": [],
            }
        return {
            "translation_id": request["translation_id"],
            "translated_catalog": request["catalog"],
            "warnings": [],
        }


def test_protected_markdown_round_trip() -> None:
    source = (
        "---\ntitle: Example\n---\n\n# Heading\n\n"
        "Use `pplx-export` at [the site](https://example.com/a?q=1).\n\n"
        "```python\nprint('# unchanged')\n```\n"
    )
    protected = protect_markdown(source)
    assert "pplx-export" not in protected.text
    assert "https://example.com" not in protected.text
    assert "print" not in protected.text
    assert restore_markdown(protected, protected.text) == source


def test_glossary_literal_terms_are_protected() -> None:
    source = "# Perplexity\n\nRun pplx-export through Perplexity Computer.\n"
    protected = protect_markdown(
        source,
        literal_terms=("Perplexity Computer", "Perplexity", "pplx-export"),
    )
    assert "Perplexity" not in protected.text
    assert "pplx-export" not in protected.text
    assert restore_markdown(protected, protected.text) == source


def test_deepseek_client_uses_configurable_model_and_json_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": '{"translated":"ok"}'},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                    },
                }
            ).encode()

    def fake_urlopen(request: object, *, timeout: int) -> Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        "scripts.translate_docs.urllib.request.urlopen",
        fake_urlopen,
    )
    client = DeepSeekClient(
        api_key="test-secret",
        base_url="https://api.deepseek.example/v1",
        model="deepseek-future-model",
        temperature=0.1,
        thinking="disabled",
        max_tokens=12345,
        max_retries=1,
        timeout_seconds=45,
    )
    result = client.complete_json(
        system_prompt="Return JSON.",
        request={"translation_id": "one"},
    )
    assert result == {"translated": "ok"}
    request = captured["request"]
    payload = json.loads(request.data)
    assert request.full_url == "https://api.deepseek.example/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-secret"
    assert captured["timeout"] == 45
    assert payload["model"] == "deepseek-future-model"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 12345
    assert json.loads(payload["messages"][1]["content"]) == {
        "translation_id": "one"
    }
    assert client.usage["total_tokens"] == 12


def test_protected_token_loss_and_duplication_are_rejected() -> None:
    protected = protect_markdown("Use `one` and `two`.\n")
    tokens = list(protected.replacements)
    with pytest.raises(TranslationFailure, match="protected-token contract"):
        restore_markdown(protected, protected.text.replace(tokens[0], ""))
    with pytest.raises(TranslationFailure, match="protected-token contract"):
        restore_markdown(protected, protected.text + tokens[0])


def test_chinese_source_links_become_locale_neutral_without_touching_code() -> None:
    source = (
        "[内部链接](guide/modes.zh-CN.md#表格) "
        "[外部链接](https://example.com/modes.zh-CN.md)\n\n"
        "`guide/modes.zh-CN.md`\n\n"
        "```text\n"
        "guide/modes.zh-CN.md\n"
        "```\n"
    )
    protected = protect_markdown(source)
    normalized = normalize_source_locale_links(
        protected,
        source_locale="zh-CN",
        default_locale="en",
    )
    restored = restore_markdown(normalized, normalized.text)
    assert "[内部链接](guide/modes.md#表格)" in restored
    assert "https://example.com/modes.zh-CN.md" in restored
    assert "`guide/modes.zh-CN.md`" in restored
    assert "```text\nguide/modes.zh-CN.md\n```" in restored


def test_source_heading_aliases_are_stable_and_idempotent() -> None:
    source = (
        "# Configuration\n\n"
        "See [the model](#multi-account-cookie-model).\n\n"
        "## Multi-account cookie model\n"
    )
    translated = (
        "# Configuration\n\n"
        "Voir [le modèle](#multi-account-cookie-model).\n\n"
        "## Modèle de cookies multi-comptes\n"
    )
    refreshed = add_source_heading_anchors(source, translated)
    assert (
        '<a id="multi-account-cookie-model" '
        'data-pplx-source-anchor="true"></a>\n'
        "## Modèle de cookies multi-comptes"
    ) in refreshed
    assert add_source_heading_anchors(source, refreshed) == refreshed


def test_mkdocs_heading_numbers_are_page_local_and_keep_stable_ids() -> None:
    markdown = (
        "# Page\n\n"
        "## Overview\n\n"
        "### Details\n\n"
        "## 401 errors\n\n"
        "### Duplicate\n\n"
        "### Duplicate\n\n"
        "```markdown\n## 9. Not a heading\n```\n"
    )
    rendered = number_page_markdown(
        markdown,
        source_path="guide/example.md",
    )
    assert "# Page {#page}" in rendered
    assert "## a. Overview {#overview}" in rendered
    assert "### a.1 Details {#details}" in rendered
    assert "## b. 401 errors {#401-errors}" in rendered
    assert "### b.1 Duplicate {#duplicate}" in rendered
    assert "### b.2 Duplicate {#duplicate_1}" in rendered
    assert "```markdown\n## 9. Not a heading\n```" in rendered


def test_mkdocs_heading_numbers_strip_only_recorded_legacy_prefixes() -> None:
    rendered = number_page_markdown(
        (
            "# Page\n\n"
            "## 8. Sequence diagram\n\n"
            "### Detail\n\n"
            "## 401 errors\n"
        ),
        source_path="architecture/example.md",
        legacy_documents={
            "architecture/example.md": [
                {
                    "heading_index": 1,
                    "level": 2,
                    "prefix": "8.",
                    "id": "8-sequence-diagram",
                }
            ]
        },
    )
    assert (
        '<a id="8-sequence-diagram" '
        'data-pplx-legacy-heading-anchor="true"></a>'
    ) in rendered
    assert "## 1. Sequence diagram {#sequence-diagram}" in rendered
    assert "### 1.1 Detail {#detail}" in rendered
    assert "## 2. 401 errors {#401-errors}" in rendered


def test_fake_translation_writes_all_registered_outputs(
    i18n_repo: Path,
) -> None:
    client = EchoClient()
    assert run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=client,
    ) == 0
    assert len(client.requests) == 4
    fr = i18n_repo / "docs/index.fr.md"
    ja = i18n_repo / "docs/index.ja.md"
    assert fr.is_file()
    assert ja.is_file()
    assert (i18n_repo / "i18n/generated/fr.json").is_file()
    assert (i18n_repo / "i18n/generated/ja.json").is_file()

    fr_meta = parse_translation_metadata(fr.read_text(encoding="utf-8"))
    ja_meta = parse_translation_metadata(ja.read_text(encoding="utf-8"))
    assert fr_meta["translation_source_locale"] == "en"
    assert ja_meta["translation_source_locale"] == "zh-CN"
    assert fr_meta["translation_source_sha256"] == sha256_file(
        i18n_repo / "docs/index.md"
    )
    assert ja_meta["translation_source_sha256"] == sha256_file(
        i18n_repo / "docs/index.zh-CN.md"
    )

    manifest = json.loads(
        (i18n_repo / "i18n/manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest["documents"]) == {
        "docs/index.md::fr",
        "docs/index.md::ja",
    }
    assert set(manifest["catalogs"]) == {"fr", "ja"}

    assert run(
        root=i18n_repo,
        check=True,
        plan_only=False,
        force=False,
        jobs=None,
        model_override=None,
    ) == 0


def test_source_and_model_changes_invalidate_only_relevant_units(
    i18n_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = EchoClient()
    run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=client,
    )
    capsys.readouterr()
    zh = i18n_repo / "docs/index.zh-CN.md"
    zh.write_text(zh.read_text(encoding="utf-8") + "\n新段落。\n", encoding="utf-8")
    assert run(
        root=i18n_repo,
        check=False,
        plan_only=True,
        force=False,
        jobs=None,
        model_override=None,
    ) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["document_translations_pending"] == 1
    assert plan["catalog_translations_pending"] == 0

    assert run(
        root=i18n_repo,
        check=False,
        plan_only=True,
        force=False,
        jobs=None,
        model_override="deepseek-future-model",
    ) == 0
    model_plan = json.loads(capsys.readouterr().out)
    assert model_plan["document_translations_pending"] == 2
    assert model_plan["catalog_translations_pending"] == 2


def test_frozen_locale_is_not_scheduled_when_source_or_model_changes(
    i18n_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = EchoClient()
    run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=client,
    )
    capsys.readouterr()
    config_path = i18n_repo / "i18n/config.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            '[locales.fr]\nname = "français"\nsource = "en"\n',
            '[locales.fr]\nname = "français"\nsource = "en"\n'
            'frozen_since = "2026-07-30"\n',
        ),
        encoding="utf-8",
    )
    source = i18n_repo / "docs/index.md"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nChanged source.\n",
        encoding="utf-8",
    )

    assert run(
        root=i18n_repo,
        check=False,
        plan_only=True,
        force=False,
        jobs=None,
        model_override="deepseek-future-model",
    ) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["frozen_machine_locales"] == 1
    assert plan["document_translations_pending"] == 1
    assert plan["catalog_translations_pending"] == 1


def test_structural_change_is_rejected_without_writing_outputs(
    i18n_repo: Path,
) -> None:
    class BrokenClient(EchoClient):
        def complete_json(
            self,
            *,
            system_prompt: str,
            request: Mapping[str, object],
        ) -> dict[str, Any]:
            response = super().complete_json(
                system_prompt=system_prompt,
                request=request,
            )
            if "translated_markdown" in response:
                response["translated_markdown"] += "\n## Invented\n"
            return response

    with pytest.raises(TranslationFailure, match="translation tasks failed"):
        run(
            root=i18n_repo,
            check=False,
            plan_only=False,
            force=False,
            jobs=2,
            model_override=None,
            client=BrokenClient(),
        )
    assert not (i18n_repo / "docs/index.fr.md").exists()
    assert not (i18n_repo / "i18n/manifest.json").exists()


def test_deleted_canonical_page_prunes_derived_outputs(
    i18n_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = EchoClient()
    run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=client,
    )
    (i18n_repo / "docs/index.md").unlink()
    (i18n_repo / "docs/index.zh-CN.md").unlink()
    monkeypatch.delenv("DEEKSEEK_API_KEY", raising=False)
    assert run(
        root=i18n_repo,
        check=True,
        plan_only=False,
        force=False,
        jobs=None,
        model_override=None,
    ) == 1
    assert run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
    ) == 0
    assert not (i18n_repo / "docs/index.fr.md").exists()
    assert not (i18n_repo / "docs/index.ja.md").exists()
    manifest = json.loads(
        (i18n_repo / "i18n/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["documents"] == {}


def test_catalog_shape_change_is_rejected(i18n_repo: Path) -> None:
    class BrokenCatalogClient(EchoClient):
        def complete_json(
            self,
            *,
            system_prompt: str,
            request: Mapping[str, object],
        ) -> dict[str, Any]:
            response = super().complete_json(
                system_prompt=system_prompt,
                request=request,
            )
            if "translated_catalog" in response:
                response["translated_catalog"] = {"site_name": "Only one key"}
            return response

    with pytest.raises(TranslationFailure, match="translation tasks failed"):
        run(
            root=i18n_repo,
            check=False,
            plan_only=False,
            force=False,
            jobs=2,
            model_override=None,
            client=BrokenCatalogClient(),
        )


def test_completed_locale_checkpoint_is_reused_after_another_locale_fails(
    i18n_repo: Path,
) -> None:
    class JapaneseFailureClient(EchoClient):
        def complete_json(
            self,
            *,
            system_prompt: str,
            request: Mapping[str, object],
        ) -> dict[str, Any]:
            if request.get("target_locale") == "ja":
                raise TranslationFailure("synthetic Japanese failure")
            return super().complete_json(
                system_prompt=system_prompt,
                request=request,
            )

    checkpoints: list[tuple[str, tuple[Path, ...]]] = []
    with pytest.raises(
        TranslationFailure,
        match="completed locale batches were retained",
    ):
        run(
            root=i18n_repo,
            check=False,
            plan_only=False,
            force=False,
            jobs=2,
            model_override=None,
            client=JapaneseFailureClient(),
            checkpoint_locale=lambda locale, paths: checkpoints.append(
                (locale, paths)
            ),
        )

    assert [locale for locale, _ in checkpoints] == ["fr"]
    assert {
        path.relative_to(i18n_repo).as_posix()
        for path in checkpoints[0][1]
    } == {"docs/index.fr.md", "i18n/generated/fr.json"}
    assert (i18n_repo / "docs/index.fr.md").is_file()
    assert (i18n_repo / "i18n/generated/fr.json").is_file()
    assert not (i18n_repo / "docs/index.ja.md").exists()
    assert not (i18n_repo / "i18n/generated/ja.json").exists()

    manifest = json.loads(
        (i18n_repo / "i18n/manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest["documents"]) == {"docs/index.md::fr"}
    assert set(manifest["catalogs"]) == {"fr"}

    retry_client = EchoClient()
    assert run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=retry_client,
    ) == 0
    assert {
        request["target_locale"] for request in retry_client.requests
    } == {"ja"}


def test_locale_checkpoints_commit_and_push_one_language_batch(
    i18n_repo: Path,
) -> None:
    remote = i18n_repo.parent / f"{i18n_repo.name}-remote.git"

    def git(*args: str, cwd: Path = i18n_repo) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Test Bot")
    git("config", "user.email", "test@example.invalid")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    git("init", "--bare", "-q", str(remote), cwd=i18n_repo.parent)
    git("remote", "add", "origin", str(remote))
    git("push", "-q", "-u", "origin", "main")
    base_sha = git("rev-parse", "HEAD").stdout.strip()
    checkpoint_branch = (
        f"automation/i18n-checkpoints/{base_sha}"
    )

    unrelated = i18n_repo / "unrelated.txt"
    unrelated.write_text("must remain uncommitted\n", encoding="utf-8")
    config = load_i18n_config(i18n_repo)
    assert run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=EchoClient(),
        checkpoint_locale=lambda locale, paths: _commit_locale_checkpoint(
            root=config.root,
            manifest_path=config.manifest_path,
            locale=locale,
            output_paths=paths,
            checkpoint_branch=checkpoint_branch,
        ),
    ) == 0

    messages = git(
        "--git-dir",
        str(remote),
        "log",
        "--format=%s",
        checkpoint_branch,
    ).stdout.splitlines()
    assert set(messages[:2]) == {
        "chore(i18n): translate fr [skip ci]",
        "chore(i18n): translate ja [skip ci]",
    }
    assert messages[2] == "base"
    assert git(
        "--git-dir",
        str(remote),
        "log",
        "--format=%s",
        "main",
    ).stdout.splitlines() == ["base"]
    assert git("status", "--short").stdout == "?? unrelated.txt\n"

    git(
        "fetch",
        "-q",
        "origin",
        f"{checkpoint_branch}:refs/remotes/origin/{checkpoint_branch}",
    )
    assert verify_checkpoint_branch(
        root=i18n_repo,
        base_sha=base_sha,
        checkpoint_branch=checkpoint_branch,
    ) == 0

    for commit in (checkpoint_branch, f"{checkpoint_branch}^"):
        changed = set(
            git(
                "--git-dir",
                str(remote),
                "show",
                "--format=",
                "--name-only",
                commit,
            ).stdout.splitlines()
        )
        assert "i18n/manifest.json" in changed
        assert len(changed) == 3
        assert any(path.startswith("docs/index.") for path in changed)
        assert any(path.startswith("i18n/generated/") for path in changed)


def test_checkpoint_verification_rejects_non_generated_changes(
    i18n_repo: Path,
) -> None:
    remote = i18n_repo.parent / f"{i18n_repo.name}-remote.git"

    def git(*args: str, cwd: Path = i18n_repo) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Test Bot")
    git("config", "user.email", "test@example.invalid")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    base_sha = git("rev-parse", "HEAD").stdout.strip()
    checkpoint_branch = f"automation/i18n-checkpoints/{base_sha}"
    git("switch", "-q", "-c", checkpoint_branch)
    (i18n_repo / "scripts").mkdir()
    (i18n_repo / "scripts/unsafe.py").write_text(
        "raise SystemExit('unsafe')\n",
        encoding="utf-8",
    )
    git("add", "scripts/unsafe.py")
    git("commit", "-q", "-m", "unsafe checkpoint")
    git("init", "--bare", "-q", str(remote), cwd=i18n_repo.parent)
    git("remote", "add", "origin", str(remote))
    git("push", "-q", "origin", checkpoint_branch)
    git(
        "fetch",
        "-q",
        "origin",
        f"{checkpoint_branch}:refs/remotes/origin/{checkpoint_branch}",
    )

    with pytest.raises(
        TranslationFailure,
        match="checkpoint changes non-generated paths",
    ):
        verify_checkpoint_branch(
            root=i18n_repo,
            base_sha=base_sha,
            checkpoint_branch=checkpoint_branch,
        )


def test_checkpoint_mode_queues_complete_locales_before_the_next_locale(
    i18n_repo: Path,
) -> None:
    events: list[tuple[str, str, str]] = []

    class RecordingClient(EchoClient):
        def complete_json(
            self,
            *,
            system_prompt: str,
            request: Mapping[str, object],
        ) -> dict[str, Any]:
            kind = "document" if "markdown" in request else "catalog"
            events.append(("request", str(request["target_locale"]), kind))
            return super().complete_json(
                system_prompt=system_prompt,
                request=request,
            )

    assert run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=1,
        model_override=None,
        client=RecordingClient(),
        checkpoint_locale=lambda locale, paths: events.append(
            ("checkpoint", locale, str(len(paths)))
        ),
    ) == 0
    assert [event for event in events if event[0] == "request"] == [
        ("request", "fr", "document"),
        ("request", "fr", "catalog"),
        ("request", "ja", "document"),
        ("request", "ja", "catalog"),
    ]
    assert [event for event in events if event[0] == "checkpoint"] == [
        ("checkpoint", "fr", "2"),
        ("checkpoint", "ja", "2"),
    ]


def test_heading_anchor_refresh_updates_manifest_without_api_calls(
    i18n_repo: Path,
) -> None:
    assert run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=EchoClient(),
    ) == 0
    french = i18n_repo / "docs/index.fr.md"
    french.write_text(
        french.read_text(encoding="utf-8").replace("# Docs", "# Documentation"),
        encoding="utf-8",
    )
    config = load_i18n_config(i18n_repo)
    checkpoints: list[tuple[str, tuple[Path, ...]]] = []
    assert refresh_heading_anchors(
        config=config,
        manifest=json.loads(
            config.manifest_path.read_text(encoding="utf-8")
        ),
        checkpoint_locale=lambda locale, paths: checkpoints.append(
            (locale, paths)
        ),
    ) == 0
    assert [locale for locale, _ in checkpoints] == ["fr"]
    assert checkpoints[0][1] == (french,)
    assert '<a id="docs" data-pplx-source-anchor="true"></a>' in (
        french.read_text(encoding="utf-8")
    )
    manifest = json.loads(
        config.manifest_path.read_text(encoding="utf-8")
    )
    assert manifest["documents"]["docs/index.md::fr"]["output_sha256"] == (
        sha256_file(french)
    )


def test_heading_anchor_refresh_skips_stale_generated_documents(
    i18n_repo: Path,
) -> None:
    assert run(
        root=i18n_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=2,
        model_override=None,
        client=EchoClient(),
    ) == 0
    french = i18n_repo / "docs/index.fr.md"
    before = french.read_text(encoding="utf-8")
    source = i18n_repo / "docs/index.md"
    source.write_text(
        source.read_text(encoding="utf-8") + "\n## New section\n",
        encoding="utf-8",
    )
    config = load_i18n_config(i18n_repo)
    checkpoints: list[tuple[str, tuple[Path, ...]]] = []
    assert refresh_heading_anchors(
        config=config,
        manifest=json.loads(
            config.manifest_path.read_text(encoding="utf-8")
        ),
        checkpoint_locale=lambda locale, paths: checkpoints.append(
            (locale, paths)
        ),
    ) == 0
    assert checkpoints == []
    assert french.read_text(encoding="utf-8") == before


def test_repository_registry_covers_selected_supported_languages() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_i18n_config(root)
    expected_locales = {
        "ar",
        "de",
        "en",
        "es",
        "fr",
        "it",
        "ja",
        "ko",
        "pt",
        "ru",
        "zh-CN",
        "zh-Hant",
    }
    assert set(config.locales) == expected_locales

    material_languages = {
        path.stem
        for path in (
            Path(material.__file__).resolve().parent
            / "templates"
            / "partials"
            / "languages"
        ).glob("*.html")
    }
    assert {
        locale.theme_language for locale in config.locales.values()
    } <= material_languages

    configured_mkdocs = set(
        re.findall(
            r"^[ ]+- locale: ([A-Za-z]{2}(?:-[A-Za-z]{2,4})?)$",
            (root / "mkdocs.yml").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    assert configured_mkdocs == set(config.locales)


def test_repository_product_titles_do_not_name_the_archive_feature() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "README.md").read_text(encoding="utf-8").splitlines()[0] == (
        "# Perplexity CLI toolkit (NOT for pay-as-go API)"
    )
    assert (
        root / "README.zh-CN.md"
    ).read_text(encoding="utf-8").splitlines()[0] == (
        "# Perplexity 命令行工具集（适用于现有订阅而非按量计费 API）"
    )
    assert (root / "docs/index.md").read_text(
        encoding="utf-8"
    ).splitlines()[0] == "# Perplexity CLI toolkit"
    assert (root / "docs/index.zh-CN.md").read_text(
        encoding="utf-8"
    ).splitlines()[0] == "# Perplexity 命令行工具集"

    english_catalog = json.loads(
        (root / "i18n/catalog.en.json").read_text(encoding="utf-8")
    )
    chinese_catalog = json.loads(
        (root / "i18n/catalog.zh-CN.json").read_text(encoding="utf-8")
    )
    assert english_catalog["site_name"] == "Perplexity CLI toolkit"
    assert chinese_catalog["site_name"] == "Perplexity 命令行工具集"

    mkdocs = (root / "mkdocs.yml").read_text(encoding="utf-8")
    assert mkdocs.startswith("site_name: Perplexity CLI toolkit\n")
    assert "site_name: Perplexity 命令行工具集\n" in mkdocs


def test_repository_navigation_scopes_top_level_sections_by_path() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "docs/javascripts/navigation-state.js").read_text(
        encoding="utf-8"
    )
    for path in (
        "/guide/",
        "/architecture/",
        "/reference/api/",
        "/development/",
    ):
        assert json.dumps(path) in script
    assert "currentPath.startsWith(sectionPath)" in script
    assert (
        'const visibleOnlyWithinSections = new Set(["/reference/api/"]);'
        in script
    )
    assert 'const numberedSections = new Set(["/guide/"]);' in script
    assert "item.hidden = hiddenOutsideSection" in script
    assert (
        'item.classList.toggle("pplx-nav--section-hidden", hiddenOutsideSection)'
        in script
    )
    assert "numberedSections.has(sectionPath)" in script
    assert "numberNavigationList(item)" in script
    assert "marker.remove()" in script
    assert 'marker.className = "pplx-nav-number"' in script
    assert 'marker.setAttribute("aria-hidden", "true")' in script
    assert "parts.join(\".\")" in script
    assert 'item.classList.add("pplx-nav--path-aware")' in script
    assert 'item.classList.toggle("pplx-nav--open", expanded)' in script
    assert 'window.matchMedia("(min-width: 76.25em)")' in script
    assert "if (!desktopNavigation.matches)" in script
    assert "desktopNavigation.addEventListener(\"change\", schedule)" in script
    assert "desktopToggleHandlers = new WeakMap()" in script
    assert 'label.removeEventListener("click", handler)' in script
    assert 'nestedToggle.closest("nav.md-nav--secondary") === null' in script
    assert 'nestedItem?.classList.contains("md-nav__item--active")' in script
    assert "nestedToggle.checked = true" in script
    stylesheet = (root / "docs/stylesheets/extra.css").read_text(
        encoding="utf-8"
    )
    assert ".pplx-nav--section-hidden" in stylesheet
    assert ".md-nav--primary .pplx-nav-number" in stylesheet
    assert "display: none !important" in stylesheet
    assert ".md-typeset :is(h1, h2, h3, h4, h5, h6)" in stylesheet
    assert "font-weight: 700" in stylesheet
    locale_script = (
        root / "docs/javascripts/language-preference.js"
    ).read_text(encoding="utf-8")
    assert 'const storageKey = "pplx-tools-doc-locale"' in locale_script
    assert "navigator.languages || [navigator.language]" in locale_script
    assert 'if (path !== "/") return' in locale_script
    assert "window.location.replace(destination)" in locale_script
    mkdocs = (root / "mkdocs.yml").read_text(encoding="utf-8")
    assert "stylesheets/extra.css?v=20260725-guide-numbering" in mkdocs
    assert (
        "javascripts/language-preference.js?v=20260725-locale-routing"
        in mkdocs
    )
    assert (
        "javascripts/navigation-state.js?v=20260725-responsive-nav"
        in mkdocs
    )
    assert "\nplugins:\n  - search:" in mkdocs
    for path in (
        "reference/api/index.md",
        "reference/api/api-authentication.md",
        "reference/api/api-graphql.md",
        "reference/api/api-rest-endpoints.md",
        "reference/api/api-responses-errors.md",
        "reference/api/api-discovery-roadmap.md",
    ):
        assert path in mkdocs
        assert (root / "docs" / path).is_file()


def test_repository_pages_workflow_uses_node24_actions() -> None:
    root = Path(__file__).resolve().parents[1]
    quality = (root / ".github/workflows/quality.yml").read_text(
        encoding="utf-8"
    )
    translation = (
        root / ".github/workflows/translate-docs.yml"
    ).read_text(encoding="utf-8")

    checkout = (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 "
        "# v7"
    )
    assert checkout in quality
    assert checkout in translation
    assert (
        "actions/upload-pages-artifact@"
        "fc324d3547104276b827a68afc52ff2a11cc49c9 # v5"
    ) in translation
    assert (
        "actions/deploy-pages@"
        "cd2ce8fcbc39b97be8ca5fce6e763baed58fa128 # v5"
    ) in translation
    assert "needs: translate-validate-build" in translation
    assert "pages: write" in translation
    assert "id-token: write" in translation
    assert "run: uv run mkdocs gh-deploy" not in translation


def test_repository_workflows_are_valid_yaml() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in (
        ".github/workflows/quality.yml",
        ".github/workflows/translate-docs.yml",
    ):
        assert yaml.compose(
            (root / relative).read_text(encoding="utf-8")
        ) is not None


def test_quality_workflow_always_supplies_an_exact_changed_base() -> None:
    root = Path(__file__).resolve().parents[1]
    quality = (root / ".github/workflows/quality.yml").read_text(
        encoding="utf-8"
    )
    assert "changed_base:" in quality
    assert "required: true" in quality
    assert "PUSH_BASE_SHA: ${{ github.event.before }}" in quality
    assert "MANUAL_BASE_SHA: ${{ inputs.changed_base }}" in quality
    assert '[[ ! "${changed_base}" =~ ^[0-9a-fA-F]{40}$ ]]' in quality
    assert 'git merge-base --is-ancestor "${changed_base}" HEAD' in quality
    assert 'args+=(--changed-base "${changed_base}")' in quality
    assert 'if [[ -n "${PR_BASE_SHA}" ]]' not in quality


def test_quality_workflow_lints_before_tests() -> None:
    root = Path(__file__).resolve().parents[1]
    quality = (root / ".github/workflows/quality.yml").read_text(
        encoding="utf-8"
    )
    assert "run: uv run ruff check ." in quality
    assert quality.index("run: uv run ruff check .") < quality.index(
        "run: uv run pytest -q"
    )


def test_quality_workflow_gates_sensitive_core_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    quality = (root / ".github/workflows/quality.yml").read_text(
        encoding="utf-8"
    )
    # The targeted gate is the mechanized mapping of the boundary declared in
    # pplx_export/core/AGENTS.md and must reference it in its output.
    # 靶向门禁是 pplx_export/core/AGENTS.md 声明边界的机械化映射，
    # 其输出必须引用该边界文件。
    assert (root / "pplx_export/core/AGENTS.md").is_file()
    assert quality.count("pplx_export/core/AGENTS.md") >= 1
    assert (
        "git diff --name-only \"${changed_base}\" HEAD "
        "-- 'pplx_export/core/'"
    ) in quality
    for targeted in (
        "tests/test_credential.py",
        "tests/test_cookie_profiles.py",
        "tests/test_fix_n04_cookies.py",
        "tests/test_fix_n05_n06_n09.py",
    ):
        assert targeted in quality
    # The sensitive-path gate runs before the full suite and never replaces it.
    # 敏感路径门禁在全量套件之前运行，且绝不替代全量门禁。
    assert "- name: Run sensitive core boundary targeted tests" in quality
    assert "run: uv run pytest -q" in quality
    assert quality.index(
        "- name: Run sensitive core boundary targeted tests"
    ) < quality.index("- name: Run tests")


def test_translation_workflow_binds_validation_and_checkpoints_before_main() -> None:
    root = Path(__file__).resolve().parents[1]
    translation = (
        root / ".github/workflows/translate-docs.yml"
    ).read_text(encoding="utf-8")
    config = load_i18n_config(root)

    assert translation.startswith(
        "name: translate-docs\n\non:\n"
    )
    assert "\npermissions:\n  contents: read\n" in translation
    assert "\n    permissions:\n      contents: write\n" in translation
    assert "github.event.workflow_run.event == 'push'" in translation
    assert "github.event.workflow_run.head_sha" in translation
    assert "ref: main" not in translation
    assert 'CHECKPOINT_BRANCH=${checkpoint_branch}' in translation
    assert "--verify-checkpoint" in translation
    assert "--checkpoint-base \"${BASE_SHA}\"" in translation
    assert "HEAD:refs/heads/${CHECKPOINT_BRANCH}" in translation
    assert "git push origin HEAD:main" in translation
    assert "git push origin --delete \"${CHECKPOINT_BRANCH}\"" in translation
    assert "--jobs 8" not in translation
    assert "'refs/heads/automation/i18n-checkpoints/*'" in translation
    assert (
        'git merge-base --is-ancestor "${stale_base}" "${BASE_SHA}"'
        in translation
    )
    assert "--checkpoint-base \"${stale_base}\"" in translation
    assert "--checkpoint-branch \"${stale_branch}\"" in translation
    assert "git push origin --delete \"${stale_branch}\"" in translation
    assert translation.index("--checkpoint-base \"${stale_base}\"") < (
        translation.index("git push origin --delete \"${stale_branch}\"")
    )

    secret_binding = (
        f"{config.translation.api_key_env}: "
        f"${{{{ secrets.{config.translation.api_key_env} }}}}"
    )
    assert translation.count(secret_binding) == 1
    assert translation.index("Check dependency lock") < translation.index(
        secret_binding
    )
    assert translation.index(
        "Reconfirm current main before API access"
    ) < translation.index(secret_binding)
    assert translation.count("--verify-checkpoint") == 3
    assert translation.index(
        "Promote the fully validated checkpoint to main"
    ) < translation.index("Upload validated GitHub Pages artifact")


def test_repository_machine_documents_support_canonical_heading_aliases() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_i18n_config(root)
    for default_path in canonical_default_documents(config):
        for locale in config.machine_locales:
            assert locale.source is not None
            source_path = canonical_source_path(
                default_path,
                locale.source,
                config,
            )
            output_path = generated_document_path(
                default_path,
                locale.code,
                config,
            )
            if not output_path.is_file():
                continue
            output = output_path.read_text(encoding="utf-8")
            metadata = parse_translation_metadata(output)
            if metadata.get("translation_source_sha256") != sha256_file(
                source_path
            ):
                continue
            add_source_heading_anchors(
                source_path.read_text(encoding="utf-8"),
                output,
            )

    source = (root / "docs/guide/configuration.md").read_text(
        encoding="utf-8"
    )
    french = (root / "docs/guide/configuration.fr.md").read_text(
        encoding="utf-8"
    )
    assert (
        '<a id="multi-account-cookie-model" '
        'data-pplx-source-anchor="true"></a>'
    ) in add_source_heading_anchors(source, french)


def test_east_asian_locales_use_chinese_and_others_use_english() -> None:
    config = load_i18n_config(Path(__file__).resolve().parents[1])
    chinese_source = {"ja", "ko", "zh-Hant"}
    assert all(
        locale.frozen_since == "2026-07-30"
        for locale in config.machine_locales
    )
    assert config.active_machine_locales == ()
    assert {
        locale.code
        for locale in config.machine_locales
        if locale.source == "zh-CN"
    } == chinese_source
    assert all(
        locale.source == "en"
        for locale in config.machine_locales
        if locale.code not in chinese_source
    )


def test_mkdocs_hook_localizes_navigation_and_machine_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = {
        "site_name": "Documentation française",
        "site_description": "Description française",
        "machine_notice_title": "Traduction automatique",
        "machine_notice_text": "Cette page a été traduite automatiquement.",
        "source_link_label": "Source anglaise",
        "report_link_label": "Signaler un problème",
        "nav": {"Home": "Accueil", "User guide": "Guide"},
    }
    monkeypatch.setattr(mkdocs_i18n, "_catalog", lambda locale: catalog)

    class Item:
        def __init__(self, title: str, children: list[object] | None = None):
            self.title = title
            self.children = children or []

    class Theme(dict):
        pass

    class Config:
        theme = Theme(language="fr")
        site_name = "English"
        site_description = "English description"

    nav = type("Nav", (), {"items": [Item("Home", [Item("User guide")])]})()
    config = Config()
    localized = mkdocs_i18n.on_nav(nav, config, [])
    assert localized.items[0].title == "Accueil"
    assert localized.items[0].children[0].title == "Guide"
    assert config.site_name == "Documentation française"

    page = type(
        "Page",
        (),
        {
            "meta": {
                "translation_kind": "machine",
                "translation_source_locale": "en",
                "translation_source_path": "docs/index.md",
            },
            "file": type("File", (), {"src_path": "index.fr.md"})(),
        },
    )()
    result = mkdocs_i18n.on_page_markdown("# Titre\n", page, None, None)
    assert result.startswith('!!! warning "Translation no longer maintained"')
    assert "no longer maintained as of 2026-07-30" in result
    assert '<a href="/">English source</a>' in result
    assert "Target+locale%3A+fr" not in result
    assert result.endswith("# Titre\n")
