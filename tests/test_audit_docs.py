"""Isolated tests for the read-only documentation auditor.

文档只读审计器的隔离测试。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

import pytest

from scripts.audit_docs import (
    FIXTURE_CONTRACT,
    audit_repository,
    format_github,
    format_json,
    main,
)
from scripts.translate_docs import run as run_translations


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fixture_page(language: str) -> str:
    source = "模拟数据" if language == "zh" else "simulated data"
    return (
        f"# Fixtures\n\n{FIXTURE_CONTRACT}\n\nAll inputs are {source}.\n\n"
        "<!-- audit:inventory fixture-directories -->\n"
        "- `deep_research_demo`\n"
        "<!-- /audit:inventory fixture-directories -->\n"
    )


def _testing_page() -> str:
    return (
        "# Testing\n\n"
        "<!-- audit:inventory test-modules -->\n"
        "- `test_alpha.py`\n"
        "<!-- /audit:inventory test-modules -->\n"
    )


def _enable_machine_i18n(root: Path) -> None:
    _write(
        root,
        "mkdocs.yml",
        """
plugins:
  - i18n:
      languages:
        - locale: en
        - locale: zh-CN
        - locale: fr
""",
    )
    _write(
        root,
        "i18n/config.toml",
        """
schema_version = 1
default_locale = "en"
canonical_locales = ["en", "zh-CN"]
docs_dir = "docs"
manifest_path = "i18n/manifest.json"
generated_catalog_dir = "i18n/generated"
excluded_docs = ["README.md", "development/testing.md", "development/fixtures.md"]

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
max_concurrency = 1
max_retries = 1
max_tokens = 4096
request_timeout_seconds = 30

[locales.en]
name = "English"
machine = false

[locales.zh-CN]
name = "简体中文"
machine = false

