"""V3-01 regression: _render_nested_wf renders the text_payload body of
WORKFLOW_ITEM_SOURCES.

Finding: when a nested workflow_payload (stub-turn sub-agent / background
appendix / nested recursion) is rendered via _render_nested_wf, the SOURCES
branch only collected URLs into the trailing citations and then continued —
the text_payload (the sub-agent's extracted page body / comparison tables)
was dropped, while the top-level render_wf_item keeps the body for the same
item kind. Fix: the SOURCES branch renders text_payload into the step inline
first; the URL collection logic is unchanged.

V3-01 回归：_render_nested_wf 渲染 WORKFLOW_ITEM_SOURCES 的 text_payload 正文。

发现：嵌套 workflow_payload（桩轮子代理 / 后台附录 / 嵌套递归）经 _render_nested_wf
渲染时，SOURCES 分支只收 URL 到末尾引文就 continue，text_payload（子代理对页面的
提取正文/对比表）被丢弃；而顶层 render_wf_item 对同类 item 会保留正文。
修复：SOURCES 分支先渲染 text_payload 进步骤内联，URL 收集逻辑不变。
"""
from pplx_export.sites.perplexity.render import _render_nested_wf, render_wf_item


def _sources_item(text=None, chunks=None, urls=()):
    tp = {}
    if text is not None:
        tp["text"] = text
    if chunks is not None:
        tp["chunks"] = chunks
    return {"type": "WORKFLOW_ITEM_SOURCES",
            "payload": {"text_payload": tp,
                        "sources_payload": {"sources": [
                            {"name": f"来源{i}", "url": u} for i, u in enumerate(urls)]}}}


def _nested_wf(items):
    return {"id": "toolu_test_v301", "headline": "测试子代理", "status": "WORKFLOW_COMPLETED",
            "steps": [{"title": "读取页面", "tool_name": "get_url_content", "items": items}]}


class TestV301NestedSourcesText:
    def test_text_payload_rendered_inline_and_urls_at_end(self):
        wp = _nested_wf([_sources_item(text="## 提取正文\n\n- 关键结论 A",
                                       urls=["https://a.example/1", "https://b.example/2"])])
        out = _render_nested_wf(wp)
        # The body goes into the step inline (inside the collapsed-block body
        # section, instead of being dropped)
        # 正文进入步骤内联（在折叠块 body 段，而非被丢弃）
        assert "## 提取正文" in out and "关键结论 A" in out
        # URLs are still aggregated into the trailing citations section, without
        # dedup-related loss
        # URL 仍聚合到末尾引文段，且不去重丢失
        assert "**引文：**" in out
        assert "- [来源0](https://a.example/1)" in out
        assert "- [来源1](https://b.example/2)" in out
        # The body appears before the citations section (step-inline position)
        # 正文出现在引文段之前（步骤内联位置）
        assert out.index("## 提取正文") < out.index("**引文：**")

    def test_chunks_fallback_rendered(self):
        wp = _nested_wf([_sources_item(chunks=["| 项目 | 值 |", "\n| a | b |"],
                                       urls=["https://c.example/"])])
        out = _render_nested_wf(wp)
        assert "| 项目 | 值 |" in out and "| a | b |" in out
        assert "- [来源0](https://c.example/)" in out

    def test_math_delims_normalized(self):
        wp = _nested_wf([_sources_item(text="公式 \\(x^2\\) 与 \\[y=1\\]")])
        out = _render_nested_wf(wp)
        assert "\\(" not in out and "\\[" not in out
        assert "$x^2$" in out

    def test_no_text_payload_zero_diff(self):
        # Without text_payload (or with blank content) behavior matches the
        # pre-fix version: the step has no renderable body and degrades to a
        # headline list, while URLs are still aggregated into the trailing citations
        # 无 text_payload（或空白）时行为与修复前一致：步骤无可渲染 body，
        # 退化为标题列表，URL 照常聚合到末尾引文
        for tp in ({}, {"text": ""}, {"text": "  \n "}, {"chunks": []}):
            it = {"type": "WORKFLOW_ITEM_SOURCES",
                  "payload": {"text_payload": tp,
                              "sources_payload": {"sources": [
                                  {"name": "n", "url": "https://d.example/"}]}}}
            out = _render_nested_wf(_nested_wf([it]))
            # Headline-only degraded list
            # 仅标题退化列表
            assert "- 读取页面（`get_url_content`）" in out
            assert "**引文：**" in out
            assert "- [n](https://d.example/)" in out
            assert "<details>" in out and "</details>" in out

    def test_url_dedup_unchanged(self):
        # The second item carries a duplicate URL
        # 第二项携带重复 URL
        items = [_sources_item(text="正文甲", urls=["https://e.example/", "https://f.example/"]),
                 _sources_item(text="正文乙", urls=["https://e.example/"])]
        out = _render_nested_wf(_nested_wf(items))
        assert "正文甲" in out and "正文乙" in out
        # Dedup-by-url logic unchanged
        # 按 url 去重逻辑不变
        assert out.count("https://e.example/") == 1

    def test_via_render_wf_item_recursion(self):
        # Entered via render_wf_item's WORKFLOW_ITEM_WORKFLOW branch recursion
        # (the real call path)
        # 经 render_wf_item 的 WORKFLOW_ITEM_WORKFLOW 分支递归进入（实际调用路径）
        it = {"type": "WORKFLOW_ITEM_WORKFLOW",
              "payload": {"workflow_payload": _nested_wf(
                  [_sources_item(text="嵌套正文", urls=["https://g.example/"])])}}
        out = render_wf_item(it)
        assert "嵌套正文" in out
        assert "- [来源0](https://g.example/)" in out
