"""Unit tests: core/state.py, core/throttle.py, hooks/incremental.py,
sites/perplexity/assets.py (_final_name), sites/perplexity/normalize.py (math normalization).

单元测试：core/state.py、core/throttle.py、hooks/incremental.py、
sites/perplexity/assets.py（_final_name）、sites/perplexity/normalize.py（公式规范化）。"""

from __future__ import annotations

import json

import pytest

from pplx_export.core.state import BatchState, norm_ts
from pplx_export.core.throttle import Throttle
from pplx_export.hooks.incremental import plan_incremental
from pplx_export.core.models import Asset
from pplx_export.sites.perplexity.assets import AssetDownloader
from pplx_export.sites.perplexity.normalize import normalize_math_delims


# ---------------------------------------------------------------- BatchState
# ------------------------------------------------------- BatchState（批处理状态）

class TestBatchState:
    def test_mark_ok_and_is_done(self, tmp_path):
        st = BatchState(tmp_path / "s.json")
        st.mark_ok("u1", "2026-01-01T00:00:00.000000Z", "标题")
        assert st.is_done("u1", "2026-01-01T00:00:00.000000Z")
        assert st.is_terminal("u1", "2026-01-01T00:00:00.000000Z")
        # lastUpdated has changed
        # lastUpdated 变了
        assert not st.is_done("u1", "2026-01-02T00:00:00.000000Z")
        assert not st.is_terminal("u1", "2026-01-02T00:00:00.000000Z")

    def test_is_done_normalizes_fractional_seconds(self, tmp_path):
        """The platform occasionally drops trailing zeros (.18033Z vs .180330Z);
        this must not be misjudged as changed.

        平台偶发丢尾零（.18033Z vs .180330Z）不应误判为已变更。"""
        st = BatchState(tmp_path / "s.json")
        st.mark_ok("u1", "2026-01-01T00:00:00.18033Z")
        assert st.is_done("u1", "2026-01-01T00:00:00.180330Z")

    def test_is_done_distinguishes_different_fractional_seconds(self, tmp_path):
        """V4-04: different fractional seconds (.100Z vs .900Z) are different
        instants and must be judged as changed.

        V4-04：不同小数秒（.100Z vs .900Z）是不同时间点，必须判为已变更。"""
        st = BatchState(tmp_path / "s.json")
        st.mark_ok("u1", "2026-01-01T00:00:00.100000Z")
        assert not st.is_done("u1", "2026-01-01T00:00:00.900000Z")

    def test_is_done_distinguishes_fraction_vs_no_fraction(self, tmp_path):
        """V4-04: with vs without a fractional part must not compare equal
        (.000000Z ≠ no fraction).

        V4-04：有小数与无小数不判同（.000000Z ≠ 无小数部分）。"""
        st = BatchState(tmp_path / "s.json")
        st.mark_ok("u1", "2026-01-01T00:00:00.000000Z")
        assert not st.is_done("u1", "2026-01-01T00:00:00Z")

    def test_is_done_requires_last_updated(self, tmp_path):
        st = BatchState(tmp_path / "s.json")
        st.mark_ok("u1", None)
        # No lastUpdated does not count as done (change cannot be determined)
        # 无 lastUpdated 不算完成（无法判变更）
        assert not st.is_done("u1", None)

    def test_mark_error_not_terminal(self, tmp_path):
        st = BatchState(tmp_path / "s.json")
        st.mark_error("u1", "2026-01-01T00:00:00Z", "t", "boom")
        assert not st.is_terminal("u1", "2026-01-01T00:00:00Z")
        # Seen before (error is not terminal; next round should retry as updated)
        # 处理过（error 非终态，下轮应重试为 updated）
        assert st.is_known("u1")

    def test_mark_expired_is_terminal(self, tmp_path):
        st = BatchState(tmp_path / "s.json")
        st.mark_expired("u1", "2026-01-01T00:00:00Z", note="ENTRY_EXPIRED")
        assert st.is_expired("u1")
        # Never retried, whatever the lastUpdated
        # 任何 lastUpdated 都不重试
        assert st.is_terminal("u1", "2026-01-02T00:00:00Z")

    def test_save_roundtrip_and_no_tmp_left(self, tmp_path):
        # Parent directory does not exist: save should create it
        # 父目录不存在：save 应自建
        p = tmp_path / "sub" / "s.json"
        st = BatchState(p)
        st.mark_ok("u1", "2026-01-01T00:00:00Z", "标题")
        st.save()
        assert p.exists()
        assert not (p.parent / f"{p.name}.tmp").exists(), "原子写后不应残留 tmp 文件"
        st2 = BatchState(p)
        assert st2.is_done("u1", "2026-01-01T00:00:00Z")
        assert st2.counts() == {"ok": 1}

    def test_corrupt_state_backed_up(self, tmp_path):
        """A corrupt state file is not silently emptied: it is backed up as
        .corrupt-* and rebuilt from scratch.

        损坏的状态文件不静默置空：备份为 .corrupt-* 后从零开始。"""
        p = tmp_path / "s.json"
        p.write_text("{not json")
        st = BatchState(p)
        assert st.state == {}
        backups = list(tmp_path.glob("s.json.corrupt-*"))
        assert len(backups) == 1 and backups[0].read_text() == "{not json"
        assert not p.exists(), "原损坏文件应已改名迁走"


# ---------------------------------------------------------------- norm_ts
# ------------------------------------------------------ norm_ts（时间戳归一）

class TestNormTs:
    """V4-04: normalize only trailing zeros in the fractional seconds; never
    strip the fractional part wholesale.

    V4-04：只对小数秒做尾零归一，不整段抹掉小数部分。"""

    def test_trailing_zero_loss_equal(self):
        """A pair differing only by a lost trailing zero compares equal
        (original intent).

        丢尾零的一对判同（原意图）。"""
        assert norm_ts("2026-01-01T00:00:00.18033Z") == norm_ts("2026-01-01T00:00:00.180330Z")
        assert norm_ts("2026-01-01T00:00:00.1Z") == norm_ts("2026-01-01T00:00:00.100000Z")

    def test_different_fraction_not_equal(self):
        """Different fractional seconds compare unequal (the fix: .100Z ≠ .900Z).

        不同小数秒判不等（修复点：.100Z ≠ .900Z）。"""
        assert norm_ts("2026-01-01T00:00:00.100Z") != norm_ts("2026-01-01T00:00:00.900Z")

    def test_fraction_vs_no_fraction_not_equal(self):
        """With vs without a fractional part compares unequal.

        有小数与无小数判不等。"""
        assert norm_ts("2026-01-01T00:00:00Z") != norm_ts("2026-01-01T00:00:00.000000Z")

    def test_all_zero_fraction_keeps_one_digit(self):
        """An all-zero fraction keeps at least one digit; differently written
        all-zero fractions still compare equal.

        全零小数保底保留一位，不同写法的全零小数仍判同。"""
        assert norm_ts("2026-01-01T00:00:00.000000Z") == norm_ts("2026-01-01T00:00:00.0Z")

    def test_empty_and_none_unchanged(self):
        """Empty/None behavior unchanged: both normalize to the empty string.

        空值/None 行为不变：统一归为空串。"""
        assert norm_ts(None) == ""
        assert norm_ts("") == ""

    def test_strips_whitespace(self):
        assert norm_ts("  2026-01-01T00:00:00.180330Z  ") == norm_ts("2026-01-01T00:00:00.18033Z")