[locales.fr]
name = "français"
source = "en"
""",
    )
    _write(root, "i18n/prompts/markdown.md", "Return JSON Markdown.")
    _write(root, "i18n/prompts/catalog.md", "Return JSON catalog.")
    _write(root, "i18n/glossary.json", "{}\n")
    _write(
        root,
        "i18n/catalog.en.json",
        '{"site_name":"Docs","nav":{"Home":"Home"}}\n',
    )
    _write(
        root,
        "i18n/catalog.zh-CN.json",
        '{"site_name":"文档","nav":{"Home":"首页"}}\n',
    )


class _EchoTranslationClient:
    def complete_json(
        self,
        *,
        system_prompt: str,
        request: Mapping[str, object],
    ) -> dict[str, Any]:
        assert "JSON" in system_prompt
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


@pytest.fixture()
def mini_repo(tmp_path: Path) -> Path:
    """Build a complete miniature repository; no test reads the real checkout.

    构建完整的微型仓库；测试不会读取真实检出。"""
    _write(tmp_path, "README.md", "# Home\n")
    _write(tmp_path, "README.zh-CN.md", "# 首页\n")
    _write(tmp_path, "pplx_export/README.md", "# Package\n")
    _write(tmp_path, "pplx_export/README.zh-CN.md", "# 包\n")
    _write(tmp_path, "pplx_export/example.py", "one = 1\ntwo = 2\nthree = 3\n")
    _write(tmp_path, "tests/test_alpha.py", "def test_alpha():\n    assert True\n")
    _write(tmp_path, "tests/fixtures/deep_research_demo/raw_entries.json", "{}\n")

    index_en = (
        "# Docs\n\n"
        "See [testing](development/testing.md).\n\n"
        "Reference: `pplx_export/example.py:1-3`.\n\n"
        "```bash\n# not a heading\n```\n"
    )
    index_zh = (
        "# 文档\n\n"
        "见[测试](development/testing.zh-CN.md)。\n\n"
        "引用：`pplx_export/example.py:1-3`。\n\n"
        "```bash\n# 不是标题\n```\n"
    )
    _write(tmp_path, "docs/index.md", index_en)
    _write(tmp_path, "docs/index.zh-CN.md", index_zh)
    _write(tmp_path, "docs/development/testing.md", _testing_page())
    _write(tmp_path, "docs/development/testing.zh-CN.md", _testing_page())
    _write(tmp_path, "docs/development/fixtures.md", _fixture_page("en"))
    _write(tmp_path, "docs/development/fixtures.zh-CN.md", _fixture_page("zh"))
    _write(tmp_path, "tests/fixtures/README.md", _fixture_page("en"))
    _write(tmp_path, "tests/fixtures/README.zh-CN.md", _fixture_page("zh"))
    return tmp_path


def _codes(root: Path) -> list[str]:
    return [finding.code for finding in audit_repository(root).findings]


def test_clean_mini_repository_passes(mini_repo: Path) -> None:
    report = audit_repository(mini_repo)
    assert report.ok
    assert report.findings == []
    assert report.stats.test_modules == 1
    assert report.stats.fixture_directories == 1
    assert report.stats.bilingual_pairs == 6


@pytest.mark.parametrize(
    ("remove", "expected_fragment"),
    [
        ("docs/index.zh-CN.md", "missing Chinese pair"),
        ("docs/index.md", "missing English pair"),
    ],
)
def test_missing_bilingual_pair(
    mini_repo: Path, remove: str, expected_fragment: str
) -> None:
    (mini_repo / remove).unlink()
    report = audit_repository(mini_repo)
    matches = [finding for finding in report.findings if finding.code == "DOC-PAIR-001"]
    assert len(matches) == 1
    assert expected_fragment in matches[0].message


def test_heading_mismatch_ignores_fenced_heading(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.zh-CN.md"
    path.write_text(path.read_text() + "\n## 新小节\n", encoding="utf-8")
    assert "DOC-HEAD-001" in _codes(mini_repo)


def test_manual_outline_heading_is_reported_but_http_status_is_not(
    mini_repo: Path,
) -> None:
    en = mini_repo / "docs/index.md"
    zh = mini_repo / "docs/index.zh-CN.md"
    en.write_text(en.read_text() + "\n## 8. Sequence\n\n## 401 errors\n")
    zh.write_text(zh.read_text() + "\n## 8. 时序\n\n## 401 错误\n")
    report = audit_repository(mini_repo)
    numbered = [
        finding for finding in report.findings
        if finding.code == "DOC-HEAD-002"
    ]
    assert {finding.path for finding in numbered} == {
        "docs/index.md",
        "docs/index.zh-CN.md",
    }
    assert all(finding.line is not None for finding in numbered)


def test_unclosed_fence_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(path.read_text() + "\n```python\nprint('x')\n", encoding="utf-8")
    assert "DOC-FENCE-001" in _codes(mini_repo)


def test_fence_language_mismatch_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.zh-CN.md"
    text = path.read_text().replace("```bash", "```python")
    path.write_text(text, encoding="utf-8")
    assert "DOC-FENCE-002" in _codes(mini_repo)


def test_missing_local_link_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(
        path.read_text() + "\n[missing](development/missing.md)\n",
        encoding="utf-8",
    )
    assert "DOC-LINK-001" in _codes(mini_repo)


def test_local_link_cannot_escape_repository(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(
        path.read_text() + "\n[outside](../../outside.md)\n",
        encoding="utf-8",
    )
    assert "DOC-LINK-002" in _codes(mini_repo)


def test_external_mail_and_fragment_links_are_ignored(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(
        path.read_text()
        + "\n[web](https://example.com) [mail](mailto:a@example.com) [local](#docs)\n",
        encoding="utf-8",
    )
    assert audit_repository(mini_repo).ok


def test_source_reference_out_of_range_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(
        path.read_text().replace("example.py:1-3", "example.py:1-30"),
        encoding="utf-8",
    )
    assert "DOC-SRC-003" in _codes(mini_repo)


def test_source_reference_reversed_range_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(
        path.read_text().replace("example.py:1-3", "example.py:3-1"),
        encoding="utf-8",
    )
    assert "DOC-SRC-004" in _codes(mini_repo)


def test_missing_source_reference_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(
        path.read_text().replace(
            "pplx_export/example.py:1-3",
            "pplx_export/missing.py:1",
        ),
        encoding="utf-8",
    )
    assert "DOC-SRC-001" in _codes(mini_repo)


def test_unique_short_source_reference_resolves(mini_repo: Path) -> None:
    for relative in ("docs/index.md", "docs/index.zh-CN.md"):
        path = mini_repo / relative
        path.write_text(
            path.read_text().replace("pplx_export/example.py:1-3", "example.py:1,3"),
            encoding="utf-8",
        )
    assert audit_repository(mini_repo).ok


def test_ambiguous_short_source_reference_is_reported(mini_repo: Path) -> None:
    _write(mini_repo, "tests/example.py", "value = 1\n")
    for relative in ("docs/index.md", "docs/index.zh-CN.md"):
        path = mini_repo / relative
        path.write_text(
            path.read_text().replace("pplx_export/example.py:1-3", "example.py:1"),
            encoding="utf-8",
        )
    assert "DOC-SRC-002" in _codes(mini_repo)


def test_mermaid_source_refs_are_checked_but_other_fences_are_ignored(
    mini_repo: Path,
) -> None:
    for relative in ("docs/index.md", "docs/index.zh-CN.md"):
        path = mini_repo / relative
        path.write_text(
            path.read_text()
            + "\n```mermaid\n"
            + 'flowchart LR\nA["example.py:30"]\n'
            + "```\n"
            + "\n```python\n"
            + 'example = "missing.py:999"\n'
            + "```\n",
            encoding="utf-8",
        )
    codes = _codes(mini_repo)
    assert "DOC-SRC-003" in codes
    assert "DOC-SRC-001" not in codes


@pytest.mark.parametrize(
    ("document", "expected_code"),
    [
        ("docs/development/testing.md", "DOC-INV-002"),
        ("docs/development/testing.zh-CN.md", "DOC-INV-002"),
    ],
)
def test_test_inventory_omission_is_reported(
    mini_repo: Path, document: str, expected_code: str
) -> None:
    path = mini_repo / document
    path.write_text(path.read_text().replace("- `test_alpha.py`\n", ""), encoding="utf-8")
    assert expected_code in _codes(mini_repo)


def test_stale_test_inventory_entry_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/development/testing.md"
    path.write_text(
        path.read_text().replace(
            "- `test_alpha.py`\n",
            "- `test_alpha.py`\n- `test_missing.py`\n",
        ),
        encoding="utf-8",
    )
    assert "DOC-INV-003" in _codes(mini_repo)


def test_duplicate_inventory_entry_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "docs/development/testing.md"
    path.write_text(
        path.read_text().replace(
            "- `test_alpha.py`\n",
            "- `test_alpha.py`\n- `test_alpha.py`\n",
        ),
        encoding="utf-8",
    )
    assert "DOC-INV-004" in _codes(mini_repo)


@pytest.mark.parametrize(
    "document",
    [
        "docs/development/fixtures.md",
        "docs/development/fixtures.zh-CN.md",
        "tests/fixtures/README.md",
        "tests/fixtures/README.zh-CN.md",
    ],
)
def test_fixture_inventory_omission_is_reported(
    mini_repo: Path, document: str
) -> None:
    path = mini_repo / document
    path.write_text(
        path.read_text().replace("- `deep_research_demo`\n", ""),
        encoding="utf-8",
    )
    assert "DOC-INV-002" in _codes(mini_repo)


def test_missing_fixture_contract_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "tests/fixtures/README.md"
    path.write_text(path.read_text().replace(FIXTURE_CONTRACT + "\n\n", ""), encoding="utf-8")
    assert "DOC-CONTRACT-001" in _codes(mini_repo)


def test_visible_simulated_data_statement_is_required(mini_repo: Path) -> None:
    path = mini_repo / "tests/fixtures/README.md"
    path.write_text(
        path.read_text().replace("simulated data", "fixture examples"),
        encoding="utf-8",
    )
    assert "DOC-CONTRACT-002" in _codes(mini_repo)


def test_negative_web_archive_statement_is_allowed(mini_repo: Path) -> None:
    path = mini_repo / "tests/fixtures/README.md"
    path.write_text(
        path.read_text()
        + "\nThe simulated data is not copied from `web_archive/`.\n",
        encoding="utf-8",
    )
    assert audit_repository(mini_repo).ok


def test_stale_fixture_provenance_is_reported(mini_repo: Path) -> None:
    path = mini_repo / "tests/fixtures/README.md"
    path.write_text(
        path.read_text() + "\nRaw API captures of representative threads.\n",
        encoding="utf-8",
    )
    assert "DOC-CONTRACT-003" in _codes(mini_repo)


def test_json_and_github_formats_are_stable(mini_repo: Path) -> None:
    path = mini_repo / "docs/index.md"
    path.write_text(path.read_text() + "\n[missing](missing%file.md)\n", encoding="utf-8")
    report = audit_repository(mini_repo)
    payload = json.loads(format_json(report))
    assert payload["ok"] is False
    assert payload["summary"]["errors"] >= 1
    github = format_github(report)
    assert "::error file=docs/index.md" in github
    assert "%25" in github


def test_cli_exit_codes_and_root_override(
    mini_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--root", str(mini_repo), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    path = mini_repo / "docs/index.md"
    path.write_text(path.read_text() + "\n[missing](missing.md)\n", encoding="utf-8")
    assert main(["--root", str(mini_repo)]) == 1
    assert "DOC-LINK-001" in capsys.readouterr().out


def test_cli_invalid_root_uses_argument_error_exit_code(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--root", str(tmp_path / "missing")])
    assert exc_info.value.code == 2


def test_audit_does_not_modify_repository(mini_repo: Path) -> None:
    before = {
        path.relative_to(mini_repo): path.read_bytes()
        for path in mini_repo.rglob("*")
        if path.is_file()
    }
    audit_repository(mini_repo)
    after = {
        path.relative_to(mini_repo): path.read_bytes()
        for path in mini_repo.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_machine_mode_allows_missing_outputs_on_canonical_pr(
    mini_repo: Path,
) -> None:
    _enable_machine_i18n(mini_repo)
    report = audit_repository(mini_repo, machine_mode="allow-stale")
    assert report.ok
    assert report.stats.machine_locales == 1
    assert report.stats.machine_documents == 0


def test_required_machine_mode_accepts_current_generated_outputs(
    mini_repo: Path,
) -> None:
    _enable_machine_i18n(mini_repo)
    assert run_translations(
        root=mini_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=1,
        model_override=None,
        client=_EchoTranslationClient(),
    ) == 0
    report = audit_repository(mini_repo, machine_mode="required")
    assert report.ok
    assert report.stats.machine_documents == 1


def test_required_machine_mode_detects_stale_and_modified_outputs(
    mini_repo: Path,
) -> None:
    _enable_machine_i18n(mini_repo)
    run_translations(
        root=mini_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=1,
        model_override=None,
        client=_EchoTranslationClient(),
    )
    source = mini_repo / "docs/index.md"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nChanged source.\n",
        encoding="utf-8",
    )
    assert "DOC-I18N-003" in [
        finding.code
        for finding in audit_repository(
            mini_repo,
            machine_mode="required",
        ).findings
    ]

    generated = mini_repo / "docs/index.fr.md"
    generated.write_text(
        generated.read_text(encoding="utf-8") + "\nManual edit.\n",
        encoding="utf-8",
    )
    codes = [
        finding.code
        for finding in audit_repository(
            mini_repo,
            machine_mode="required",
        ).findings
    ]
    assert "DOC-I18N-004" in codes


def test_required_machine_mode_allows_frozen_stale_outputs_but_not_modifications(
    mini_repo: Path,
) -> None:
    _enable_machine_i18n(mini_repo)
    run_translations(
        root=mini_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=1,
        model_override=None,
        client=_EchoTranslationClient(),
    )
    config_path = mini_repo / "i18n/config.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            '[locales.fr]\nname = "français"\nsource = "en"\n',
            '[locales.fr]\nname = "français"\nsource = "en"\n'
            'frozen_since = "2026-07-30"\n',
        ),
        encoding="utf-8",
    )
    source = mini_repo / "docs/index.md"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nChanged source.\n",
        encoding="utf-8",
    )
    report = audit_repository(mini_repo, machine_mode="required")
    assert "DOC-I18N-003" not in [finding.code for finding in report.findings]

    generated = mini_repo / "docs/index.fr.md"
    generated.write_text(
        generated.read_text(encoding="utf-8") + "\nManual edit.\n",
        encoding="utf-8",
    )
    assert "DOC-I18N-004" in [
        finding.code
        for finding in audit_repository(
            mini_repo,
            machine_mode="required",
        ).findings
    ]


def test_allow_stale_mode_does_not_block_canonical_heading_change(
    mini_repo: Path,
) -> None:
    _enable_machine_i18n(mini_repo)
    run_translations(
        root=mini_repo,
        check=False,
        plan_only=False,
        force=False,
        jobs=1,
        model_override=None,
        client=_EchoTranslationClient(),
    )
    for relative, heading in (
        ("docs/index.md", "## New section\n"),
        ("docs/index.zh-CN.md", "## 新章节\n"),
    ):
        path = mini_repo / relative
        path.write_text(
            path.read_text(encoding="utf-8") + f"\n{heading}",
            encoding="utf-8",
        )
    report = audit_repository(mini_repo, machine_mode="allow-stale")
    assert report.ok
    assert "DOC-I18N-006" not in [finding.code for finding in report.findings]


def test_required_machine_mode_reports_missing_output(mini_repo: Path) -> None:
    _enable_machine_i18n(mini_repo)
    codes = [
        finding.code
        for finding in audit_repository(
            mini_repo,
            machine_mode="required",
        ).findings
    ]
    assert "DOC-I18N-001" in codes
    assert "DOC-I18N-002" in codes


def test_changed_canonical_document_requires_changed_counterpart(
    mini_repo: Path,
) -> None:
    _enable_machine_i18n(mini_repo)
    subprocess.run(["git", "init", "-q"], cwd=mini_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=mini_repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "base",
        ],
        cwd=mini_repo,
        check=True,
    )
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=mini_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    english = mini_repo / "docs/index.md"
    english.write_text(
        english.read_text(encoding="utf-8") + "\nChanged.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "docs/index.md"], cwd=mini_repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "english only",
        ],
        cwd=mini_repo,
        check=True,
    )
    report = audit_repository(
        mini_repo,
        machine_mode="allow-stale",
        changed_base=base,
    )
    assert "DOC-PAIR-002" in [finding.code for finding in report.findings]

    chinese = mini_repo / "docs/index.zh-CN.md"
    chinese.write_text(
        chinese.read_text(encoding="utf-8") + "\n已变更。\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "docs/index.zh-CN.md"],
        cwd=mini_repo,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "chinese counterpart",
        ],
        cwd=mini_repo,
        check=True,
    )
    report = audit_repository(
        mini_repo,
        machine_mode="allow-stale",
        changed_base=base,
    )
    assert "DOC-PAIR-002" not in [finding.code for finding in report.findings]


def test_changed_pair_check_includes_staged_and_unstaged_worktree(
    mini_repo: Path,
) -> None:
    _enable_machine_i18n(mini_repo)
    subprocess.run(["git", "init", "-q"], cwd=mini_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=mini_repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "base",
        ],
        cwd=mini_repo,
        check=True,
    )
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=mini_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    english = mini_repo / "docs/index.md"
    english.write_text(
        english.read_text(encoding="utf-8") + "\nStaged change.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "docs/index.md"], cwd=mini_repo, check=True)
    report = audit_repository(
        mini_repo,
        machine_mode="allow-stale",
        changed_base=base,
    )
    assert "DOC-PAIR-002" in [
        finding.code for finding in report.findings
    ]

    chinese = mini_repo / "docs/index.zh-CN.md"
    chinese.write_text(
        chinese.read_text(encoding="utf-8") + "\n未暂存变更。\n",
        encoding="utf-8",
    )
    report = audit_repository(
        mini_repo,
        machine_mode="allow-stale",
        changed_base=base,
    )
    assert "DOC-PAIR-002" not in [
        finding.code for finding in report.findings
    ]


def test_invalid_changed_base_is_cli_invocation_error(
    mini_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _enable_machine_i18n(mini_repo)
    subprocess.run(["git", "init", "-q"], cwd=mini_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=mini_repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "base",
        ],
        cwd=mini_repo,
        check=True,
    )
    assert main(
        [
            "--root",
            str(mini_repo),
            "--changed-base",
            "not-a-commit",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert "docs audit invocation error" in captured.err
    assert "DOC-PAIR-002" not in captured.out
