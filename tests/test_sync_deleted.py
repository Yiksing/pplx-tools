"""sync-deleted regression tests: remote deletion detection + local archive tombstoning.

Covers:
  - Candidate detection: an ok thread gone from the union of **all**
    index/library_*.json account indexes becomes a candidate (any index still
    holding the uuid counts as alive — a cross-account export_via thread only
    appears in the owner account's index, so a single-account diff would
    false-positive); when every index is missing/unreadable, skip safely and
    record the reason faithfully; non-ok statuses (expired/error/deleted)
    produce no candidates.
  - Terminal semantics: deleted on par with expired — is_terminal is true,
    plan_incremental never re-exports (not even with --force), and early-stop
    may truncate the deleted tail.
  - Online confirmation: ENTRY_DELETED / ENTRY_EXPIRED / HTTP 404 → mark
    deleted + add remote_deleted in place in thread.json (idempotent: an
    existing key is not overwritten); thread still exists → false positive
    leaves state unchanged; consecutive auth failures abort fail-fast.
  - batch hitting EntryDeletedError → mark_deleted (isomorphic to the expired
    branch); export single-export hitting EntryDeletedError → graceful
    SystemExit + terminal registration, no traceback.
  - Offline dry-run by default: no network (the adapter factory must not be
    called), no files changed.

Fully offline: synthetic indexes/archives/fake adapters, no network access
(ENTRY_DELETED behavior synthesized from the live measurements in
docs/reports/2026-07-23-remote-delete/research.md).

sync-deleted 回归测试：远端删除识别 + 本地归档墓碑标记。

覆盖：
  - 候选检测：ok 线程在**所有** index/library_*.json 账户索引并集中均消失 → 候选
    （任一索引含该 uuid 即视为存活——跨账户 export_via 线程只出现在所有者账户
    索引里，单账户 diff 会误报）；全部索引缺失/不可读时安全跳过并如实记录原因；
    非 ok 状态（expired/error/deleted）不产生候选。
  - 终态语义：deleted 与 expired 并列——is_terminal 为真、plan_incremental
    不重导（--force 也不重导）、早停尾段可截掉 deleted。
  - 在线确认：ENTRY_DELETED / ENTRY_EXPIRED / HTTP 404 → 标记 deleted +
    thread.json 就地加 remote_deleted（幂等：已有该键不覆盖）；线程仍存在 →
    误报不改状态；连续鉴权失败 fail-fast。
  - batch 遇 EntryDeletedError → mark_deleted（与 expired 分支同构）；
    export 单导遇 EntryDeletedError → 优雅 SystemExit + 终态登记，不 traceback。
  - 默认离线 dry-run：不联网（适配器工厂不得被调用）、不改任何文件。

全离线：合成索引/归档/假适配器，不触网（ENTRY_DELETED 行为以
docs/reports/2026-07-23-remote-delete/research.md 实测为准做合成）。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pplx_export.commands.sync_deleted_cmd import (cmd_sync_deleted, find_candidates,
                                                   mark_thread_json_remote_deleted)
from pplx_export.core.errors import (AuthTransportError, EntryDeletedError,
                                     EntryExpiredError, TransportError)
from pplx_export.core.models import Account
from pplx_export.core.state import BatchState
from pplx_export.hooks.incremental import plan_incremental

ACCOUNT = Account(username="bob", display_name="bob")
# ok, gone from the indexes
# ok，索引中已消失
UUID_GONE = "11111111-2222-3333-4444-555555555555"
# ok, still present in the indexes
# ok，索引中仍在
UUID_LIVE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
# ok, exported via another account (shared space)
# ok，经他账户导出（共享空间）
UUID_XACCT = "bbbbbbbb-2222-3333-4444-555555555555"
# expired terminal state
# expired 终态
UUID_EXPIRED = "ffffffff-1111-2222-3333-444444444444"


def _write_state(root: Path, entries: dict) -> Path:
    idx = root / "index"
    idx.mkdir(parents=True, exist_ok=True)
    p = idx / "batch_state.json"
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=1))
    return p


def _ok(uuid: str, **kw) -> dict:
    st = {"status": "ok", "lastUpdated": "2026-07-20T00:00:00Z",
          "title": f"t-{uuid[:4]}", "exported_at": "2026-07-20T01:00:00Z"}
    st.update(kw)
    return st


def _write_index(root: Path, username: str, uuids: list[str]) -> Path:
    idx = root / "index"
    idx.mkdir(parents=True, exist_ok=True)
    rows = [{"entryUUID": u, "title": f"t-{u[:4]}",
             "lastUpdated": "2026-07-20T00:00:00Z"} for u in uuids]
    p = idx / f"library_{username}.json"
    p.write_text(json.dumps({"account": username, "count": len(rows),
                             "threads": rows}, ensure_ascii=False, indent=1))
    return p


def _archive_thread(root: Path, uuid: str, export_via: str,
                    folder: str = "bob", remote_deleted: str | None = None) -> Path:
    """Synthesize an archived thread directory (thread.json carries web_uuid
    equality verification + export_via).

    合成已归档线程目录（thread.json 含 web_uuid 全等核验 + export_via）。"""
    d = root / folder / "search" / f"2026-07-20_t_{uuid[:8]}"
    d.mkdir(parents=True)
    tj = {"web_uuid": uuid, "title": f"t-{uuid[:4]}", "export_via": export_via}
    if remote_deleted:
        tj["remote_deleted"] = remote_deleted
    (d / "thread.json").write_text(json.dumps(tj, ensure_ascii=False, indent=1))
    return d


def _read_state(root: Path) -> dict:
    return json.loads((root / "index" / "batch_state.json").read_text())


class _NoNetworkFactory:
    """Fail on any network attempt: proves the offline dry-run uses zero network.

    任何联网企图即失败：证明离线 dry-run 零网络。"""

    def __call__(self, username=None, throttle=None):  # pragma: no cover
        raise AssertionError("不应触网：离线 dry-run 不得构造适配器")


class _FakeFetcher:
    def __init__(self, payload_by_uuid: dict):
        self.payload_by_uuid = payload_by_uuid
        self.calls: list[str] = []

    def get_thread(self, uuid: str, max_pages: int = 20):
        self.calls.append(uuid)
        payload = self.payload_by_uuid[uuid]
        if isinstance(payload, Exception):
            raise payload
        return payload


class _FakeAdapter:
    def __init__(self, payload_by_uuid: dict):
        self.fetcher = _FakeFetcher(payload_by_uuid)


def _factory(payload_by_uuid: dict, calls: list | None = None):
    def factory(username=None, throttle=None):
        if calls is not None:
            calls.append(username)
        return _FakeAdapter(payload_by_uuid)
    return factory


class TestFindCandidates:
    def test_gone_from_index_is_candidate(self, tmp_path):
        """An ok thread gone from the exporting account's index → candidate;
        one still in the index is not.

        ok 线程在导出账户索引中消失 → 候选；仍在索引中的不是候选。"""
        _archive_thread(tmp_path, UUID_GONE, "bob")
        _archive_thread(tmp_path, UUID_LIVE, "bob")
        _write_state(tmp_path, {UUID_GONE: _ok(UUID_GONE), UUID_LIVE: _ok(UUID_LIVE)})
        # GONE has disappeared
        # GONE 已消失
        _write_index(tmp_path, "bob", [UUID_LIVE])
        candidates, skipped = find_candidates(tmp_path, "bob")
        assert [c["uuid"] for c in candidates] == [UUID_GONE]
        assert candidates[0]["account"] == "bob"
        # Carries the thread dirs for tombstone marking
        # 携线程目录供打标记
        assert candidates[0]["thread_dirs"]
        assert skipped == []

    def test_cross_account_export_via_alive_in_other_index(self, tmp_path):
        """A cross-account exported thread (export_via=A) absent from A's index
        but alive in B's index → not a candidate.

        Coordinator re-check measurement: a thread owned by account B and
        exported by A via a shared space never appears in A's index — liveness
        must be judged by the union of all account indexes (the old
        single-account diff produced 14 false candidates in testing).

        跨账户导出线程（export_via=A）不在 A 索引但在 B 索引中存活 → 非候选。

        协调方复核实测：账户 B 拥有、经共享空间由 A 导出的线程永远不会出现在
        A 的索引里——必须按全账户索引并集判定（旧单账户 diff 实测产生 14 条假候选）。
        """
        _archive_thread(tmp_path, UUID_XACCT, "alice", folder="bob")
        _write_state(tmp_path, {UUID_XACCT: _ok(UUID_XACCT)})
        # Not in A's index
        # A 的索引中没有
        _write_index(tmp_path, "alice", [])
        # But alive in B's index
        # 但在 B 的索引中存活
        _write_index(tmp_path, "bob", [UUID_XACCT])
        candidates, skipped = find_candidates(tmp_path, "bob")
        # Present in any index → considered alive
        # 任一索引含有即视为存活
        assert candidates == []
        assert skipped == []

    def test_gone_from_all_indexes_is_candidate(self, tmp_path):
        """A cross-account exported thread gone from all indexes → candidate;
        account is taken from export_via (for online verification).

        跨账户导出线程在所有索引中均消失 → 候选；account 取 export_via（供在线验证）。"""
        _archive_thread(tmp_path, UUID_XACCT, "alice", folder="bob")
        _write_state(tmp_path, {UUID_XACCT: _ok(UUID_XACCT)})
        _write_index(tmp_path, "alice", [])
        _write_index(tmp_path, "bob", [])
        candidates, skipped = find_candidates(tmp_path, "bob")
        assert [c["uuid"] for c in candidates] == [UUID_XACCT]
        # Online verification uses the export_via account
        # 在线验证用 export_via 账户
        assert candidates[0]["account"] == "alice"
        assert skipped == []

    def test_missing_index_safe_skip(self, tmp_path):
        """All account indexes missing/unreadable → skip safely with a hint to
        run index first; no candidates, no crash.

        全部账户索引缺失/不可读 → 安全跳过并提示先跑 index，不产候选、不崩。"""
        _archive_thread(tmp_path, UUID_GONE, "alice")
        _write_state(tmp_path, {UUID_GONE: _ok(UUID_GONE)})
        # Not a single library_*.json exists
        # 一个 library_*.json 都没有
        candidates, skipped = find_candidates(tmp_path, "bob")
        assert candidates == []
        assert len(skipped) == 1
        assert "先运行 index" in skipped[0]["reason"]

    def test_partial_index_still_diffs(self, tmp_path):
        """With only one account index available, diff against that union (no
        skip); a missing thread is a candidate.

        只有一个账户索引可用时按该并集 diff（不跳过）；线程缺失即候选。"""
        _archive_thread(tmp_path, UUID_GONE, "alice")
        _write_state(tmp_path, {UUID_GONE: _ok(UUID_GONE)})
        # The only available index, and the thread is not in it
        # 唯一可用索引，线程不在其中
        _write_index(tmp_path, "bob", [])
        candidates, skipped = find_candidates(tmp_path, "bob")
        assert [c["uuid"] for c in candidates] == [UUID_GONE]
        assert skipped == []

    def test_non_ok_status_not_candidates(self, tmp_path):
        """expired/error/already-deleted statuses produce no candidates.

        expired/error/已 deleted 的状态不产生候选。"""
        _write_state(tmp_path, {
            UUID_EXPIRED: {"status": "expired", "lastUpdated": "2026-01-01T00:00:00Z",
                           "title": "gone", "note": "ENTRY_EXPIRED"},
            UUID_GONE: {"status": "error", "lastUpdated": "2026-01-01T00:00:00Z",
                        "title": "err", "error": "boom"},
            UUID_LIVE: {"status": "deleted", "lastUpdated": "2026-01-01T00:00:00Z",
                        "title": "del", "note": "已确认"},
        })
        _write_index(tmp_path, "bob", [])
        candidates, skipped = find_candidates(tmp_path, "bob")
        assert candidates == []
        assert skipped == []


class TestTerminalSemantics:
    def test_is_terminal_includes_deleted(self, tmp_path):
        state = BatchState(tmp_path / "index" / "batch_state.json")
        state.mark_deleted(UUID_GONE, "2026-07-20T00:00:00Z", "t", "索引消失 + 404")
        assert state.is_deleted(UUID_GONE)
        assert state.is_terminal(UUID_GONE, "2026-07-20T00:00:00Z")
        # Terminal even when lastUpdated changed (same as expired, no retry)
        # lastUpdated 变了也是终态（与 expired 一致，不重试）
        assert state.is_terminal(UUID_GONE, "2026-07-21T00:00:00Z")
        st = state.get(UUID_GONE)
        assert st["status"] == "deleted" and st["note"] and st["deleted_at"]

    def test_plan_incremental_deleted_never_reexport(self, tmp_path):
        """deleted terminal state: truncated by default early-stop; --full
        marks each item deleted; --force does not re-export either.

        deleted 终态：默认早停截掉；--full 逐项标 deleted；--force 也不重导。"""
        state = BatchState(tmp_path / "index" / "batch_state.json")
        state.mark_deleted(UUID_GONE, "2026-07-20T00:00:00Z", "t")
        threads = [{"entryUUID": UUID_GONE, "lastUpdated": "2026-07-20T00:00:00Z"}]
        actions, n_stopped = plan_incremental(threads, state)
        # Early-stop truncates the deleted tail
        # 早停截掉 deleted 尾段
        assert actions == [] and n_stopped == 1
        actions, _ = plan_incremental(threads, state, full=True)
        assert actions[0][1] == "deleted"
        actions, _ = plan_incremental(threads, state, force=True)
        # --force does not re-export either
        # --force 也不重导
        assert actions[0][1] == "deleted"

    def test_plan_incremental_deleted_not_confused_with_updated(self, tmp_path):
        """A deleted thread must not be judged updated even when lastUpdated
        changes.

        deleted 线程 lastUpdated 变化也不得判为 updated。"""
        state = BatchState(tmp_path / "index" / "batch_state.json")
        state.mark_deleted(UUID_GONE, "2026-07-20T00:00:00Z", "t")
        threads = [{"entryUUID": UUID_GONE, "lastUpdated": "2026-07-22T00:00:00Z"}]
        actions, _ = plan_incremental(threads, state, full=True)
        assert actions[0][1] == "deleted"


class TestOfflineDryRun:
    def test_offline_lists_only_no_writes(self, tmp_path):
        """Offline by default: no network (the factory must not be called),
        no changes to batch_state, no changes to thread.json.

        默认离线：不联网（工厂不得被调用）、不改 batch_state、不改 thread.json。"""
        d = _archive_thread(tmp_path, UUID_GONE, "bob")
        _write_state(tmp_path, {UUID_GONE: _ok(UUID_GONE)})
        _write_index(tmp_path, "bob", [])
        state_before = (tmp_path / "index" / "batch_state.json").read_text()
        tj_before = (d / "thread.json").read_text()
        cmd_sync_deleted(_NoNetworkFactory(), ACCOUNT, tmp_path, online=False)
        assert (tmp_path / "index" / "batch_state.json").read_text() == state_before
        assert (d / "thread.json").read_text() == tj_before


class TestOnlineConfirm:
    def _setup(self, tmp_path):
        d = _archive_thread(tmp_path, UUID_GONE, "bob")
        _write_state(tmp_path, {UUID_GONE: _ok(UUID_GONE)})
        _write_index(tmp_path, "bob", [])
        return d

    def test_entry_deleted_confirms_deleted(self, tmp_path):
        """ENTRY_DELETED (measured in research: after deletion GET thread
        returns 400 ENTRY_DELETED) → confirmed.

        ENTRY_DELETED（调研实测：删除后 GET thread 返回 400 ENTRY_DELETED）→ 确认。"""
        d = self._setup(tmp_path)
        cmd_sync_deleted(_factory({UUID_GONE: EntryDeletedError(
            'HTTP 400: {"error":"ENTRY_DELETED","message":"This entry has been deleted"}')}),
            ACCOUNT, tmp_path, online=True, delay_min=0, delay_max=0)
        st = _read_state(tmp_path)[UUID_GONE]
        assert st["status"] == "deleted"
        assert "ENTRY_DELETED" in st["note"]
        assert json.loads((d / "thread.json").read_text())["remote_deleted"]

    def test_entry_expired_confirms_deleted(self, tmp_path):
        """ENTRY_EXPIRED → confirmed: batch_state marked deleted (note records
        the reason) + thread.json tombstoned.

        ENTRY_EXPIRED → 确认：batch_state 标记 deleted（note 记原因）+ thread.json 打标。"""
        d = self._setup(tmp_path)
        calls = []
        cmd_sync_deleted(_factory({UUID_GONE: EntryExpiredError("ENTRY_EXPIRED")}, calls),
                         ACCOUNT, tmp_path, online=True, delay_min=0, delay_max=0)
        # Adapter built for the exporting account
        # 按导出账户构造适配器
        assert calls == ["bob"]
        st = _read_state(tmp_path)[UUID_GONE]
        assert st["status"] == "deleted"
        assert "ENTRY_EXPIRED" in st["note"]
        assert st["deleted_at"]
        tj = json.loads((d / "thread.json").read_text())
        # Tombstone marker written
        # 墓碑标记已写入
        assert tj["remote_deleted"]
        # Other fields left as-is
        # 其余字段原样
        assert tj["web_uuid"] == UUID_GONE

    def test_http_404_confirms_deleted(self, tmp_path):
        """HTTP 404 (TransportError) → likewise confirms deletion.

        HTTP 404（TransportError）→ 同样确认删除。"""
        d = self._setup(tmp_path)
        cmd_sync_deleted(_factory({UUID_GONE: TransportError("HTTP 404: b'not found'")}),
                         ACCOUNT, tmp_path, online=True, delay_min=0, delay_max=0)
        st = _read_state(tmp_path)[UUID_GONE]
        assert st["status"] == "deleted" and "404" in st["note"]
        assert json.loads((d / "thread.json").read_text())["remote_deleted"]

    def test_remote_deleted_mark_idempotent(self, tmp_path):
        """thread.json already has remote_deleted: do not overwrite the
        original timestamp, do not rewrite.

        thread.json 已有 remote_deleted：不覆盖原时间、不重复写。"""
        d = _archive_thread(tmp_path, UUID_GONE, "bob",
                            remote_deleted="2026-01-01T00:00:00Z")
        _write_state(tmp_path, {UUID_GONE: _ok(UUID_GONE)})
        _write_index(tmp_path, "bob", [])
        cmd_sync_deleted(_factory({UUID_GONE: EntryExpiredError("ENTRY_EXPIRED")}),
                         ACCOUNT, tmp_path, online=True, delay_min=0, delay_max=0)
        tj = json.loads((d / "thread.json").read_text())
        # Original value preserved
        # 原值保留
        assert tj["remote_deleted"] == "2026-01-01T00:00:00Z"

    def test_confirmed_thread_not_candidate_next_run(self, tmp_path):
        """State becomes deleted after confirmation: reruns no longer produce
        it as a candidate (idempotent resumption).

        确认后状态变为 deleted：重跑不再成为候选（幂等续跑）。"""
        self._setup(tmp_path)
        cmd_sync_deleted(_factory({UUID_GONE: EntryExpiredError("ENTRY_EXPIRED")}),
                         ACCOUNT, tmp_path, online=True, delay_min=0, delay_max=0)
        candidates, _ = find_candidates(tmp_path, "bob")
        assert candidates == []

    def test_false_positive_thread_still_exists(self, tmp_path, caplog):
        """Thread still exists → false positive: no batch_state change, no
        thread.json mark, reported faithfully.

        线程仍存在 → 误报：不改 batch_state、不打 thread.json 标记，如实报告。"""
        d = self._setup(tmp_path)
        payload = {"metadata": {}, "background_entries": [], "entries": []}
        cmd_sync_deleted(_factory({UUID_GONE: payload}),
                         ACCOUNT, tmp_path, online=True, delay_min=0, delay_max=0)
        # State untouched
        # 状态不动
        assert _read_state(tmp_path)[UUID_GONE]["status"] == "ok"
        assert "remote_deleted" not in json.loads((d / "thread.json").read_text())
        assert any("误报" in r.message for r in caplog.records)

    def test_transient_error_keeps_state(self, tmp_path):
        """5xx/network-type transport errors: leave state unchanged for the
        next round.

        5xx/网络类传输错误：不改状态，留待下轮。"""
        d = self._setup(tmp_path)
        cmd_sync_deleted(_factory({UUID_GONE: TransportError("HTTP 504: timeout")}),
                         ACCOUNT, tmp_path, online=True, delay_min=0, delay_max=0)
        assert _read_state(tmp_path)[UUID_GONE]["status"] == "ok"
        assert "remote_deleted" not in json.loads((d / "thread.json").read_text())

    def test_auth_fail_fast(self, tmp_path):
        """Consecutive auth failures (401/403) reaching the limit → fail-fast
        abort, no thread mis-marked.

        连续鉴权失败（401/403）达上限 → fail-fast 中止，不误标任何线程。"""
        _archive_thread(tmp_path, UUID_GONE, "bob")
        _archive_thread(tmp_path, UUID_LIVE, "bob")
        _archive_thread(tmp_path, UUID_XACCT, "bob")
        _write_state(tmp_path, {u: _ok(u) for u in (UUID_GONE, UUID_LIVE, UUID_XACCT)})
        # All three are candidates
        # 三个都是候选
        _write_index(tmp_path, "bob", [])
        payload = {u: AuthTransportError("鉴权失败 401")
                   for u in (UUID_GONE, UUID_LIVE, UUID_XACCT)}
        with pytest.raises(SystemExit):
            cmd_sync_deleted(_factory(payload), ACCOUNT, tmp_path,
                             online=True, delay_min=0, delay_max=0)
        st = _read_state(tmp_path)
        assert all(st[u]["status"] == "ok" for u in (UUID_GONE, UUID_LIVE, UUID_XACCT))

    def test_limit(self, tmp_path):
        """--limit processes only the first N candidates.

        --limit 只处理前 N 条候选。"""
        _archive_thread(tmp_path, UUID_GONE, "bob")
        _archive_thread(tmp_path, UUID_LIVE, "bob")
        _write_state(tmp_path, {UUID_GONE: _ok(UUID_GONE, lastUpdated="2026-07-20T00:00:00Z"),
                                UUID_LIVE: _ok(UUID_LIVE, lastUpdated="2026-07-21T00:00:00Z")})
        _write_index(tmp_path, "bob", [])
        fetcher_payload = {UUID_GONE: EntryExpiredError("ENTRY_EXPIRED"),
                           UUID_LIVE: EntryExpiredError("ENTRY_EXPIRED")}
        adapter = _FakeAdapter(fetcher_payload)
        cmd_sync_deleted(lambda username=None, throttle=None: adapter,
                         ACCOUNT, tmp_path, online=True, limit=1, delay_min=0, delay_max=0)
        # Sorted by lastUpdated descending; only UUID_LIVE (the newer one) is verified
        # 按 lastUpdated 降序，只验证 UUID_LIVE（较新者）
        assert adapter.fetcher.calls == [UUID_LIVE]
        st = _read_state(tmp_path)
        assert st[UUID_LIVE]["status"] == "deleted"
        assert st[UUID_GONE]["status"] == "ok"


class TestMarkThreadJson:
    def test_marks_all_dirs_and_skips_missing(self, tmp_path):
        """All directories (one per account, cross-account) get marked;
        directories missing thread.json are skipped safely.

        多目录（跨账户各一份）全部打标；thread.json 缺失的目录安全跳过。"""
        d1 = _archive_thread(tmp_path, UUID_GONE, "bob", folder="bob")
        d2 = _archive_thread(tmp_path, UUID_GONE, "alice", folder="Alice Example")
        d3 = tmp_path / "bob" / "search" / f"2026-07-19_old_{UUID_GONE[:8]}"
        # No thread.json: skipped without crashing
        # 无 thread.json：跳过不崩
        d3.mkdir(parents=True)
        n = mark_thread_json_remote_deleted([d1, d2, d3], "2026-07-22T00:00:00Z")
        assert n == 2
        for d in (d1, d2):
            assert json.loads((d / "thread.json").read_text())["remote_deleted"] == \
                "2026-07-22T00:00:00Z"
        # Idempotent: a second run writes nothing
        # 幂等：再跑一次零写盘
        assert mark_thread_json_remote_deleted([d1, d2], "2026-07-23T00:00:00Z") == 0
        assert json.loads((d1 / "thread.json").read_text())["remote_deleted"] == \
            "2026-07-22T00:00:00Z"


class _NoopThrottle:
    """Stand-in for Throttle: never sleeps, just satisfies the interface
    (same pattern as test_fix_n11).

    替代 Throttle：不睡眠，只满足接口（同 test_fix_n11 模式）。"""

    def delay(self):
        return 0.0

    def backoff(self, base=None):
        return 0.0

    def reset(self):
        pass


class TestBatchEntryDeleted:
    """batch hitting EntryDeletedError → mark_deleted (isomorphic to the
    expired branch, classified as deleted).

    batch 遇 EntryDeletedError → mark_deleted（与 expired 分支同构，分类为 deleted）。"""

    def _fixture(self, tmp_path: Path) -> None:
        idx = tmp_path / "index"
        idx.mkdir(parents=True)
        threads = [
            {"entryUUID": UUID_GONE, "title": "被远端删除", "mode": "SEARCH",
             "lastUpdated": "2026-07-20T00:00:00Z"},
        ]
        (idx / "library_acct.json").write_text(json.dumps({"threads": threads}))

    def test_batch_marks_deleted_on_entry_deleted(self, tmp_path):
        from pplx_export.commands.batch_cmd import cmd_batch

        self._fixture(tmp_path)

        class _A:
            def get_thread(self, uuid, url=None, idx_thread=None):
                raise EntryDeletedError('HTTP 400: {"error":"ENTRY_DELETED"}')

            # Never reached
            # 不会到达
            def get_assets(self, conv, dest_dir=None):  # pragma: no cover
                return []

        class _W:
            # Never reached
            # 不会到达
            def thread_dir_for(self, conv):  # pragma: no cover
                return Path("/nonexistent")

            def write_thread(self, conv, adapter=None):  # pragma: no cover
                pass

        account = SimpleNamespace(username="acct", folder="Acct")
        cmd_batch(_A(), _W(), account, tmp_path, limit=None, mode_filter=None,
                  force=False, delay_min=0, delay_max=0, full=False,
                  throttle=_NoopThrottle())
        st = _read_state(tmp_path)[UUID_GONE]
        # Not expired: precise classification
        # 不是 expired：分类精确
        assert st["status"] == "deleted"
        assert "ENTRY_DELETED" in st["note"]
        assert st["deleted_at"]

    def test_batch_deleted_terminal_skipped_next_run(self, tmp_path):
        """Once marked deleted, the next batch run skips it directly (no
        retry, no re-export even with --force).

        标记 deleted 后下轮 batch 直接跳过（不重试，--force 也不重导）。"""
        from pplx_export.commands.batch_cmd import cmd_batch

        self._fixture(tmp_path)
        state = BatchState(tmp_path / "index" / "batch_state.json")
        state.mark_deleted(UUID_GONE, "2026-07-20T00:00:00Z", "被远端删除",
                           "ENTRY_DELETED（用户/远端已删除，不可恢复）")
        state.save()

        class _A:
            def get_thread(self, uuid, url=None, idx_thread=None):  # pragma: no cover
                raise AssertionError("终态线程不得再请求")

        class _W:
            def thread_dir_for(self, conv):  # pragma: no cover
                return Path("/nonexistent")

        account = SimpleNamespace(username="acct", folder="Acct")
        # --force does not re-export the deleted terminal state either
        # --force 也不重导 deleted 终态
        cmd_batch(_A(), _W(), account, tmp_path, limit=None, mode_filter=None,
                  force=True, delay_min=0, delay_max=0, full=False,
                  throttle=_NoopThrottle())
        assert _read_state(tmp_path)[UUID_GONE]["status"] == "deleted"


class TestExportEntryDeleted:
    """export single-export hitting EntryDeletedError: graceful SystemExit +
    terminal registration, no traceback.

    export 单导遇 EntryDeletedError：优雅 SystemExit + 终态登记，不 traceback。"""

    def test_export_graceful_on_entry_deleted(self, tmp_path):
        from pplx_export.commands.export_cmd import cmd_export
        from pplx_export.sites.perplexity.fs_writer import FilesystemWriter

        class _A:
            def get_thread(self, uuid, url=None, idx_thread=None):
                raise EntryDeletedError('HTTP 400: {"error":"ENTRY_DELETED"}')

        account = SimpleNamespace(username="acct", folder="Acct")
        with pytest.raises(SystemExit) as exc_info:
            cmd_export(_A(), FilesystemWriter(tmp_path), UUID_GONE, account,
                       False, tmp_path)
        assert "ENTRY_DELETED" in str(exc_info.value)
        assert "已被用户/远端删除" in str(exc_info.value)
        st = _read_state(tmp_path)[UUID_GONE]
        assert st["status"] == "deleted"
        assert "ENTRY_DELETED" in st["note"]

    def test_export_graceful_on_entry_expired(self, tmp_path):
        """Symmetric path: ENTRY_EXPIRED also exits gracefully and registers
        expired (no traceback).

        对称路径：ENTRY_EXPIRED 也优雅退出并登记 expired（不 traceback）。"""
        from pplx_export.commands.export_cmd import cmd_export
        from pplx_export.sites.perplexity.fs_writer import FilesystemWriter

        class _A:
            def get_thread(self, uuid, url=None, idx_thread=None):
                raise EntryExpiredError('HTTP 400: {"error":"ENTRY_EXPIRED"}')

        account = SimpleNamespace(username="acct", folder="Acct")
        with pytest.raises(SystemExit) as exc_info:
            cmd_export(_A(), FilesystemWriter(tmp_path), UUID_GONE, account,
                       False, tmp_path)
        assert "ENTRY_EXPIRED" in str(exc_info.value)
        assert _read_state(tmp_path)[UUID_GONE]["status"] == "expired"


class TestEntryDeletedHierarchy:
    """EntryDeletedError exception hierarchy: inherits the fallback semantics
    of EntryExpiredError.

    EntryDeletedError 异常层次：继承 EntryExpiredError 的兜底语义。"""

    def test_is_subclass_of_entry_expired(self):
        """Existing except EntryExpiredError paths unaware of ENTRY_DELETED
        fall back to terminal state, never landing in "transient error retried
        forever".

        未感知 ENTRY_DELETED 的既有 except EntryExpiredError 路径兜底为终态，
        绝不落入「瞬态错误永久重试」。"""
        assert issubclass(EntryDeletedError, EntryExpiredError)
        err = EntryDeletedError("x")
        assert isinstance(err, EntryExpiredError)

    def test_distinguishable_from_expired(self):
        """Aware paths can distinguish precisely (except EntryDeletedError
        comes before EntryExpiredError).

        感知路径可精确区分（except EntryDeletedError 先于 EntryExpiredError）。"""
        err = EntryDeletedError("x")
        caught = "deleted" if isinstance(err, EntryDeletedError) else "expired"
        assert caught == "deleted"
        assert not isinstance(EntryExpiredError("x"), EntryDeletedError)