# ---------------------------------------------------------------- Throttle
# ------------------------------------------------------------ Throttle（节流）

@pytest.fixture()
def no_sleep(monkeypatch):
    """Intercept time.sleep and return the call log (for test assertions).

    拦截 time.sleep，返回记录列表（测试断言用）。"""
    calls = []
    monkeypatch.setattr("pplx_export.core.throttle.time.sleep", calls.append)
    return calls


class TestThrottle:
    def test_delay_in_range(self, no_sleep):
        th = Throttle(delay_min=10.0, delay_max=20.0)
        for _ in range(50):
            d = th.delay()
            assert 10.0 <= d <= 20.0
        assert len(no_sleep) == 50 and all(10.0 <= s <= 20.0 for s in no_sleep)

    def test_backoff_jitter_bounds(self, no_sleep, monkeypatch):
        """jitter ∈ [0.8, 1.2] × base: pin both ends to verify the interval bounds.

        jitter ∈ [0.8, 1.2] × 基数：钉住两端验证区间边界。"""
        th = Throttle(backoff_factor=3.0)
        monkeypatch.setattr("pplx_export.core.throttle.random.uniform", lambda a, b: a)
        d = th.backoff(base=10.0)
        # 1st failure: base × factor^1 × 0.8
        # 第 1 次失败：base × factor^1 × 0.8
        assert d == pytest.approx(10.0 * 3.0 * 0.8)
        monkeypatch.setattr("pplx_export.core.throttle.random.uniform", lambda a, b: b)
        d = th.backoff(base=10.0)
        # 2nd failure: base × factor^2 × 1.2
        # 第 2 次失败：base × factor^2 × 1.2
        assert d == pytest.approx(10.0 * 9.0 * 1.2)

    def test_backoff_cap_300(self, no_sleep, monkeypatch):
        th = Throttle(backoff_factor=3.0)
        monkeypatch.setattr("pplx_export.core.throttle.random.uniform", lambda a, b: b)
        for _ in range(9):
            th.backoff(base=100.0)
        no_sleep.clear()  # isolate the final backoff's heartbeat chunks
        d = th.backoff(base=100.0)
        assert d == 300.0, "退避应封顶 300s"
        # Heartbeat-chunked sleep: the chunks of this backoff sum to the capped 300s,
        # and no single chunk exceeds the heartbeat interval — total wall-clock is unchanged.
        # 心跳分片睡眠：本次退避各分片之和等于封顶的 300s，单片不超过心跳间隔——总时长不变。
        assert abs(sum(no_sleep) - 300.0) < 1e-6, "分片之和应等于封顶 300s"
        assert all(s <= th.heartbeat_interval + 1e-9 for s in no_sleep)

    def test_reset(self, no_sleep, monkeypatch):
        th = Throttle(backoff_factor=3.0)
        monkeypatch.setattr("pplx_export.core.throttle.random.uniform", lambda a, b: 1.0)
        th.backoff(base=10.0)
        th.backoff(base=10.0)
        th.reset()
        assert th.backoff(base=10.0) == pytest.approx(30.0), "reset 后应回到 factor^1"


# ---------------------------------------------------------------- plan_incremental
# ------------------------------------------------- plan_incremental（增量计划）

def _t(uuid: str, lu: str) -> dict:
    return {"entryUUID": uuid, "lastUpdated": lu, "title": uuid}


@pytest.fixture()
def state(tmp_path):
    return BatchState(tmp_path / "batch_state.json")


class TestPlanIncremental:
    def test_all_new(self, state):
        actions, n = plan_incremental([_t("a", "2026-03-01"), _t("b", "2026-02-01")], state)
        assert [a for _, a in actions] == ["new", "new"]
        assert n == 0
        assert actions[0][0]["entryUUID"] == "a", "应按 lastUpdated 从新到旧排序"

    def test_all_terminal_early_stop(self, state):
        state.mark_ok("a", "2026-03-01")
        state.mark_ok("b", "2026-02-01")
        state.mark_expired("c", "2026-01-01")
        actions, n = plan_incremental([_t("a", "2026-03-01"), _t("b", "2026-02-01"), _t("c", "2026-01-01")], state)
        assert actions == [] and n == 3, "全终态应整体早停"

    def test_head_new_tail_done(self, state):
        state.mark_ok("b", "2026-02-01")
        state.mark_ok("c", "2026-01-01")
        actions, n = plan_incremental(
            [_t("a", "2026-03-01"), _t("b", "2026-02-01"), _t("c", "2026-01-01")], state)
        assert [a for _, a in actions] == ["new"] and n == 2, "尾部连续终态段被截掉"

    def test_gap_blocks_early_stop(self, state):
        """A gap in the middle (a new thread sandwiched between terminal ones):
        terminal entries above the gap cannot be skipped; only the tail is cut.

        中间缺口（新线程夹在终态之间）：缺口之上的终态不可跳过，仅截尾部。"""
        state.mark_ok("a", "2026-03-01")
        state.mark_ok("c", "2026-01-01")
        actions, n = plan_incremental(
            [_t("a", "2026-03-01"), _t("b", "2026-02-01"), _t("c", "2026-01-01")], state)
        assert [t["entryUUID"] for t, _ in actions] == ["a", "b"]
        assert [a for _, a in actions] == ["done", "new"] and n == 1

    def test_updated_when_last_updated_changed(self, state):
        state.mark_ok("a", "2026-01-01")
        actions, n = plan_incremental([_t("a", "2026-05-01")], state)
        assert [a for _, a in actions] == ["updated"] and n == 0

    def test_full_disables_early_stop(self, state):
        state.mark_ok("a", "2026-03-01")
        state.mark_ok("b", "2026-02-01")
        actions, n = plan_incremental([_t("a", "2026-03-01"), _t("b", "2026-02-01")], state, full=True)
        assert [a for _, a in actions] == ["done", "done"] and n == 0, "full 不早停，逐项返回"

    def test_force_reexport_but_not_expired(self, state):
        state.mark_ok("a", "2026-03-01")
        state.mark_expired("b", "2026-02-01")
        actions, n = plan_incremental([_t("a", "2026-03-01"), _t("b", "2026-02-01")], state, force=True)
        assert dict((t["entryUUID"], a) for t, a in actions) == {"a": "updated", "b": "expired"}
        assert n == 0, "force 不早停"


