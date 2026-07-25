"""Regression tests for search_mode enrichment (risk item 1 fix).

Background: library index rows lack the platform-authoritative mode signal
search_mode (measured 0 coverage across all 578 library rows), so `batch --mode`
can only rely on the mode/displayModel heuristic — in practice one study thread
(displayModel=pplx_beta) was missed by --mode study.
Fix:
  1. New search-mode-backfill subcommand: local-first (extracted from
     raw_entries.json, zero network), online fallback (GET /rest/thread/<uuid>),
     expired-terminal skip, idempotent and resumable; writes the search_mode key
     back into index rows (platform raw value, aggregated per thread by
     specificity).
  2. cmd_index refresh merges and preserves search_mode enrichment from the old
     index by entryUUID.
  3. batch --mode filter: with search_mode present, the SEARCH_MODE_MAP
     authoritative mapping is used; when missing, falls back to the old
     displayModel/mode heuristic (behavior unchanged).

Fully offline: synthetic index/archives/fake adapters, no network access.

search_mode 富化回归测试（风险点 1 修复）。

背景：library 索引行不含平台权威模式信号 search_mode（实测全库 578 行 0 覆盖），
`batch --mode` 只能靠 mode/displayModel 启发式——实测 1 个 study 线程
（displayModel=pplx_beta）被 --mode study 漏掉。
修复：
  1. 新子命令 search-mode-backfill：本地优先（raw_entries.json 提取，零网络）、
     联网兜底（GET /rest/thread/<uuid>）、expired 终态跳过、幂等可续跑，
     索引行写回 search_mode 键（平台原始值，线程级按特异性聚合）。
  2. cmd_index 刷新时按 entryUUID 从旧索引合并保留 search_mode 富化。
  3. batch --mode 过滤：有 search_mode 走 SEARCH_MODE_MAP 权威映射，
     缺失回落旧 displayModel/mode 启发式（行为不变）。

全离线：合成索引/归档/假适配器，不触网。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from pplx_export.commands.batch_cmd import index_row_matches_mode
from pplx_export.commands.index_cmd import cmd_index
from pplx_export.commands.search_mode_backfill_cmd import cmd_search_mode_backfill
from pplx_export.core.errors import EntryExpiredError
from pplx_export.core.models import Account
from pplx_export.sites.perplexity.normalize import aggregate_search_mode

ACCOUNT = Account(username="bob", display_name="bob")
UUID_LOCAL = "11111111-2222-3333-4444-555555555555"
UUID_ONLINE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
UUID_EXPIRED = "ffffffff-1111-2222-3333-444444444444"


def _write_index(root: Path, rows: list[dict]) -> Path:
    idx = root / "index"
    idx.mkdir(parents=True, exist_ok=True)
    p = idx / f"library_{ACCOUNT.username}.json"
    p.write_text(json.dumps({"account": ACCOUNT.username, "count": len(rows),
                             "threads": rows}, ensure_ascii=False, indent=1))
    return p


def _row(uuid: str, **kw) -> dict:
    t = {"title": f"t-{uuid[:4]}", "entryUUID": uuid, "mode": "SEARCH",
         "displayModel": "pplx_pro", "lastUpdated": "2026-07-20T00:00:00Z",
         "status": "COMPLETED", "space": None}
    t.update(kw)
    return t


def _archive_thread(root: Path, uuid: str, search_modes: list[str | None]) -> Path:
    """Synthesize an archived thread directory: thread.json (web_uuid exact-match check) + raw_entries.json.

    合成已归档线程目录：thread.json（web_uuid 全等核验）+ raw_entries.json。"""
    d = root / "bob" / "search" / f"2026-07-20_t_{uuid[:8]}"
    d.mkdir(parents=True)
    (d / "thread.json").write_text(json.dumps({"web_uuid": uuid, "title": "t"}))
    (d / "raw_entries.json").write_text(json.dumps(
        {"thread_metadata": {}, "background_entries": [],
         "entries": [{"search_mode": sm} for sm in search_modes]}))
    return d


def _load_rows(p: Path) -> list[dict]:
    return json.loads(p.read_text())["threads"]


class _NoNetworkFactory:
    """Fail on any network attempt: proves the local path uses zero network.

    任何联网企图即失败：证明本地路径零网络。"""

    # Being called means test failure
    # 被调用即测试失败
    def __call__(self, throttle=None):  # pragma: no cover
        raise AssertionError("不应触网：本地可解/expired 跳过的行不得构造适配器")


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


class TestAggregateSearchMode:
    def test_specificity_wins(self):
        entries = [{"search_mode": "SEARCH"}, {"search_mode": "STUDY"}]
        assert aggregate_search_mode(entries) == "STUDY"
        entries = [{"search_mode": "RESEARCH"}, {"search_mode": "SEARCH"}]
        assert aggregate_search_mode(entries) == "RESEARCH"
        entries = [{"search_mode": "SEARCH"}, {"search_mode": "AGENTIC_RESEARCH"},
                   {"search_mode": "RESEARCH"}]
        assert aggregate_search_mode(entries) == "AGENTIC_RESEARCH"
        entries = [{"search_mode": "STUDY"}, {"search_mode": "ASI"}]
        assert aggregate_search_mode(entries) == "ASI"

    def test_raw_value_preserved(self):
        # STUDIO maps to search, but the written-back value is the platform raw value
        # STUDIO 映射为 search，但写回的是平台原始值
        assert aggregate_search_mode([{"search_mode": "STUDIO"}]) == "STUDIO"

    def test_unknown_and_missing_ignored(self):
        assert aggregate_search_mode([{"search_mode": "FUTURE_MODE"},
                                      {"search_mode": None}, {}]) == ""
        assert aggregate_search_mode(None) == ""
        assert aggregate_search_mode([]) == ""
        # Unknown values do not block: a later known value still hits
        # 未知值不挡路：后面已知值仍命中
        assert aggregate_search_mode([{"search_mode": "FUTURE_MODE"},
                                      {"search_mode": "SEARCH"}]) == "SEARCH"

    def test_non_dict_entries_skipped(self):
        assert aggregate_search_mode([None, "x", {"search_mode": "SEARCH"}]) == "SEARCH"


class TestSearchModeBackfill:
    def test_local_only_zero_network(self, tmp_path):
        """All archived threads resolved locally: the adapter factory must not be called (zero network).

        已归档线程全部本地解决：适配器工厂不得被调用（零网络）。"""
        _archive_thread(tmp_path, UUID_LOCAL, ["SEARCH", "STUDY"])
        p = _write_index(tmp_path, [_row(UUID_LOCAL), _row(UUID_ONLINE,
                                                         displayModel="pplx_beta")])
        # UUID_ONLINE has no local archive; with --offline it waits for the next round (still no network)
        # UUID_ONLINE 无本地归档，--offline 时留待下轮（也不触网）
        cmd_search_mode_backfill(_NoNetworkFactory(), ACCOUNT, tmp_path,
                                 online=False)
        rows = _load_rows(p)
        by_uuid = {t["entryUUID"]: t for t in rows}
        # Specificity aggregation
        # 特异性聚合
        assert by_uuid[UUID_LOCAL]["search_mode"] == "STUDY"
        assert "search_mode" not in by_uuid[UUID_ONLINE]

    def test_expired_terminal_skipped(self, tmp_path):
        """expired-terminal threads in batch_state are skipped without touching the network.

        batch_state 中 expired 终态线程跳过且不实测网络。"""
        _write_index(tmp_path, [_row(UUID_EXPIRED)])
        (tmp_path / "index" / "batch_state.json").write_text(json.dumps(
            {UUID_EXPIRED: {"status": "expired",
                            "lastUpdated": "2026-01-20T04:53:43Z",
                            "note": "ENTRY_EXPIRED（平台已清除，不可恢复）"}}))
        cmd_search_mode_backfill(_NoNetworkFactory(), ACCOUNT, tmp_path)
        rows = _load_rows(tmp_path / "index" / f"library_{ACCOUNT.username}.json")
        # Terminal state is not backfilled; left empty as-is
        # 终态不补、如实留空
        assert "search_mode" not in rows[0]

    def test_online_fallback_and_expired_marking(self, tmp_path):
        """Go online only when no local raw exists: write back on successful extraction;
        ENTRY_EXPIRED is marked into batch_state.

        本地无 raw 才联网：成功提取写回；ENTRY_EXPIRED 标记进 batch_state。"""
        _write_index(tmp_path, [_row(UUID_ONLINE), _row(UUID_EXPIRED)])
        fetcher_payload = {
            UUID_ONLINE: {"metadata": {}, "background_entries": [],
                          "entries": [{"search_mode": "AGENTIC_RESEARCH"}]},
            UUID_EXPIRED: EntryExpiredError("ENTRY_EXPIRED"),
        }
        calls = []

        def factory(throttle=None):
            calls.append(throttle)
            return _FakeAdapter(fetcher_payload)

        cmd_search_mode_backfill(factory, ACCOUNT, tmp_path,
                                 delay_min=0, delay_max=0)
        rows = _load_rows(tmp_path / "index" / f"library_{ACCOUNT.username}.json")
        by_uuid = {t["entryUUID"]: t for t in rows}
        assert by_uuid[UUID_ONLINE]["search_mode"] == "AGENTIC_RESEARCH"
        assert "search_mode" not in by_uuid[UUID_EXPIRED]
        # Adapter lazily constructed exactly once
        # 适配器惰性构造一次
        assert len(calls) == 1
        state = json.loads((tmp_path / "index" / "batch_state.json").read_text())
        # Next round needs no request
        # 下轮免请求
        assert state[UUID_EXPIRED]["status"] == "expired"

    def test_idempotent_resume(self, tmp_path):
        """Already-enriched rows are skipped (idempotent): reruns neither overwrite nor reprocess.

        已富化的行跳过（幂等）：重跑不覆盖、不重复处理。"""
        _archive_thread(tmp_path, UUID_LOCAL, ["SEARCH"])
        p = _write_index(tmp_path, [_row(UUID_LOCAL, search_mode="RESEARCH")])
        cmd_search_mode_backfill(_NoNetworkFactory(), ACCOUNT, tmp_path)
        # Original value is not overwritten
        # 原值不被覆盖
        assert _load_rows(p)[0]["search_mode"] == "RESEARCH"

    def test_limit(self, tmp_path):
        _archive_thread(tmp_path, UUID_LOCAL, ["SEARCH"])
        _archive_thread(tmp_path, UUID_ONLINE, ["STUDY"])
        p = _write_index(tmp_path, [_row(UUID_LOCAL), _row(UUID_ONLINE)])
        cmd_search_mode_backfill(_NoNetworkFactory(), ACCOUNT, tmp_path, limit=1,
                                 online=False)
        rows = _load_rows(p)
        enriched = [t for t in rows if t.get("search_mode")]
        assert len(enriched) == 1


class _ListAdapter:
    """Fake adapter for cmd_index: platform index rows carry no search_mode (matching reality).

    cmd_index 用的假适配器：平台索引行不含 search_mode（与现实一致）。"""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def list_threads(self, account: Account):
        yield from self._rows


class TestIndexPreservesSearchMode:
    def test_refresh_merges_enrichment(self, tmp_path):
        """After an index refresh, search_mode enrichment is preserved by entryUUID; new rows are unaffected.

        index 刷新后 search_mode 富化按 entryUUID 保留；新行不受影响。"""
        idx = tmp_path / "index"
        idx.mkdir(parents=True)
        old = {"account": ACCOUNT.username, "count": 2,
               "threads": [_row(UUID_LOCAL, search_mode="STUDY"),
                           # Unenriched row has no key
                           # 未富化的行无键
                           _row(UUID_ONLINE)]}
        (idx / f"library_{ACCOUNT.username}.json").write_text(
            json.dumps(old, ensure_ascii=False))
        # Platform refresh: UUID_LOCAL still present (title changed), UUID_ONLINE deleted, a new thread added
        # 平台刷新：UUID_LOCAL 还在（title 变了），UUID_ONLINE 已删，新增新线程
        new_rows = [_row(UUID_LOCAL, title="改名了"), _row("99999999-0000-0000-0000-000000000000")]
        cmd_index(_ListAdapter(new_rows), ACCOUNT, tmp_path)
        rows = _load_rows(tmp_path / "index" / f"library_{ACCOUNT.username}.json")
        by_uuid = {t["entryUUID"]: t for t in rows}
        assert by_uuid[UUID_LOCAL]["search_mode"] == "STUDY"
        assert by_uuid[UUID_LOCAL]["title"] == "改名了"
        assert "search_mode" not in by_uuid["99999999-0000-0000-0000-000000000000"]

    def test_first_run_no_old_index(self, tmp_path):
        cmd_index(_ListAdapter([_row(UUID_LOCAL)]), ACCOUNT, tmp_path)
        rows = _load_rows(tmp_path / "index" / f"library_{ACCOUNT.username}.json")
        assert "search_mode" not in rows[0]

    def test_corrupt_old_index_warns_but_writes(self, tmp_path, caplog):
        idx = tmp_path / "index"
        idx.mkdir(parents=True)
        (idx / f"library_{ACCOUNT.username}.json").write_text("{损坏")
        with caplog.at_level(logging.WARNING):
            cmd_index(_ListAdapter([_row(UUID_LOCAL)]), ACCOUNT, tmp_path)
        rows = _load_rows(tmp_path / "index" / f"library_{ACCOUNT.username}.json")
        assert rows[0]["entryUUID"] == UUID_LOCAL
        assert any("search_mode" in r.message for r in caplog.records)


class TestBatchModeFilter:
    """index_row_matches_mode: authoritative search_mode wins; falls back to the old heuristic when missing (behavior unchanged).

    index_row_matches_mode：search_mode 权威优先；缺失回落旧启发式（行为不变）。"""

    def test_authoritative_search_mode(self):
        # The measured case from risk item 1: a study thread with displayModel=pplx_beta
        # was missed by the old heuristic under --mode study; after enrichment the authoritative path hits
        # 风险点 1 的实测案例：study 线程 displayModel=pplx_beta，
        # 旧启发式漏配 --mode study；富化后权威命中
        t = _row(UUID_LOCAL, displayModel="pplx_beta", search_mode="STUDY")
        assert index_row_matches_mode(t, "study")
        assert not index_row_matches_mode(t, "search")
        # STUDIO → search (the authoritative path no longer broad-matches sub-modes in)
        # STUDIO → search（权威路径下不再宽匹配混入子模式）
        t2 = _row(UUID_LOCAL, displayModel="pplx_beta", search_mode="STUDIO")
        assert index_row_matches_mode(t2, "search")
        assert not index_row_matches_mode(t2, "study")
        # RESEARCH → deep-research
        # RESEARCH 映射为 deep-research
        t3 = _row(UUID_LOCAL, displayModel="pplx_pro", search_mode="RESEARCH")
        assert index_row_matches_mode(t3, "deep-research")
        assert not index_row_matches_mode(t3, "search")

    def test_fallback_heuristic_unchanged(self):
        # Without search_mode: old behavior preserved exactly
        # 无 search_mode：旧行为逐样保持
        assert index_row_matches_mode(_row(UUID_LOCAL, displayModel="pplx_study"),
                                      "study")
        assert index_row_matches_mode(_row(UUID_LOCAL, displayModel="pplx_alpha"),
                                      "deep-research")
        assert index_row_matches_mode(
            _row(UUID_LOCAL, displayModel="pplx_agentic_research"), "council")
        assert index_row_matches_mode(_row(UUID_LOCAL, mode="COMPUTER"), "computer")
        # Old --mode search broad match: sub-mode threads with mode=SEARCH also hit (behavior unchanged)
        # 旧 --mode search 宽匹配：mode=SEARCH 的子模式线程也命中（行为不变）
        assert index_row_matches_mode(_row(UUID_LOCAL, displayModel="pplx_study"),
                                      "search")
        assert not index_row_matches_mode(_row(UUID_LOCAL, mode="COMPUTER"), "search")

    def test_unmapped_search_mode_falls_back(self):
        # search_mode holds an unknown new value: does not block, falls back to the heuristic
        # search_mode 为未知新值：不挡路，回落启发式
        t = _row(UUID_LOCAL, displayModel="pplx_study", search_mode="FUTURE_MODE")
        assert index_row_matches_mode(t, "study")
        assert index_row_matches_mode(t, "search")
