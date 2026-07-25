"""N-10 regression: WORKFLOW_ITEM_TABLE header escaping of | and newlines
(aligned with the cell handling at :182/:190).

Finding: render.py:173 header concatenation did not apply
.replace("|","｜").replace("\\n"," "), so column names containing | or
newlines broke the markdown table structure.

N-10 回归：WORKFLOW_ITEM_TABLE 列头转义 | 与换行（与单元格 :182/:190 对齐）。

发现：render.py:173 列头拼接未做 .replace("|","｜").replace("\\n"," ")，
含 | 或换行的列名会破坏 markdown 表格结构。
"""
from pplx_export.sites.perplexity.render import render_wf_item


def _table(columns, rows):
    return {"type": "WORKFLOW_ITEM_TABLE",
            "payload": {"table_payload": {"columns": columns, "rows": rows}}}


def _split_row(line: str) -> list:
    # Split a markdown table row on bare | (including the leading/trailing separators)
    # markdown 表格行按裸 | 切分（含首尾分隔符）
    return line.split("|")


class TestN10TableHeaderEscape:
    def test_pipe_in_header_escaped(self):
        it = _table(["a|b", "c"], [{"cells": {"a|b": "1", "c": "2"}}])
        out = render_wf_item(it)
        header = out.splitlines()[0]
        assert "｜" in header and "a|b" not in header
        # Column count check: a row split on bare | should yield len(cols)+2
        # segments (leading/trailing empty strings + one per column)
        # 列数一致：行按裸 | 切分后应有 len(cols)+2 段（首尾空串 + 各列）
        assert len(_split_row(header)) == len(["a|b", "c"]) + 2
        body = out.splitlines()[2]
        assert len(_split_row(body)) == len(_split_row(header))

    def test_newline_in_header_escaped(self):
        it = _table(["a\nb", "c"], [["1", "2"]])
        out = render_wf_item(it)
        lines = out.splitlines()
        # Header newlines are replaced with spaces: the whole table is still
        # 1 header + 1 separator + 1 data row
        # 列头换行被替换为空格：整张表仍是 1 表头 + 1 分隔 + 1 行数据
        assert len(lines) == 3
        assert lines[0].startswith("| a b | c |")

    def test_structure_intact_with_bare_pipe_and_newline(self):
        cols = ["x|y", "z\nw", "plain"]
        rows = [{"cells": {"x|y": {"value": "v|1"}, "z\nw": "v2", "plain": "v3"}},
                ["r|2", "r2\nline", "r3"]]
        out = render_wf_item(_table(cols, rows))
        lines = out.splitlines()
        assert len(lines) == 1 + 1 + len(rows), "表格行数完整（表头+分隔+数据行）"
        for i, line in enumerate(lines):
            if i == 1:
                # Separator row
                # 分隔行
                continue
            segs = _split_row(line)
            assert len(segs) == len(cols) + 2, f"第 {i} 行列数不一致: {line!r}"
        # Data-row cell escaping behavior unchanged (existing escaping at :182/:190)
        # 数据行单元格转义行为未变（:182/:190 既有转义）
        assert "v｜1" in out and "r｜2" in out