# ---------------------------------------------------------------- AssetDownloader._final_name
# ------------------------------------- AssetDownloader._final_name（最终文件名）

class TestFinalName:
    """Double-extension guard and content sniffing (pure function; the transport
    never touches the network).

    双扩展名防护与内容嗅探（纯函数，transport 不触网）。"""

    dl = AssetDownloader(None)

    def test_shell_script_no_double_ext(self):
        a = Asset(uuid="u", asset_type="CODE_FILE", filename="compile.sh")
        assert self.dl._final_name(a, b"#!/bin/bash\nset -e\n") == "compile.sh"

    def test_mermaid_versioned_no_double_ext(self):
        a = Asset(uuid="u", asset_type="CODE_FILE", filename="timeline_chart.mmd", version="v1", n_versions=2)
        assert self.dl._final_name(a, b"flowchart TD\n A-->B\n") == "timeline_chart_v1.mmd"

    def test_r_script_versioned(self):
        a = Asset(uuid="u", asset_type="CODE_FILE", filename="analysis.R", version="v2", n_versions=2)
        assert self.dl._final_name(a, b"x <- 1:10\n") == "analysis_v2.R"

    def test_magic_sniff_overrides_bin(self):
        """A CHART that is really a PNG: magic bytes correct the extension
        (.bin → .png).

        CHART 实为 PNG：魔数纠正扩展名（.bin → .png）。"""
        a = Asset(uuid="u", asset_type="CHART", filename="chart")
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        assert self.dl._final_name(a, png) == "chart.png"

    def test_url_path_ext_wins(self):
        a = Asset(uuid="u", asset_type="CHART", filename="fig",
                  url="https://pplx.ai/s3/model_structure.png?Policy=xxx")
        assert self.dl._final_name(a, b"\x89PNG\r\n\x1a\n") == "fig.png"

    def test_unknown_ext_fallback_txt(self):
        """Unknown extensions are not dropped (dest_name keeps the full original
        name as stem); .txt is appended once sniffed as text.

        未知扩展名不丢弃（dest_name 保留完整原名作 stem），嗅探为文本后追加 .txt。"""
        a = Asset(uuid="u", asset_type="", filename="notes.wkt")
        assert self.dl._final_name(a, b"POINT (30 10)\n") == "notes.wkt.txt"


# ---------------------------------------------------------------- normalize_math_delims
# -------------------------------------- normalize_math_delims（公式定界符规范化）

class TestNormalizeMath:
    def test_inline_paren(self):
        assert normalize_math_delims(r"其中 \(g_s\) 是气孔导度") == "其中 $g_s$ 是气孔导度"

    def test_display_bracket(self):
        assert normalize_math_delims(r"公式：\[x^2 + y^2\]") == "公式：$$\nx^2 + y^2\n$$"

    def test_empty_citation_marker_removed(self):
        assert normalize_math_delims(r"结论\[\]如下") == "结论如下"

    def test_inline_code_protected(self):
        src = r"用 `\(x\)` 表示字面量，而 \(x\) 是公式"
        assert normalize_math_delims(src) == r"用 `\(x\)` 表示字面量，而 $x$ 是公式"

    def test_fence_protected(self):
        src = "```r\n# 注释里的 \\(x\\) 不动\n```\n正文 \\(y\\)"
        assert normalize_math_delims(src) == "```r\n# 注释里的 \\(x\\) 不动\n```\n正文 $y$"

    def test_long_fence_with_inner_backticks(self):
        """Fences of 4+ backticks: an inner ``` does not terminate early.

        4+ 反引号围栏：内嵌 ``` 不提前截断。"""
        src = "````\n```\n\\(z\\)\n```\n````\n\\(w\\)"
        assert normalize_math_delims(src) == "````\n```\n\\(z\\)\n```\n````\n$w$"

    def test_mixed_open_paren_close_dollar(self):
        assert normalize_math_delims(r"\(x+1$ 残留") == "$x+1$ 残留"

    def test_mixed_open_dollar_close_paren(self):
        assert normalize_math_delims(r"$x+1\) 残留") == "$x+1$ 残留"

    def test_empty_input(self):
        assert normalize_math_delims("") == ""


class TestSafeFolder:
    """_safe_folder directory-name cleanup (OBS-01: cross-platform illegal
    characters + path traversal).

    _safe_folder 目录名消毒（OBS-01：跨平台非法字符 + 路径穿越）。"""

    def test_windows_illegal_chars(self):
        from pplx_export.sites.perplexity.fs_writer import _safe_folder
        assert _safe_folder('a:b*c?d"e<f>g|h') == "a_b_c_d_e_f_g_h"

    def test_path_traversal(self):
        from pplx_export.sites.perplexity.fs_writer import _safe_folder
        assert _safe_folder("a/b\\c") == "a_b_c"
        assert _safe_folder("..") == "unknown"
        assert _safe_folder(".") == "unknown"
        assert _safe_folder("") == "unknown"

    def test_existing_account_names_unchanged(self):
        from pplx_export.sites.perplexity.fs_writer import _safe_folder
        assert _safe_folder("Alice Example") == "Alice Example"
        assert _safe_folder("bob") == "bob"


def test_nested_wf_sources_uncapped():
    """Nested-payload citations are listed in full (self-review fix: removed the
    [:20] cap for citation fidelity).

    嵌套负载引文全量列出（自审修复：去 [:20] 封顶，引文保真）。"""
    from pplx_export.sites.perplexity.render import _render_nested_wf
    wp = {"id": "w1", "headline": "调研", "status": "WORKFLOW_COMPLETED",
          "steps": [{"status": "COMPLETED", "title": "检索", "items": [
              {"type": "WORKFLOW_ITEM_SOURCES",
               "payload": {"sources_payload": {"sources": [
                   {"name": f"来源{i}", "url": f"https://e.com/{i}"} for i in range(25)]}}}]}]}
    out = _render_nested_wf(wp)
    assert out.count("https://e.com/") == 25 and "余略" not in out


# ---------------------------------------------------------------- detect_mode
# ------------------------------------------------------ detect_mode（模式探测）

