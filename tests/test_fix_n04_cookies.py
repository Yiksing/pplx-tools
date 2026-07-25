"""N-04 regression: domain-suffix matching in from_file's JSON-list branch
(covers the F-11 gap).

- evilperplexity.ai / perplexity.ai.attacker.com must not be collected
  (substring matching would false-positive on them)
- .perplexity.ai / www.perplexity.ai are collected
- entries missing the name/value keys are skipped without raising KeyError
Fully offline: operates only on tmp_path temporary files.

N-04 回归测试：from_file 的 JSON-list 分支域后缀匹配（补 F-11 遗漏）。

- evilperplexity.ai / perplexity.ai.attacker.com 不被采（子字符串匹配会误采）
- .perplexity.ai / www.perplexity.ai 被采
- 缺 name/value 键的条目跳过，不抛 KeyError
全离线：仅操作 tmp_path 临时文件。
"""

import json

from pplx_export.core.cookies import _domain_match, from_file


def _write_json(tmp_path, entries):
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps(entries))
    return p


class TestDomainMatchPredicate:
    """Module-level shared predicate: used by all three import paths
    (browser / JSON-list / Netscape).

    模块级共享谓词：三处导入路径（browser/JSON-list/Netscape）共用。"""

    def test_exact_and_subdomain_hit(self):
        assert _domain_match("perplexity.ai", "perplexity.ai")
        assert _domain_match(".perplexity.ai", "perplexity.ai")
        assert _domain_match("www.perplexity.ai", "perplexity.ai")
        assert _domain_match(".www.perplexity.ai", "perplexity.ai")

    def test_substring_impostors_rejected(self):
        assert not _domain_match("evilperplexity.ai", "perplexity.ai")
        assert not _domain_match("perplexity.ai.attacker.com", "perplexity.ai")
        assert not _domain_match("notperplexity.ai", "perplexity.ai")
        assert not _domain_match("", "perplexity.ai")


class TestFromFileJsonListBranch:
    def test_impostor_domains_not_collected(self, tmp_path):
        p = _write_json(tmp_path, [
            {"name": "good", "value": "1", "domain": "perplexity.ai"},
            {"name": "evil", "value": "2", "domain": "evilperplexity.ai"},
            {"name": "atk", "value": "3", "domain": "perplexity.ai.attacker.com"},
        ])
        out = from_file(p)
        assert out == {"good": "1"}, f"冒名域不得被采: {out}"

    def test_dot_and_subdomain_collected(self, tmp_path):
        p = _write_json(tmp_path, [
            {"name": "a", "value": "1", "domain": ".perplexity.ai"},
            {"name": "b", "value": "2", "domain": "www.perplexity.ai"},
            {"name": "c", "value": "3", "domain": ".www.perplexity.ai"},
        ])
        out = from_file(p)
        assert out == {"a": "1", "b": "2", "c": "3"}

    def test_missing_keys_skipped_no_keyerror(self, tmp_path):
        # Entries below: missing name / missing value / missing both — all skipped
        # 以下条目分别缺 name / 缺 value / 缺 name+value —— 均应跳过
        p = _write_json(tmp_path, [
            {"name": "ok", "value": "1", "domain": "perplexity.ai"},
            {"value": "2", "domain": "perplexity.ai"},
            {"name": "no_value", "domain": "perplexity.ai"},
            {"domain": "perplexity.ai"},
        ])
        # Must not raise KeyError
        # 不抛 KeyError
        out = from_file(p)
        assert out == {"ok": "1"}

    def test_missing_domain_not_collected(self, tmp_path):
        p = _write_json(tmp_path, [
            {"name": "nodom", "value": "1"},
            {"name": "ok", "value": "2", "domain": "perplexity.ai"},
        ])
        out = from_file(p)
        assert out == {"ok": "2"}
