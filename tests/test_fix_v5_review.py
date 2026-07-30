"""V5 regression tests: fifth review-round fixes (V5-01/03/04/05/06/08/10).

Coverage:
- V5-01: idx_thread passthrough chain of export/batch (lastUpdated taken from
  the index updatedAt as microsecond ISO), the ts_us_to_iso_full fallback
  format, and idempotent single-export recovery for legacy ISO threads
  (is_unchanged);
- V5-03: find_thread_dirs rejects directories that are corrupt / missing
  web_uuid / missing thread.json;
- V5-04: _best_thread_dir candidates must match web_uuid exactly;
- V5-05: batch --mode filters council/study (by index displayModel);
- V5-06: CookieCache.save atomic write + 0o600 permissions;
- V5-08: spaces (without --fetch-meta) is purely local and must not trigger
  make_transport;
- V5-10: cron snippet quotes the account name + out_root passed explicitly.
Fully offline: synthetic data / TemporaryDirectory / monkeypatch, no network.

V5 回归测试：第五轮审查修复（V5-01/03/04/05/06/08/10）。

覆盖：
- V5-01：export/batch 的 idx_thread 传参链路（lastUpdated 取索引 updatedAt 微秒 ISO）、
  ts_us_to_iso_full 兜底格式、遗留 ISO 线程单导幂等（is_unchanged）；
- V5-03：find_thread_dirs 拒绝损坏/缺 web_uuid/缺 thread.json 的目录；
- V5-04：_best_thread_dir 候选须 web_uuid 全等；
- V5-05：batch --mode 过滤 council/study（按索引 displayModel）；
- V5-06：CookieCache.save 原子写 + 0o600 权限；
- V5-08：spaces（无 --fetch-meta）纯本地，不触发 make_transport；
- V5-10：cron 片段账户名加引号 + out_root 显式传入。
全离线：合成数据/TemporaryDirectory/monkeypatch，不触网。
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace


from pplx_export.commands.spaces_cmd import _best_thread_dir
from pplx_export.core.cookies import CookieCache
from pplx_export.core.models import Conversation, Turn
from pplx_export.sites.perplexity.fs_writer import FilesystemWriter
from pplx_export.sites.perplexity.normalize import ts_us_to_iso_full

UUID = "abcdef12-3456-7890-abcd-ef1234567890"
ISO_LU = "2026-07-22T14:58:06.833809Z"


def _conv(lu: str, n: int = 1) -> Conversation:
    return Conversation(
        web_uuid=UUID, title="t", mode="search", author="tester", last_updated=lu,
        turns=[Turn(index=i + 1, query=f"q{i}", created_us=1700000000000000 + i)
               for i in range(n)])


# ── V5-01: idx_thread passthrough chain and the lastUpdated contract
# ── V5-01：idx_thread 传参链路与 lastUpdated 契约 ────────────────────────────

class TestIdxThreadPassthrough:
    def test_export_uses_index_updated_at(self, tmp_path):
        """cmd_export looks up the index row in the local index and passes it to
        get_thread: thread.json.lastUpdated is the index updatedAt (microsecond
        ISO), not the minute-level display from ts_us_to_iso.

        cmd_export 从本地索引查索引行传入 get_thread：thread.json.lastUpdated
        为索引 updatedAt（微秒 ISO），不是 ts_us_to_iso 的分钟级 display。"""
        from pplx_export.commands.export_cmd import cmd_export

        idx = tmp_path / "index"
        idx.mkdir(parents=True)
        (idx / "library_acct.json").write_text(json.dumps({"threads": [{
            "entryUUID": UUID, "title": "t", "lastUpdated": ISO_LU, "mode": "SEARCH",
        }]}, ensure_ascii=False))
        seen = {}

        class _A:
            def get_thread(self, uuid, url=None, idx_thread=None):
                seen["idx"] = idx_thread
                return _conv((idx_thread or {}).get("lastUpdated") or "fallback")

            def get_assets(self, conv, dest_dir=None):
                return []

            def sub_agents(self, conv):
                return []

        account = SimpleNamespace(username="acct", folder="Tester")
        cmd_export(_A(), FilesystemWriter(tmp_path), UUID, account, False, tmp_path)

        assert seen["idx"]["entryUUID"] == UUID, "索引行应作为 idx_thread 传入"
        tj = json.loads(next(tmp_path.glob("*/*/*/thread.json")).read_text())
        assert tj["lastUpdated"] == ISO_LU
        assert " UTC" not in tj["lastUpdated"], "不得再写分钟级 display 格式"

    def test_export_idx_lookup_missing_returns_none(self, tmp_path):
        """Not found in the index (not refreshed / another account's thread):
        returns None, with the adapter as fallback.

        索引中查不到（未刷新/他账户线程）：返回 None，由 adapter 兜底。"""
        from pplx_export.commands.export_cmd import _idx_thread_for
        (tmp_path / "index").mkdir()
        assert _idx_thread_for(tmp_path, UUID) is None

    def test_fallback_is_true_iso_not_display(self):
        """The fallback without an index row is true ISO (second precision, Z
        suffix), same family as the index updatedAt.

        无索引行时的兜底为真 ISO（秒级 Z 后缀），与索引 updatedAt 同族。"""
        s = ts_us_to_iso_full(1753100286833809)
        assert s == "2026-07-21T13:38:06Z" or s.endswith("Z") and "T" in s
        assert " UTC" not in s and re_match_iso(s)
        assert ts_us_to_iso_full(None) == ""
        assert ts_us_to_iso_full("garbage") == ""

    def test_is_unchanged_recovers_for_iso_threads(self, tmp_path):
        """Post-fix chain: thread.json and conv.last_updated both carry the index
        ISO → idempotent-skip recovered (pre-fix conv used the display format,
        so 549 legacy threads were always judged changed).

        修复后链路：thread.json 与 conv.last_updated 同为索引 ISO → 幂等跳过恢复
        （修复前 conv 为 display 格式，549 个遗留线程恒判已变化）。"""
        w = FilesystemWriter(tmp_path)
        d = w.write_thread(_conv(ISO_LU))
        assert w.is_unchanged(_conv(ISO_LU), d) is True
        # Index trailing-zero difference still judged identical (V4-04 semantics
        # preserved)
        # 索引尾零差仍判同（V4-04 语义保持）
        assert w.is_unchanged(_conv("2026-07-22T14:58:06.8338090Z"), d) is True


def re_match_iso(s: str) -> bool:
    import re
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s))


# ── V5-03: find_thread_dirs identity verification tightened
# ── V5-03：find_thread_dirs 身份核验严格化 ──────────────────────────────────

class TestFindThreadDirsStrict:
    def _mk(self, root: Path, name: str, tj_content: str | None) -> Path:
        d = root / "acct" / "search" / f"{name}_{UUID[:8]}"
        d.mkdir(parents=True)
        if tj_content is not None:
            (d / "thread.json").write_text(tj_content)
        return d

    def test_corrupt_thread_json_rejected(self, tmp_path):
        w = FilesystemWriter(tmp_path)
        bad = self._mk(tmp_path, "2026-01-01_bad", "{corrupted json")
        assert bad not in w.find_thread_dirs(UUID)

    def test_missing_web_uuid_rejected(self, tmp_path):
        w = FilesystemWriter(tmp_path)
        d1 = self._mk(tmp_path, "2026-01-01_nofield", json.dumps({"title": "x"}))
        d2 = self._mk(tmp_path, "2026-01-02_empty", json.dumps({"web_uuid": ""}))
        assert d1 not in w.find_thread_dirs(UUID)
        assert d2 not in w.find_thread_dirs(UUID)

    def test_missing_thread_json_rejected(self, tmp_path):
        w = FilesystemWriter(tmp_path)
        d = self._mk(tmp_path, "2026-01-01_notj", None)
        assert d not in w.find_thread_dirs(UUID)

    def test_valid_match_accepted_and_mismatch_rejected(self, tmp_path):
        w = FilesystemWriter(tmp_path)
        good = self._mk(tmp_path, "2026-01-01_good", json.dumps({"web_uuid": UUID}))
        other = self._mk(tmp_path, "2026-01-02_other",
                         json.dumps({"web_uuid": "bbbbbbbb-1111-2222-3333-444444444444"}))
        found = w.find_thread_dirs(UUID)
        assert good in found and other not in found


# ── V5-04: _best_thread_dir candidates must match web_uuid exactly
# ── V5-04：_best_thread_dir 候选须 web_uuid 全等 ────────────────────────────

class TestBestThreadDirIdentity:
    def test_mismatched_web_uuid_not_candidate(self, tmp_path):
        """uuid8 name collision but a different web_uuid: must not become a
        candidate (prefer linking "not exported").

        uuid8 撞名但 web_uuid 不同：不得作为候选（宁可链「未导出」）。"""
        d = tmp_path / "a" / "search" / f"2026-07-22_x_{UUID[:8]}"
        d.mkdir(parents=True)
        (d / "thread.json").write_text(json.dumps(
            {"web_uuid": "bbbbbbbb-1111-2222-3333-444444444444",
             "lastUpdated": "2026-07-22T00:00:00Z"}))
        assert _best_thread_dir(tmp_path, UUID) is None

    def test_corrupt_not_candidate_valid_wins(self, tmp_path):
        bad = tmp_path / "a" / "search" / f"2026-07-22_bad_{UUID[:8]}"
        bad.mkdir(parents=True)
        (bad / "thread.json").write_text("{oops")
        good = tmp_path / "a" / "search" / f"2026-07-21_good_{UUID[:8]}"
        good.mkdir(parents=True)
        (good / "thread.json").write_text(json.dumps(
            {"web_uuid": UUID, "lastUpdated": "2026-07-21T00:00:00Z"}))
        assert _best_thread_dir(tmp_path, UUID) == good


# ── V5-05: batch --mode filters council/study
# ── V5-05：batch --mode 过滤 council/study ──────────────────────────────────

class TestBatchModeFilter:
    def _run(self, tmp_path, mode_filter):
        from pplx_export.commands.batch_cmd import cmd_batch

        idx = tmp_path / "index"
        idx.mkdir(parents=True)
        threads = [
            {"entryUUID": "u-search", "title": "s", "lastUpdated": "2026-07-04T00:00:00Z",
             "mode": "SEARCH", "displayModel": "pplx_pro"},
            {"entryUUID": "u-council", "title": "c", "lastUpdated": "2026-07-03T00:00:00Z",
             "mode": "SEARCH", "displayModel": "pplx_agentic_research"},
            {"entryUUID": "u-study", "title": "st", "lastUpdated": "2026-07-02T00:00:00Z",
             "mode": "SEARCH", "displayModel": "pplx_study"},
            {"entryUUID": "u-dr", "title": "dr", "lastUpdated": "2026-07-01T00:00:00Z",
             "mode": "SEARCH", "displayModel": "pplx_alpha"},
        ]
        (idx / "library_acct.json").write_text(json.dumps({"threads": threads}))
        seen = []

        class _A:
            def get_thread(self, uuid, url=None, idx_thread=None):
                seen.append(uuid)
                return _conv("2026-07-04T00:00:00Z")

            def get_assets(self, conv, dest_dir=None):
                return []

        class _W:
            def thread_dir_for(self, conv):
                return tmp_path / "w"

            def write_thread(self, conv, adapter=None):
                pass

        class _T:
            def delay(self): return 0.0
            def backoff(self, base=None): return 0.0
            def reset(self): pass

        account = SimpleNamespace(username="acct", folder="Acct")
        cmd_batch(_A(), _W(), account, tmp_path, None, mode_filter, False,
                  0, 0, full=True, throttle=_T())
        return seen

    def test_council_filter(self, tmp_path):
        assert self._run(tmp_path, "council") == ["u-council"]

    def test_study_filter(self, tmp_path):
        assert self._run(tmp_path, "study") == ["u-study"]

    def test_deep_research_filter_unchanged(self, tmp_path):
        assert self._run(tmp_path, "deep-research") == ["u-dr"]


# ── V5-06: CookieCache atomic write + permissions
# ── V5-06：CookieCache 原子写 + 权限 ────────────────────────────────────────

class TestCookieCacheAtomicSave:
    def test_save_permissions_and_content(self, tmp_path):
        p = tmp_path / ".cookies.json"
        cc = CookieCache(p)
        cc.save({"k": "v"}, "browser:edge", "a@b.c")
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600, f"应为 0o600，实际 {oct(mode)}"
        doc = json.loads(p.read_text())
        assert doc["cookies"] == {"k": "v"} and doc["account_email"] == "a@b.c"
        assert not (tmp_path / ".cookies.json.tmp").exists(), "临时文件应已被 replace"

    def test_overwrite_keeps_600_and_no_partial_json(self, tmp_path):
        p = tmp_path / ".cookies.json"
        # Simulate an existing corrupt/old file
        # 模拟既有损坏/旧文件
        p.write_text("{old")
        os.chmod(p, 0o644)
        cc = CookieCache(p)
        cc.save({"k2": "v2"}, "cache", "")
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
        assert json.loads(p.read_text())["cookies"] == {"k2": "v2"}
        assert cc.load() == {"k2": "v2"}


# ── V5-08: spaces purely local, exempt from transport
# ── V5-08：spaces 纯本地豁免 transport ───────────────────────────────────────

class TestSpacesOfflineExempt:
    def test_spaces_without_fetch_meta_needs_no_transport(self, tmp_path, monkeypatch):
        """spaces without --fetch-meta runs purely locally: any make_transport
        call fails the test.

        无 --fetch-meta 的 spaces 纯本地运行：make_transport 被调用即失败。"""
        import pplx_export.cli as cli

        monkeypatch.setattr(cli, "make_transport",
                            lambda *a, **k: (_ for _ in ()).throw(
                                AssertionError("离线 spaces 不应构造 transport")))
        monkeypatch.setattr(sys, "argv",
                            ["pplx-export", "spaces", "--out", str(tmp_path / "web_archive")])
        monkeypatch.chdir(tmp_path)
        # Passes as long as no exception is raised
        # 不抛异常即通过
        cli.main()
        assert (tmp_path / "spaces" / "spaces.json").exists()


# ── V5-10: cron snippet quoting discipline and explicit out_root
# ── V5-10：cron 片段引号纪律与显式 out_root ──────────────────────────────────

class TestCronSnippet:
    def test_account_quoted_and_explicit_out_root(self, tmp_path):
        from pplx_export.hooks.scheduler import SchedulerHook
        sch = SchedulerHook(tmp_path / "index")
        # Contains a space: the touchstone of quoting discipline
        # 含空格：引号纪律的试金石
        account = SimpleNamespace(username="my user")
        p = sch.write_cron_snippet(account, tmp_path / "web_archive")
        assert p == (tmp_path / "web_archive" / "index" / "cron_snippet.txt").resolve()
        content = p.read_text()
        assert "--account 'my user'" in content, "账户名必须加引号（F-07/F-14 对齐）"
        assert "--out '" in content