class TestDetectMode:
    """search_mode as the authoritative signal: mapping, any-entry traversal,
    multi-value specificity, conflicts with downstream signals, all-absent fallback.

    search_mode 权威信号：映射、any 遍历、多值特异性、与下游信号冲突、全灭回退。"""

    @staticmethod
    def _turn(step_type: str = ""):
        from pplx_export.core.models import Step, Turn
        return Turn(steps=[Step(step_type=step_type)] if step_type else [])

    def _detect(self, entries, step_type="", url="", metadata=None, idx=None):
        from pplx_export.sites.perplexity.normalize import detect_mode
        return detect_mode(metadata or {}, idx, url, [self._turn(step_type)], entries=entries)

    # ── search_mode mappings ──────────────────────────────
    # ── search_mode 各映射 ────────────────────────────────
    @pytest.mark.parametrize("sm,mode", [
        ("ASI", "computer"), ("AGENTIC_RESEARCH", "council"), ("STUDY", "study"),
        ("RESEARCH", "deep-research"), ("SEARCH", "search"), ("STUDIO", "search"),
    ])
    def test_search_mode_mapping(self, sm, mode):
        assert self._detect([{"search_mode": sm}]) == mode

    def test_search_mode_any_entry(self):
        """any() walks all entries: a first entry without search_mode must not
        be missed.

        any 遍历全部 entries：首条无 search_mode 不漏判。"""
        entries = [{"search_mode": ""}, {"search_mode": "RESEARCH"}]
        assert self._detect(entries) == "deep-research"

    def test_search_mode_case_insensitive(self):
        assert self._detect([{"search_mode": "research"}]) == "deep-research"

    # ── Multi-value conflict within a thread: highest specificity wins ──
    # ── 线程内多值冲突：特异性取最高 ───────────────────────
    def test_multi_value_specificity(self, caplog):
        entries = [{"search_mode": "SEARCH"}, {"search_mode": "RESEARCH"}]
        with caplog.at_level("WARNING", logger="normalize"):
            assert self._detect(entries) == "deep-research"
        assert "模式切换" in caplog.text

    def test_multi_value_computer_wins(self, caplog):
        entries = [{"search_mode": "ASI"}, {"search_mode": "STUDY"}, {"search_mode": "SEARCH"}]
        with caplog.at_level("WARNING", logger="normalize"):
            assert self._detect(entries) == "computer"
        assert "模式切换" in caplog.text

    # ── Conflict with downstream signals: search_mode wins ──
    # ── 与下游信号冲突：search_mode 优先 ───────────────────
    def test_search_mode_beats_step_name(self, caplog):
        """RESEARCH_ANSWER step vs search_mode=SEARCH: search_mode wins, with a
        warning logged.

        RESEARCH_ANSWER 步骤 vs search_mode=SEARCH：采 search_mode 并告警。"""
        with caplog.at_level("WARNING", logger="normalize"):
            assert self._detect([{"search_mode": "SEARCH"}], step_type="RESEARCH_ANSWER") == "search"
        assert "search_mode" in caplog.text

    def test_search_mode_beats_display_model(self, caplog):
        """display_model=pplx_study vs search_mode=RESEARCH: search_mode wins,
        with a warning logged.

        display_model=pplx_study vs search_mode=RESEARCH：采 search_mode 并告警。"""
        entries = [{"search_mode": "RESEARCH", "display_model": "pplx_study"}]
        with caplog.at_level("WARNING", logger="normalize"):
            assert self._detect(entries) == "deep-research"
        assert "search_mode" in caplog.text

    def test_search_mode_research_without_steps(self):
        """A RESEARCH thread missing the RESEARCH_ANSWER step (root cause of the
        historical misjudgment): still detected as deep-research.

        RESEARCH 会话缺 RESEARCH_ANSWER 步骤（历史误判根因）：仍判 deep-research。"""
        entries = [{"search_mode": "RESEARCH", "display_model": "pplx_alpha"}]
        assert self._detect(entries, step_type="SEARCH_WEB") == "deep-research"

    # ── search_mode all absent: original step-name + display_model chain ──
    # ── search_mode 全灭：走原有步骤名+display_model 链 ────
    def test_fallback_step_name_chain(self):
        assert self._detect([{"display_model": "turbo"}], step_type="RESEARCH_ANSWER") == "deep-research"
        assert self._detect([{"display_model": "turbo"}], step_type="COUNCIL_RESEARCH") == "council"
        assert self._detect([{"display_model": "turbo"}], url="https://www.perplexity.ai/computer/tasks/x") == "computer"

    def test_fallback_display_model_chain(self):
        assert self._detect([{"display_model": "pplx_study"}]) == "study"
        assert self._detect([{"display_model": "pplx_agentic_research"}]) == "council"
        assert self._detect([{"display_model": "pplx_asi_opus"}]) == "computer"

    def test_fallback_display_model_beats_step(self, caplog):
        """Conflicts inside the original chain keep the original semantics:
        display_model beats the step name.

        原链内部冲突保持原语义：display_model 优先于步骤名。"""
        with caplog.at_level("WARNING", logger="normalize"):
            assert self._detect([{"display_model": "pplx_study"}], step_type="RESEARCH_ANSWER") == "study"
        assert "display_model" in caplog.text

    def test_fallback_unknown_search_mode_ignored(self):
        """An unlisted search_mode value is treated as absent; fall back to the
        original chain.

        未收录的 search_mode 取值视为全灭，回退原链。"""
        entries = [{"search_mode": "FUTURE_MODE_X", "display_model": "pplx_study"}]
        assert self._detect(entries) == "study"

    def test_fallback_all_empty_is_search(self):
        assert self._detect([{"display_model": "turbo"}]) == "search"
        assert self._detect([], step_type="SEARCH_WEB") == "search"
        assert self._detect(None) == "search"

    # ── search_mode vs classification consistency across the five full-thread fixtures ──
    # ── 五个全线程 fixture 的 search_mode 与分类一致性 ─────
    @pytest.mark.parametrize("fixture,mode", [
        ("search_demo", "search"), ("deep_research_demo", "deep-research"),
        ("council_demo", "council"), ("study_demo", "study"),
        ("computer_demo", "computer"),
    ])
    def test_thread_fixtures(self, fixture, mode):
        from pathlib import Path
        p = Path(__file__).parent / "fixtures" / fixture / "raw_entries.json"
        entries = json.loads(p.read_text())["entries"]
        assert self._detect(entries) == mode


