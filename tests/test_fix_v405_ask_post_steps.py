"""V4-05 regression: after ask completes, failures of non-core steps
(move-to-BOT / read receipt / view telemetry) must not block auto-archiving.

Scenario: after SSE reaches COMPLETED, each of move / mark-read / telemetry /
export is mocked individually.
Expected:
- telemetry raises → export still runs; telemetry=False in the JSON and
  step_errors records the details;
- move raises → mark-read / telemetry / export still run;
- export raises → the exception propagates faithfully, not swallowed;
- the JSON contract stays backward-compatible: step keys are always booleans
  (true = executed and succeeded, false = not executed or failed); failures
  are never represented by truthy structures (protecting boolean consumers
  from misreading success); failure details live separately in step_errors.
Fully offline: sse_ask and all step functions are replaced via monkeypatch.

V4-05 回归：ask 完成后非核心步骤（移入 BOT/已读回执/阅读遥测）失败不阻断自动归档。

场景：SSE 已达 COMPLETED 后，逐项 mock 移动/已读/遥测/导出。
期望：
- 遥测抛错 → 导出仍执行，JSON 中 telemetry=False 且 step_errors 记录详情；
- 移动抛错 → 已读/遥测/导出仍执行；
- 导出抛错 → 异常如实向上抛出，不被吞；
- JSON 契约向后兼容：步骤键恒为布尔（true=执行且成功，false=未执行或失败），
  失败绝不用 truthy 结构表示（防布尔消费方误判成功）；失败详情单列 step_errors。
全离线：sse_ask/各步骤函数均经 monkeypatch 替换，不触网。
"""

import json
from types import SimpleNamespace

import pytest

import pplx_export.ask_cli as ask_cli


class _Recorder:
    """Call-order recording stub: optionally raises to simulate step failure.

    记录调用顺序的桩：可选抛错模拟步骤失败。"""

    def __init__(self, calls: list, name: str, error: Exception | None = None):
        self.calls = calls
        self.name = name
        self.error = error

    def __call__(self, *args, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(self.name)
        return {"status": "success"}


def _patch_common(monkeypatch, calls: list, *, fail_move=False, fail_mark=False,
                  fail_telemetry=False, fail_export=False):
    """Replace every external step cmd_ask depends on; return (args, account).

    替换 cmd_ask 依赖的全部外部步骤；返回 (args, account)。"""
    # SSE returns the COMPLETED terminal state directly (no streaming)
    # SSE 直接返回 COMPLETED 终态（不走流）
    monkeypatch.setattr(ask_cli, "sse_ask",
                        lambda *a, **k: {"backend_uuid": "uu-1", "context_uuid": "ctx-1",
                                         "status": "COMPLETED"})
    monkeypatch.setattr(ask_cli, "move_threads",
                        _Recorder(calls, "move", RuntimeError("boom-move") if fail_move else None))
    monkeypatch.setattr(ask_cli, "mark_read",
                        _Recorder(calls, "mark", RuntimeError("boom-mark") if fail_mark else None))
    monkeypatch.setattr(ask_cli, "send_view_telemetry",
                        _Recorder(calls, "telemetry",
                                  RuntimeError("boom-telemetry") if fail_telemetry else None))

    def _export(adapter, writer, uuid, account, force, out_root):
        if fail_export:
            raise RuntimeError("boom-export")
        calls.append("export")
    monkeypatch.setattr(ask_cli, "cmd_export", _export)

    args = SimpleNamespace(space="home", prompt="测试提问", mode="search", models=None,
                           mark_read=True, no_telemetry=False, no_export=False, timeout=1)
    return args, SimpleNamespace(username="acct")


def _run(capsys, tmp_path, args, account):
    ask_cli.cmd_ask(args, account, transport=object(), writer=object(), out_root=tmp_path)
    out = capsys.readouterr().out.strip().splitlines()
    return json.loads(out[-1])


def test_telemetry_failure_does_not_block_export(monkeypatch, capsys, tmp_path):
    calls: list = []
    args, account = _patch_common(monkeypatch, calls, fail_telemetry=True)
    result = _run(capsys, tmp_path, args, account)
    assert calls == ["move", "mark", "export"]
    # Telemetry failed but export still ran
    # Boolean contract: failure is False (falsy, not misread as success)
    # 遥测失败但导出仍执行
    # 布尔契约：失败为 False（falsy，不误判成功）
    assert result["telemetry"] is False
    assert "boom-telemetry" in result["step_errors"]["telemetry"]
    assert result["moved_to_bot"] is True
    assert result["mark_read"] is True
    assert result["exported"] is not None


def test_move_failure_does_not_block_mark_telemetry_export(monkeypatch, capsys, tmp_path):
    calls: list = []
    args, account = _patch_common(monkeypatch, calls, fail_move=True)
    result = _run(capsys, tmp_path, args, account)
    # Move failed; the later steps ran as usual
    # 移动失败，后续步骤照常
    assert calls == ["mark", "telemetry", "export"]
    assert result["moved_to_bot"] is False
    assert "boom-move" in result["step_errors"]["moved_to_bot"]
    assert result["mark_read"] is True
    assert result["telemetry"] is True
    assert result["exported"] is not None


def test_export_failure_propagates_not_swallowed(monkeypatch, capsys, tmp_path):
    calls: list = []
    args, account = _patch_common(monkeypatch, calls, fail_export=True)
    with pytest.raises(RuntimeError, match="boom-export"):
        ask_cli.cmd_ask(args, account, transport=object(), writer=object(), out_root=tmp_path)
    # The pre-export non-core steps all ran; the exception is not swallowed
    # 导出前的非核心步骤均已执行，异常不被吞
    assert calls == ["move", "mark", "telemetry"]


def test_all_success_json_reports_each_step(monkeypatch, capsys, tmp_path):
    calls: list = []
    args, account = _patch_common(monkeypatch, calls)
    result = _run(capsys, tmp_path, args, account)
    assert calls == ["move", "mark", "telemetry", "export"]
    assert result["thread_uuid"] == "uu-1"
    assert result["thread_url"] == "https://www.perplexity.ai/search/uu-1"
    assert result["context_uuid"] == "ctx-1"
    assert result["moved_to_bot"] is True
    assert result["mark_read"] is True
    assert result["telemetry"] is True
    assert result["step_errors"] == {}
    assert result["exported"] is not None


def test_unrequested_steps_report_false(monkeypatch, capsys, tmp_path):
    """Unrequested mark-read / telemetry (--mark-read not given,
    --no-telemetry) report False in the JSON (consistent with the old boolean
    contract `true only when executed`), are absent from step_errors, and send
    no requests.

    未请求的已读/遥测（--mark-read 未给、--no-telemetry）在 JSON 中为 False（与旧布尔契约
    `执行才为 true` 一致），不进 step_errors，且不发请求。"""
    calls: list = []
    args, account = _patch_common(monkeypatch, calls)
    args.mark_read = False
    args.no_telemetry = True
    result = _run(capsys, tmp_path, args, account)
    assert calls == ["move", "export"]
    assert result["moved_to_bot"] is True
    assert result["mark_read"] is False
    assert result["telemetry"] is False
    assert result["step_errors"] == {}
