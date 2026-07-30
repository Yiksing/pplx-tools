"""Fix H01: the --check residue gate must report unexecuted check classes
explicitly (machine-readable) instead of silently passing when the identity /
content replacement sources are absent, and the CI workflow steps must publish
those classes to the step summary.

修复 H01：--check 残留门禁在身份/内容替换源缺失时必须显式（机器可读）报告
未执行的检查类，而非静默通过；CI 工作流步骤须把这些类写入步骤摘要。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import scrub_fixtures as sf
from pplx_export import config as cfg

ROOT = Path(__file__).resolve().parents[1]

PARTIAL_CONFIG_TOML = """\
default_account = "zz-unique-account"

[accounts.zz-unique-account]
display_name = "Zz Unique Display"
email = "zz-unique@example.invalid"
"""


def _run_check(monkeypatch, capsys, pairs_local: Path) -> tuple[int, str]:
    monkeypatch.setattr(sf, "PAIRS_LOCAL", pairs_local)
    monkeypatch.setattr(sys, "argv", ["scrub_fixtures.py", "--check"])
    rc = sf.main()
    return rc, capsys.readouterr().out


def test_check_reports_identity_and_content_unexecuted(monkeypatch, capsys, tmp_path):
    # Simulate the CI runner: empty account registry, no local pairs file.
    # 模拟 CI 运行器：账户注册表为空，本地内容对文件缺失。
    empty = tmp_path / "config.toml"
    empty.write_text("", encoding="utf-8")
    cfg.configure(empty)
    rc, out = _run_check(monkeypatch, capsys, tmp_path / "scrub_pairs.local.json")
    assert rc == 0
    assert "[check-class] identity unexecuted" in out
    assert "[check-class] content unexecuted" in out
    for executed in ("positional", "token", "path", "signed-url"):
        assert f"[check-class] {executed} executed" in out
    assert "unexecuted-check-classes: identity,content" in out
    assert "[warn]" not in out


def test_check_reports_partial_identity_and_executed_content(monkeypatch, capsys, tmp_path):
    # An account without user_id leaves the identity class partially executed;
    # a present local pairs file keeps the content class executed.
    # 缺 user_id 的账户使身份类仅部分执行；本地内容对文件存在则内容类为已执行。
    partial = tmp_path / "config.toml"
    partial.write_text(PARTIAL_CONFIG_TOML, encoding="utf-8")
    cfg.configure(partial)
    pairs_local = tmp_path / "scrub_pairs.local.json"
    pairs_local.write_text(json.dumps({
        "pairs": [["zz-unique-old-source", "示例替换值"]],
        "gate": ["zz-unique-gate-pattern"],
    }), encoding="utf-8")
    rc, out = _run_check(monkeypatch, capsys, pairs_local)
    assert rc == 0
    assert "[check-class] identity partial" in out
    assert "缺 user_id" in out
    assert "[check-class] content executed" in out
    assert "unexecuted-check-classes: identity" in out


def test_workflow_residue_steps_publish_unexecuted_classes():
    # Both CI residue steps must parse the machine-readable summary line and
    # append unexecuted classes to the step summary, while pipefail preserves
    # the existing failure behavior of the gate itself.
    # 两个 CI 残留步骤须解析机器可读汇总行并把未执行类追加进步骤摘要，
    # pipefail 保持门禁本身的失败行为不变。
    for relative in (
        ".github/workflows/quality.yml",
        ".github/workflows/translate-docs.yml",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "uv run python tests/scrub_fixtures.py --check | tee" in text
        assert "s/^unexecuted-check-classes: //p" in text
        assert '>> "${GITHUB_STEP_SUMMARY}"' in text