class TestFetchMissingBlocks:
    """fetch-blocks: study now in scope + automatic adapter switching per account
    directory (time.sleep stubbed).

    fetch-blocks：study 纳入范围 + 按账户目录分组自动换适配器（时间休眠打桩）。"""

    def _mk_thread(self, root, folder, mode, uuid8, with_blocks=False):
        import json as _json
        td = root / folder / mode / f"2025-01-01_t_{uuid8}"
        td.mkdir(parents=True)
        (td / "thread.json").write_text(_json.dumps(
            {"web_uuid": uuid8 + "-x", "mode": mode, "title": "t"}, ensure_ascii=False, indent=1))
        if with_blocks:
            (td / "raw_blocks.json").write_text("{}")
        return td

    def test_study_in_scope_and_per_account_adapters(self, tmp_path, monkeypatch):
        import json as _json
        from pplx_export.commands.assets_backfill_cmd import _fetch_missing_blocks
        monkeypatch.setattr("time.sleep", lambda *_: None)

        class FakeFetcher:
            def get_thread_blocks(self, uuid):
                return {"metadata": {}, "entries": [], "background_entries": []}

        class FakeTransport:
            pass

        class FakeAdapter:
            def __init__(self, tag):
                self.tag = tag
                self.fetcher = FakeFetcher()
                self.transport = FakeTransport()

        t1 = self._mk_thread(tmp_path, "Alice Example", "deep-research", "aaaa1111")
        t2 = self._mk_thread(tmp_path, "bob", "study", "bbbb2222")
        t3 = self._mk_thread(tmp_path, "bob", "search", "cccc3333")
        t4 = self._mk_thread(tmp_path, "bob", "computer", "dddd4444", with_blocks=True)

        requested = []
        primary = FakeAdapter("primary")
        _fetch_missing_blocks(primary, tmp_path, None,
                              adapter_for_dir=lambda f: (requested.append(f), FakeAdapter(f))[1])

        assert sorted(requested) == ["Alice Example", "bob"], "每账户目录各建一个适配器"
        assert (t1 / "raw_blocks.json").exists() and (t2 / "raw_blocks.json").exists(), \
            "deep-research 与 study 都应补抓"
        assert not (t3 / "raw_blocks.json").exists(), "search 不在补抓范围"
        assert _json.loads((t4 / "raw_blocks.json").read_text()) == {}, "已有 blocks 不动"

    def test_single_adapter_fallback(self, tmp_path, monkeypatch):
        from pplx_export.commands.assets_backfill_cmd import _fetch_missing_blocks
        monkeypatch.setattr("time.sleep", lambda *_: None)

        class FakeFetcher:
            def get_thread_blocks(self, uuid):
                return {"metadata": {}, "entries": [], "background_entries": []}

        class FakeAdapter:
            fetcher = FakeFetcher()
            transport = None

        t1 = self._mk_thread(tmp_path, "bob", "study", "eeee5555")
        # adapter_for_dir not passed
        # 不传 adapter_for_dir
        _fetch_missing_blocks(FakeAdapter(), tmp_path, None)
        assert (t1 / "raw_blocks.json").exists()


class TestExternalReviewFixes:
    """Regressions for fixes from the 2026-07-22 full external review
    (docs/reports/2026-07-22-full-code-review).

    2026-07-22 外部完整审查（docs/reports/2026-07-22-full-code-review）修复回归。"""

    def test_f01_table_cells_not_truncated(self):
        from pplx_export.sites.perplexity.render import render_wf_item
        long_val = "x" * 200
        it = {"type": "WORKFLOW_ITEM_TABLE",
              "payload": {"table_payload": {"columns": ["c"],
                                            "rows": [{"cells": {"c": long_val}}]}}}
        out = render_wf_item(it)
        assert long_val in out, "表格单元格不得按 80 字符截断（保真）"

    def test_f06_cookie_cache_chmod_600(self, tmp_path):
        import os
        import stat
        from pplx_export.core.cookies import CookieCache
        cc = CookieCache(tmp_path / ".cookies.json")
        cc.save({"k": "v"}, source="test", account_email="a@b.c")
        mode = stat.S_IMODE(os.stat(tmp_path / ".cookies.json").st_mode)
        assert mode == 0o600, oct(mode)

    def test_f10_cookie_cache_bad_fetched_at(self, tmp_path):
        from pplx_export.core.cookies import CookieCache
        p = tmp_path / ".cookies.json"
        p.write_text('{"fetched_at": "2026-07-22", "cookies": {"k": "v"}}')
        assert CookieCache(p).load() is None, "非数值 fetched_at 应按无缓存处理不抛异常"

    def test_f11_domain_suffix_match(self, monkeypatch):
        # Assert the real source behavior directly: from_browser_raw filters the
        # browser cookie jar via _domain_match; evilperplexity.ai / notperplexity.ai
        # must not match perplexity.ai (the predicate's own positive/negative cases
        # are covered by test_fix_n04_cookies.py; this covers the browser import path).
        # 直接断言源码真实行为：from_browser_raw 经 _domain_match 过滤浏览器 cookie jar，
        # evilperplexity.ai / notperplexity.ai 不得命中 perplexity.ai（_domain_match 谓词本身
        # 的正负面由 test_fix_n04_cookies.py 覆盖，这里补浏览器导入路径）。
        import pplx_export.core.cookies.loaders as cookies_mod

        class _FakeCookie:
            def __init__(self, domain):
                self.name, self.domain, self.value = "k", domain, "v"

        jar = [_FakeCookie(d) for d in (
            "perplexity.ai", ".www.perplexity.ai", "www.perplexity.ai",
            "evilperplexity.ai", "notperplexity.ai",
        )]
        monkeypatch.setattr(cookies_mod, "_bc3_loader",
                            lambda name: (lambda domain_name=None: jar))
        domains = [d for _, d, _ in cookies_mod.from_browser_raw("edge")]
        assert domains == ["perplexity.ai", ".www.perplexity.ai", "www.perplexity.ai"], (
            f"冒名域不得被采: {domains}")

    def test_f17_uuid_regex_ignorecase(self):
        import re
        pat = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                         re.IGNORECASE)
        assert pat.findall("参见 00000000-0000-4000-8000-0000000000AB 线程")


# ---------------------------------------------------------------- incremental index (B)
# ------------------------------------------------- 增量 index（B）

from pplx_export.commands.index_cmd import cmd_index, _STOP_RUN  # noqa: E402


class _FakeIdxAdapter:
    def __init__(self, rows):
        self._rows = rows
        self.consumed = 0

    def list_threads(self, account):
        for r in self._rows:
            self.consumed += 1
            yield r


class _IdxAcct:
    username = "u"


def _irow(u: str, lu: str, **extra) -> dict:
    return {"entryUUID": u, "lastUpdated": lu, "title": u, **extra}


