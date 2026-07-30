"""N-11 regression: batch total semantics = actual iteration count + early-stop
tail segment (excluding dropped rows missing entryUUID).

Scenario: the index has 1 bad row missing entryUUID + 2 pending rows + 2
terminal-state early-stop tail rows.
Expected: progress [batch i/4], a final tally of ok=1 skip=2 fail=1 out of 4 total,
and ok+skip+fail == total.
Fully offline: adapter/writer/throttle are all stubs; no network access.

N-11 回归：batch total 口径 = 实际迭代数 + 早停尾段（不含缺 entryUUID 丢弃行）。

场景：索引含 1 条缺 entryUUID 坏行 + 2 条待处理 + 2 条终态早停尾段。
期望：进度 [batch i/4]、末尾「ok=1 skip=2 fail=1 / 共 4」，且 ok+skip+fail == total。
全离线：adapter/writer/throttle 均为 stub，不触网。
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from pplx_export.commands.batch_cmd import cmd_batch
from pplx_export.core.state import BatchState
from pplx_export.hooks.incremental import plan_incremental


class _NoopThrottle:
    """Stand-in for Throttle: never sleeps, only satisfies the interface.

    替代 Throttle：不睡眠，只满足接口。"""

    def delay(self):
        return 0.0

    def backoff(self, base=None):
        return 0.0

    def reset(self):
        pass


class _FakeConv:
    def __init__(self):
        self.export_via = None
        self.author = ""
        self.space = None
        self.assets = []


class _FakeAdapter:
    """u-fail raises a generic exception (takes the fail+backoff branch); all
    others export successfully.

    Since V5-01 batch passes idx_thread (the index row): the stub accepts and
    records it for assertions.

    u-fail 抛一般异常（走 fail+backoff 分支），其余导出成功。

    V5-01 起 batch 会传 idx_thread（索引行）：桩同步接收并记录，供断言。"""

    def __init__(self):
        self.seen_idx: dict = {}

    def get_thread(self, uuid, url=None, idx_thread=None):
        if uuid == "u-fail":
            raise RuntimeError("boom")
        self.seen_idx[uuid] = idx_thread
        return _FakeConv()

    def get_assets(self, conv, dest_dir=None):
        return []


class _FakeWriter:
    def thread_dir_for(self, conv):
        return Path("/nonexistent")

    def write_thread(self, conv, adapter=None):
        pass


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _fixture(out_root: Path):
    """Build the index and batch_state: 1 bad row + 2 pending + 2 terminal tail rows.

    构造索引与 batch_state：1 坏行 + 2 待处理 + 2 终态尾段。"""
    idx = out_root / "index"
    idx.mkdir(parents=True)
    threads = [
        # Bad row missing entryUUID (should be dropped with a warning, not counted in total)
        # 缺 entryUUID 的坏行（应被丢弃并 warning，不计入 total）
        {"title": "坏行缺UUID", "lastUpdated": "2026-07-04T00:00:00Z", "mode": "SEARCH"},
        {"entryUUID": "u-ok", "title": "新增", "lastUpdated": "2026-07-03T00:00:00Z", "mode": "SEARCH"},
        {"entryUUID": "u-fail", "title": "上次失败", "lastUpdated": "2026-07-02T00:00:00Z", "mode": "SEARCH"},
        {"entryUUID": "u-done", "title": "已导出", "lastUpdated": "2026-07-01T00:00:00Z", "mode": "SEARCH"},
        {"entryUUID": "u-exp", "title": "已过期", "lastUpdated": "2026-06-30T00:00:00Z", "mode": "SEARCH"},
    ]
    (idx / "library_acct.json").write_text(json.dumps({"threads": threads}))
    state = BatchState(idx / "batch_state.json")
    state.mark_error("u-fail", "2026-07-02T00:00:00Z", "上次失败", "boom")
    state.mark_ok("u-done", "2026-07-01T00:00:00Z", "已导出")
    state.mark_expired("u-exp", "2026-06-30T00:00:00Z", "已过期")
    state.save()
    return threads


def _run_batch(tmp_path):
    _fixture(tmp_path)
    handler = _LogCapture()
    logger = logging.getLogger("pplx_export.cli")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    adapter = _FakeAdapter()
    try:
        account = SimpleNamespace(username="acct", folder="Acct")
        cmd_batch(adapter, _FakeWriter(), account, tmp_path,
                  limit=None, mode_filter=None, force=False,
                  delay_min=0, delay_max=0, full=False, throttle=_NoopThrottle())
    finally:
        logger.removeHandler(handler)
    return handler.messages, adapter


def test_batch_total_excludes_dropped_and_matches_final_counts(tmp_path):
    msgs, adapter = _run_batch(tmp_path)

    # Bad row dropped with a warning
    # 坏行被 warning 丢弃
    assert any("缺 entryUUID" in m for m in msgs)
    # Progress total=4 (2 iterations + 2 early-stops), not len(threads)=5
    # 进度 total=4（2 迭代 + 2 早停），不是 len(threads)=5
    assert any("[batch 1/4]" in m for m in msgs)
    assert any("[batch 2/4]" in m for m in msgs)
    assert not any("/5]" in m for m in msgs)
    # Final summary reconciles with total: ok+skip+fail == total
    # 末尾汇总与 total 对账：ok+skip+fail == total
    final = [m for m in msgs if m.startswith("[batch] 完成。")]
    assert final and "ok=1 skip=2 fail=1 / 共 4" in final[0]
    # Early-stop rows are merged into skip
    # 早停行并入 skip
    assert any("增量早停" in m and "ok=1 skip=2 fail=1" in m for m in msgs)
    # V5-01: batch passes the index row as idx_thread to get_thread
    # V5-01：batch 把索引行作为 idx_thread 传给 get_thread
    assert adapter.seen_idx["u-ok"]["entryUUID"] == "u-ok"
    assert adapter.seen_idx["u-ok"]["lastUpdated"] == "2026-07-03T00:00:00Z"


def test_plan_invariant_actions_plus_stopped_equals_valid(tmp_path):
    """Pure counting logic: len(actions) + n_stopped == len(valid) (rows missing
    UUID never enter the plan).

    纯计数逻辑：len(actions) + n_stopped == len(valid)（缺 UUID 行不进计划）。"""
    threads = _fixture(tmp_path)
    state = BatchState(tmp_path / "index" / "batch_state.json")
    valid = [t for t in threads if t.get("entryUUID")]
    actions, n_stopped = plan_incremental(valid, state, full=False, force=False)
    assert len(actions) == 2          # u-ok new + u-fail updated
    # u-done + u-exp terminal tail segment
    # u-done + u-exp 终态尾段
    assert n_stopped == 2
    assert len(actions) + n_stopped == len(valid)


class _AllFailAdapter:
    """Every export raises a generic (non-auth) error → fail+backoff branch.

    每次导出都抛一般（非鉴权）错误 → 走 fail+退避分支。"""

    transport = object()

    def get_thread(self, uuid, url=None, idx_thread=None):
        raise RuntimeError("net boom")

    def get_assets(self, conv, dest_dir=None):
        return []


def _write_pending_lib(out_root: Path, n: int):
    idx = out_root / "index"
    idx.mkdir(parents=True)
    threads = [{"entryUUID": f"u{i}", "title": f"t{i}",
                "lastUpdated": f"2026-07-{i + 1:02d}T00:00:00Z", "mode": "SEARCH"}
               for i in range(n)]
    (idx / "library_acct.json").write_text(json.dumps({"threads": threads}))


def test_batch_deferred_check_aborts_on_auth_problem(tmp_path, monkeypatch):
    """--skip-auth-check path: after 3 generic failures the deferred account check
    runs once; a confirmed auth/account problem aborts the batch (no 空转).

    --skip-auth-check 路径：3 次通用失败后回退校验一次；确认鉴权/账户问题即中止。"""
    import pplx_export.commands.batch_cmd as bc

    _write_pending_lib(tmp_path, 3)
    calls: list[int] = []
    monkeypatch.setattr(bc, "report_account_status", lambda t, a: (calls.append(1) or True))
    account = SimpleNamespace(username="acct", folder="Acct")
    with pytest.raises(SystemExit):
        cmd_batch(_AllFailAdapter(), _FakeWriter(), account, tmp_path,
                  limit=None, mode_filter=None, force=False,
                  delay_min=0, delay_max=0, full=False, throttle=_NoopThrottle(),
                  verify_on_errors=True)
    assert calls == [1], "报错累积后应恰好回退校验一次"


def test_batch_deferred_check_continues_when_account_ok(tmp_path, monkeypatch):
    """When the deferred check says the account is fine (network/rate-limit), the
    batch runs to completion instead of aborting.

    回退校验判定账户正常（网络/限流）时，批量跑完而非中止。"""
    import pplx_export.commands.batch_cmd as bc

    _write_pending_lib(tmp_path, 4)
    calls: list[int] = []
    monkeypatch.setattr(bc, "report_account_status", lambda t, a: (calls.append(1) or False))
    account = SimpleNamespace(username="acct", folder="Acct")
    # Must not raise: a healthy account means the failures are transient.
    # 不应抛出：账户健康说明失败是瞬态的。
    cmd_batch(_AllFailAdapter(), _FakeWriter(), account, tmp_path,
              limit=None, mode_filter=None, force=False,
              delay_min=0, delay_max=0, full=False, throttle=_NoopThrottle(),
              verify_on_errors=True)
    assert calls == [1], "账户正常时也只回退校验一次，不重复"


def test_batch_no_deferred_check_without_verify_flag(tmp_path, monkeypatch):
    """Without verify_on_errors (no --skip-auth-check), the deferred check never runs.

    未开 verify_on_errors（无 --skip-auth-check）时，绝不触发回退校验。"""
    import pplx_export.commands.batch_cmd as bc

    _write_pending_lib(tmp_path, 4)
    calls: list[int] = []
    monkeypatch.setattr(bc, "report_account_status", lambda t, a: (calls.append(1) or True))
    account = SimpleNamespace(username="acct", folder="Acct")
    cmd_batch(_AllFailAdapter(), _FakeWriter(), account, tmp_path,
              limit=None, mode_filter=None, force=False,
              delay_min=0, delay_max=0, full=False, throttle=_NoopThrottle())
    assert calls == [], "未开 verify_on_errors 不应回退校验"
