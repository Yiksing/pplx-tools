"""Shared pytest fixtures: copy raw JSON from fixtures/ and re-render offline (zero network).

pytest 公共 fixture：从 fixtures/ 复制原始 JSON 并离线重渲（零网络）。"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

RAW_FILES = ("raw_entries.json", "raw_blocks.json", "thread.json")

# Placeholder user-level config (aligned with config.example.toml): tests never
# depend on a real ~/.config.
# 占位符用户级配置（与 config.example.toml 对齐）：测试绝不依赖真实 ~/.config。
PLACEHOLDER_CONFIG_TOML = """\
default_account = "alice"

[accounts.alice]
display_name = "Alice Example"
email = "alice@example.com"
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
"""

# Establish a process-local config before pytest imports any production module.
# This prevents collection from consulting PPLX_EXPORT_CONFIG inherited from the
# developer's shell or the real default config path.
# 在 pytest 导入任何生产模块前建立进程级占位配置，避免收集阶段读取开发者环境。
_SESSION_CONFIG_DIRECTORY = tempfile.TemporaryDirectory(
    prefix="pplx-tools-pytest-config-"
)
SESSION_CONFIG_PATH = Path(_SESSION_CONFIG_DIRECTORY.name) / "config.toml"
SESSION_CONFIG_PATH.write_text(PLACEHOLDER_CONFIG_TOML, encoding="utf-8")
os.environ["PPLX_EXPORT_CONFIG"] = str(SESSION_CONFIG_PATH)

from pplx_export.commands.rerender_cmd import rerender  # noqa: E402


@pytest.fixture(autouse=True)
def _placeholder_user_config(tmp_path):
    """Load a per-test placeholder, then restore the session placeholder.

    加载逐测试占位配置，结束后恢复进程级占位配置。"""
    from pplx_export import config as cfg

    p = tmp_path / "config.toml"
    p.write_text(PLACEHOLDER_CONFIG_TOML, encoding="utf-8")
    cfg.configure(p)
    yield
    cfg.configure(SESSION_CONFIG_PATH)


def render_fixture(name: str, dst: Path) -> Path:
    """Copy the raw JSON of fixtures/<name> into dst and re-render offline;
    return the thread directory.

    把 fixtures/<name> 的原始 JSON 复制到 dst 并离线重渲，返回线程目录。"""
    src = FIXTURES / name
    work = dst / name
    work.mkdir()
    for f in RAW_FILES:
        if (src / f).exists():
            shutil.copy2(src / f, work / f)
    assert rerender(work), f"rerender 失败: {name}"
    return work


@pytest.fixture()
def rendered(tmp_path):
    """Factory: rendered('search_demo') → (re-rendered thread dir, golden dir in fixtures).

    工厂：rendered('search_demo') → (重渲后的线程目录, fixtures 里的 golden 目录)。"""
    def _make(name: str):
        return render_fixture(name, tmp_path), FIXTURES / name / "golden"
    return _make