class TestIncrementalIndex:
    def _write_lib(self, tmp_path, rows, **doc_extra):
        idx = tmp_path / "index" / "library_u.json"
        idx.parent.mkdir(parents=True, exist_ok=True)
        doc = {"account": "u", "extracted_at": "2026-06-01T00:00:00Z",
               "count": len(rows), "threads": rows, **doc_extra}
        idx.write_text(json.dumps(doc), encoding="utf-8")
        return idx

    def _seed_state(self, **kw):
        from pplx_export import config as cfg
        cfg.INDEX_STATE["u"] = {"extracted_at": "2026-06-01T00:00:00Z",
                                "last_full_index_at": "", "incremental_runs_since_full": 0, **kw}

    def _state(self):
        from pplx_export import config as cfg
        return cfg.INDEX_STATE.get("u") or {}

    def test_incremental_stops_at_known_boundary_and_merges(self, tmp_path):
        from pplx_export import config as cfg
        old = [_irow(f"o{i}", "2026-01-01T00:00:00Z") for i in range(30)]
        old[0]["search_mode"] = "RESEARCH"  # enrichment must survive
        idx = self._write_lib(tmp_path, old)
        self._seed_state()
        # NEWEST-first stream: 2 new rows, then the 30 old rows unchanged
        # NEWEST 流：2 条新行，随后 30 条旧行未变
        stream = [_irow("n0", "2026-07-01T00:00:00Z"),
                  _irow("n1", "2026-07-01T00:00:00Z")] + [dict(r) for r in old]
        adapter = _FakeIdxAdapter(stream)
        cmd_index(adapter, _IdxAcct(), tmp_path, full=False)
        # Early stop: 2 new + _STOP_RUN known-unchanged consumed, the rest not paged
        # 早停：只消费 2 新 + _STOP_RUN 条已知未变，其余不翻页
        assert adapter.consumed == 2 + _STOP_RUN
        doc = json.loads(idx.read_text())
        uuids = [t["entryUUID"] for t in doc["threads"]]
        assert uuids[:2] == ["n0", "n1"]
        # No loss: every old thread is still present (tail carried over)
        # 不丢失：全部旧线程仍在（尾段沿用）
        assert set(uuids) == {"n0", "n1"} | {f"o{i}" for i in range(30)}
        assert doc["count"] == 32
        # Volatile metadata moved to config [index_state]; doc carries only stable fields
        # 易变元数据已迁至 config [index_state]；doc 只保留稳定字段
        assert "extracted_at" not in doc
        assert "incremental_runs_since_full" not in doc
        assert self._state()["incremental_runs_since_full"] == 1
        # last full reconciliation time is preserved in config state
        # 上次全量对账时间保留在 config 状态
        assert self._state()["last_full_index_at"] == "2026-06-01T00:00:00Z"
        # search_mode enrichment preserved on the re-fetched row
        # 重抓行上的 search_mode 富化保留
        assert next(t for t in doc["threads"] if t["entryUUID"] == "o0")["search_mode"] == "RESEARCH"
        cfg.INDEX_STATE.clear()

    def test_incremental_runs_counter_increments(self, tmp_path):
        from pplx_export import config as cfg
        old = [_irow(f"o{i}", "2026-01-01T00:00:00Z") for i in range(30)]
        self._write_lib(tmp_path, old, incremental_runs_since_full=4,
                        last_full_index_at="2026-05-01T00:00:00Z")
        stream = [dict(r) for r in old]
        cmd_index(_FakeIdxAdapter(stream), _IdxAcct(), tmp_path, full=False)
        assert self._state()["incremental_runs_since_full"] == 5
        assert self._state()["last_full_index_at"] == "2026-05-01T00:00:00Z"
        cfg.INDEX_STATE.clear()

    def test_full_rewrites_and_resets_counter(self, tmp_path):
        from pplx_export import config as cfg
        old = [_irow(f"o{i}", "2026-01-01T00:00:00Z") for i in range(30)]
        self._write_lib(tmp_path, old, incremental_runs_since_full=9)
        self._seed_state(incremental_runs_since_full=9)
        stream = [_irow("n0", "2026-07-01T00:00:00Z")] + [dict(r) for r in old[:5]]
        adapter = _FakeIdxAdapter(stream)
        cmd_index(adapter, _IdxAcct(), tmp_path, full=True)
        # Full sweep consumes the whole stream (no early stop)
        # 全量消费整个流（不早停）
        assert adapter.consumed == len(stream)
        doc = json.loads((tmp_path / "index" / "library_u.json").read_text())
        # Full rewrite: only what was fetched, counter reset
        # 全量重写：只保留本次抓取，计数归零
        assert doc["count"] == len(stream)
        assert self._state()["incremental_runs_since_full"] == 0
        assert self._state()["last_full_index_at"] == self._state()["extracted_at"]
        cfg.INDEX_STATE.clear()

    def test_first_run_without_existing_library_is_full(self, tmp_path):
        from pplx_export import config as cfg
        # No existing library → incremental has nothing to stop against → full behavior
        # 无既有库 → 增量无从早停 → 按全量行为
        stream = [_irow(f"n{i}", "2026-07-01T00:00:00Z") for i in range(3)]
        adapter = _FakeIdxAdapter(stream)
        cmd_index(adapter, _IdxAcct(), tmp_path, full=False)
        assert adapter.consumed == 3
        doc = json.loads((tmp_path / "index" / "library_u.json").read_text())
        assert doc["count"] == 3
        assert self._state()["incremental_runs_since_full"] == 0
        cfg.INDEX_STATE.clear()


def test_index_incremental_exhausted_counts_as_full(tmp_path):
    """An incremental run that pages the whole library (no early stop) is a full
    reconciliation: counter reset and last_full refreshed.

    增量却翻到尽头（未早停）等同一次全量对账：计数归零、last_full 刷新。"""
    from pplx_export import config as cfg
    old = [_irow(f"o{i}", "2026-01-01T00:00:00Z") for i in range(5)]
    idx = tmp_path / "index" / "library_u.json"
    idx.parent.mkdir(parents=True)
    idx.write_text(json.dumps({"account": "u", "extracted_at": "2026-06-01T00:00:00Z",
                               "count": 5, "threads": old,
                               "incremental_runs_since_full": 4}), encoding="utf-8")
    adapter = _FakeIdxAdapter([dict(r) for r in old])
    cmd_index(adapter, _IdxAcct(), tmp_path, full=False)
    assert adapter.consumed == 5  # exhausted, no early stop
    doc = json.loads(idx.read_text())
    assert doc["count"] == 5
    st = cfg.INDEX_STATE["u"]
    assert st["incremental_runs_since_full"] == 0
    assert st["last_full_index_at"] == st["extracted_at"]
    cfg.INDEX_STATE.clear()


def test_index_incremental_preserves_uuidless_old_rows(tmp_path):
    """Incremental merge must carry over old rows lacking entryUUID (what --full keeps).

    增量合并必须保留缺 entryUUID 的旧行（--full 会保留的行）。"""
    uuidless = {"title": "legacy-no-uuid", "lastUpdated": "2026-01-01T00:00:00Z"}
    old = [uuidless] + [_irow(f"o{i}", "2026-01-01T00:00:00Z") for i in range(30)]
    idx = tmp_path / "index" / "library_u.json"
    idx.parent.mkdir(parents=True)
    idx.write_text(json.dumps({"account": "u", "extracted_at": "2026-06-01T00:00:00Z",
                               "count": len(old), "threads": old}), encoding="utf-8")
    adapter = _FakeIdxAdapter([_irow(f"o{i}", "2026-01-01T00:00:00Z") for i in range(30)])
    cmd_index(adapter, _IdxAcct(), tmp_path, full=False)
    assert adapter.consumed == _STOP_RUN  # early-stopped at the known boundary
    doc = json.loads(idx.read_text())
    assert "legacy-no-uuid" in [t.get("title") for t in doc["threads"]]


# ---------------------------------------------------------------- models config (soft-coded)
# ------------------------------------------------- 模型配置（软编码）

def test_api_version_single_source():
    """2.18 and the ask block-list literal live only in platform.py (no drift).

    2.18 与 ask 块列表字面量仅存在于 platform.py（不散落）。"""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "pplx_export"
    stray_ver, stray_block = [], []
    for pyf in root.rglob("*.py"):
        if pyf.name == "platform.py":
            continue
        text = pyf.read_text(encoding="utf-8")
        rel = str(pyf.relative_to(root))
        if "2.18" in text:
            stray_ver.append(rel)
        if '"answer_modes"' in text:  # first entry of the ask block list
            stray_block.append(rel)
    assert stray_ver == [], f"2.18 只应在 platform.py，散落于: {stray_ver}"
    assert stray_block == [], f"block 列表只应在 platform.py，散落于: {stray_block}"


def test_refresh_models_extracts_frontend_fields(tmp_path, monkeypatch):
    """refresh_models writes models_cache.json and config.toml metadata,
    then populates MODEL_CONFIG with frontend-visible fields only.

    refresh_models 写入 models_cache.json 与 config.toml 元数据，
    并将 MODEL_CONFIG 仅填充前端可见字段。"""
    from pplx_export import config as cfg
    from pplx_export.sites.perplexity import ask_api
    import pplx_export.sites.perplexity.ask_api as mod

    raw = {
        "models": {"pplx_pro": {"label": "Best", "provider": "PERPLEXITY", "mode": "search"},
                   "pplx_alpha": {"label": "R", "provider": "P", "mode": "research"}},
        "default_models": {"research": "pplx_alpha", "search": "pplx_pro"},
        "agentic_research_compare_models": ["m1", "m2", "m3"],
        "search_config": [],
        "computer_config": [],
    }
    # Mock fetch_models_config to return our raw
    # Mock fetch_models_config 返回原始数据
    monkeypatch.setattr(mod, "fetch_models_config", lambda t: raw)
    # Mock write_models_section (no real file write)
    # Mock write_models_section（不实际写文件）
    writes = []
    monkeypatch.setattr(cfg, "write_models_section", lambda p, s: writes.append((str(p), s)))
    monkeypatch.setattr(cfg, "write_models_cache", lambda r: None)
    cfg.MODEL_CONFIG.clear()
    config_path = tmp_path / "config.toml"
    config_path.write_text("")

    section = ask_api.refresh_models(object(), str(config_path))

    assert section["default_models"] == {"research": "pplx_alpha", "search": "pplx_pro"}
    assert section["council_defaults"] == ["m1", "m2", "m3"]
    assert "search_config" in section
    assert "computer_config" in section
    # Metadata-only write
    # 仅元数据写入
    assert len(writes) == 1
    assert "last_refreshed" in writes[0][1]
    assert "catalog" not in writes[0][1]  # catalog NOT in config.toml anymore
    cfg.MODEL_CONFIG.clear()


def test_build_envelope_config_override_then_platform_fallback():
    from pplx_export import config as cfg
    from pplx_export.sites.perplexity import ask_api
    cfg.MODEL_CONFIG.clear()
    try:
        # fallback: pinned platform values
        # 回退：platform 钉死值
        assert ask_api.build_envelope("q", "search")["params"]["model_preference"] == ask_api.MODE_MODEL["search"]
        assert (ask_api.build_envelope("q", "council")["params"]["compare_model_preferences"]
                == list(ask_api.COUNCIL_DEFAULT_MODELS)[:3])
        # override: config default_models wins (API mode names)
        # 覆盖：default_models 优先（API 模式名）
        cfg.MODEL_CONFIG.update({"default_models": {"search": "XYZ"}, "council_defaults": ["m1", "m2"]})
        assert ask_api.build_envelope("q", "search")["params"]["model_preference"] == "XYZ"
        assert ask_api.build_envelope("q", "council")["params"]["compare_model_preferences"] == ["m1", "m2"]
    finally:
        cfg.MODEL_CONFIG.clear()


def test_maybe_refresh_models_ttl(monkeypatch, tmp_path, caplog):
    import logging
    from pplx_export import config as cfg
    import pplx_export.ask_cli as ac
    calls = []
    monkeypatch.setattr(ac, "refresh_models", lambda *a, **k: calls.append(1))
    try:
        # no config loaded → no-op (rely on pinned fallback)
        # 未加载配置 → 空操作（用钉死兜底）
        monkeypatch.setattr(cfg, "LOADED_CONFIG_PATH", None)
        cfg.MODEL_CONFIG.clear()
        ac._maybe_refresh_models(object())
        assert calls == []
        # loaded + stale (no last_refreshed) + auto_refresh → refresh runs
        # 已加载 + 过期（无 last_refreshed）+ auto_refresh → 触发刷新
        monkeypatch.setattr(cfg, "LOADED_CONFIG_PATH", tmp_path / "c.toml")
        cfg.MODEL_CONFIG.update({"auto_refresh": True})
        ac._maybe_refresh_models(object())
        assert calls == [1]
        # loaded + stale + no auto_refresh → warn, no refresh
        # 已加载 + 过期 + 无 auto_refresh → 仅告警，不刷新
        calls.clear()
        cfg.MODEL_CONFIG.clear()
        with caplog.at_level(logging.WARNING, logger="pplx_export.ask-cli"):
            ac._maybe_refresh_models(object())
        assert calls == []
        assert any("模型表" in r.getMessage() for r in caplog.records)
    finally:
        cfg.MODEL_CONFIG.clear()


def test_find_git_root(tmp_path):
    """_find_git_root walks up to the first ancestor containing .git.

    _find_git_root 向上找到第一个含 .git 的祖先目录。"""
    from pplx_export.commands.common import _find_git_root
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    archive = repo / "web_archive" / "Alice Example"
    archive.mkdir(parents=True)
    assert _find_git_root(archive) == repo.resolve()
    # No git repo anywhere up the tree → None
    # 树中无 git 仓库 → None
    assert _find_git_root(tmp_path / "elsewhere" / "x") is None


def test_git_pins_c_locale(tmp_path, monkeypatch):
    """_git must run the child git with LC_ALL=C so diagnostics stay the
    canonical English strings that maybe_auto_commit's push classifier
    matches. Under a localized git (zh_CN.UTF-8 on this host) a plain
    "未配置推送目标" matches no English pattern, so a missing push
    destination would be misclassified as a hard conflict. Everything else
    in the environment must be inherited unchanged.

    _git 必须以 LC_ALL=C 运行子 git，保证报错恒为 maybe_auto_commit 的 push
    分类所匹配的规范英文串：本机（zh_CN.UTF-8）本地化 git 输出的
    “未配置推送目标”无英文模式可匹配，会把“无推送目标”误判为冲突硬错误。
    其余环境变量须原样继承。"""
    import os
    from pplx_export.commands import common

    seen: dict = {}

    class R:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, *args, **kwargs):
        seen["env"] = kwargs.get("env")
        return R()

    monkeypatch.setattr(common.subprocess, "run", fake_run)
    monkeypatch.setenv("PPLX_TEST_INHERIT_MARKER", "keep")
    common._git(tmp_path, "status")

    env = seen["env"]
    assert env is not None
    assert env["LC_ALL"] == "C"
    assert env["LANG"] == "C"
    assert env["LANGUAGE"] == ""
    # PATH / HOME / git-config discovery inherited unchanged.
    # PATH / HOME / git 配置发现原样继承。
    assert env["PPLX_TEST_INHERIT_MARKER"] == "keep"
    assert env["PATH"] == os.environ["PATH"]


def test_maybe_auto_commit(tmp_path, monkeypatch):
    """maybe_auto_commit: commits the archive subtree; unrelated dirty files are
    left untouched; no changes → no commit; no enclosing repo → skip.

    maybe_auto_commit：提交归档子树；仓库内无关脏文件不动；无变更不提交；
    无上层仓库则跳过。"""
    import subprocess
    from pplx_export import config as cfg
    from pplx_export.commands import common

    monkeypatch.setattr(cfg, "AUTO_COMMIT", True)
    monkeypatch.setattr(cfg, "AUTO_PUSH", False)

    # Build a real git repo with unrelated dirty file + archive subtree
    # 建真实 git 仓库，含无关脏文件 + 归档子树
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "unrelated.txt").write_text("keep me")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    archive = repo / "web_archive"
    archive.mkdir()
    (archive / "new_thread.txt").write_text("data")
    # Modify an unrelated tracked file AFTER init: it must stay unstaged.
    # init 后修改一个无关的已跟踪文件：它必须保持未暂存。
    (repo / "unrelated.txt").write_text("modified but not mine")

    common.maybe_auto_commit(archive)

    # Archive committed; unrelated.txt left unstaged
    # 归档已提交；unrelated.txt 未被暂存
    out = subprocess.run(["git", "-C", str(repo), "log", "--oneline", "-1"],
                         capture_output=True, text=True).stdout
    assert "archive: incremental snapshot" in out
    status = subprocess.run(["git", "-C", str(repo), "status", "--short"],
                            capture_output=True, text=True).stdout
    assert "unrelated.txt" in status  # still dirty, untouched
    assert "new_thread.txt" not in status  # committed

    # No changes → no new commit
    # 无变更 → 不产生新提交
    before = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout
    common.maybe_auto_commit(archive)
    after = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout
    assert before == after

    # No enclosing repo → skip without error
    # 无上层仓库 → 跳过不报错
    common.maybe_auto_commit(tmp_path / "nowhere")

    # auto_commit=false → skip
    # auto_commit=false → 跳过
    monkeypatch.setattr(cfg, "AUTO_COMMIT", False)
    (archive / "other.txt").write_text("x")
    common.maybe_auto_commit(archive)
    status = subprocess.run(["git", "-C", str(repo), "status", "--short"],
                            capture_output=True, text=True).stdout
    assert "other.txt" in status  # untouched
    monkeypatch.setattr(cfg, "AUTO_COMMIT", True)


def test_maybe_auto_commit_push_conflict_hard_error(tmp_path, monkeypatch):
    """A rejected push (non-fast-forward / conflict) must raise SystemExit —
    visible at any verbosity; a missing upstream is only a warning.

    Also the regression guard for the locale bug: with a localized git
    (zh_CN.UTF-8) the "no push destination" message is Chinese, and the
    English-only classifier would misread it as a conflict — _git pins
    LC_ALL=C so this stays a warning.

    push 被拒（non-fast-forward/冲突）必须 SystemExit——任何日志级别可见；
    无上游分支仅 warning。本测试同时守护 locale 缺陷：本地化 git（中文）下
    “未配置推送目标”为中文串，纯英文分类会误读为冲突——_git 固定 LC_ALL=C
    使其仍仅记 warning。"""
    import subprocess
    import pytest
    from pplx_export import config as cfg
    from pplx_export.commands import common

    monkeypatch.setattr(cfg, "AUTO_COMMIT", True)
    monkeypatch.setattr(cfg, "AUTO_PUSH", True)

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    archive = repo / "web_archive"
    archive.mkdir()

    # Simulate a rejected push (real repo, real commit; only push is mocked)
    # 模拟 push 被拒（真实仓库、真实 commit；仅 mock push 一次）
    real_push = common._git

    def fake_push(root, *args):
        if args and args[0] == "push":
            class R:
                returncode = 1
                stderr = "! [rejected] main -> main (fetch first)\n"
                stdout = ""
            return R()
        return real_push(root, *args)

    monkeypatch.setattr(common, "_git", fake_push)
    (archive / "x.txt").write_text("new")
    with pytest.raises(SystemExit):
        common.maybe_auto_commit(archive)
    # commit still happened before the hard exit
    # commit 在硬退出前已发生
    out = subprocess.run(["git", "-C", str(repo), "log", "--oneline", "-1"],
                         capture_output=True, text=True).stdout
    assert "archive: incremental snapshot" in out

    # Missing upstream → warning only, no SystemExit
    # 无上游分支 → 仅 warning，不 SystemExit
    monkeypatch.setattr(common, "_git", real_push)
    (archive / "y.txt").write_text("y")
    common.maybe_auto_commit(archive)  # must not raise
    monkeypatch.setattr(cfg, "AUTO_PUSH", False)
