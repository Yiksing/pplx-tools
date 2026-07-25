"""Tests for cmd: status (archive state summary and change report).

Offline: synthetic index/library files and batch_state under tmp_path; output is
captured via caplog (logger "cli") and stdout for --json.

cmd: status（归档状态账与变更报告）的测试。

全离线：tmp_path 下合成索引与 batch_state；经 caplog（"cli" logger）与
stdout（--json）捕获输出。
"""

import json
import logging
from types import SimpleNamespace

import pytest

from pplx_export.commands.status_cmd import cmd_status


def _row(uuid, lu, title, mode="SEARCH", sm="SEARCH"):
    """Build one library index row.

    构造一条 library 索引行。
    """
    return {"entryUUID": uuid, "lastUpdated": lu, "title": title,
            "mode": mode, "search_mode": sm}


def _rec(status, lu, exported, title):
    """Build one batch_state record.

    构造一条 batch_state 记录。
    """
    return {"status": status, "lastUpdated": lu,
            "exported_at": exported, "title": title}


@pytest.fixture
def archive(tmp_path):
    """Synthetic two-account archive: alice covers all five plan actions plus an
    error record, bob a single done thread; batch_state adds terminal, orphan and
    deleted records for the global/state-only views.

    合成双账户归档：alice 覆盖五种 plan 动作加一条 error 记录，bob 一条 done；
    batch_state 另有终态、孤儿与已删除记录（全局/state-only 视图用）。
    """
    index = tmp_path / "index"
    index.mkdir()
    alice_rows = [
        _row("u-err-1", "2026-07-26T00:00:00Z", "失败对话甲"),
        _row("u-new-1", "2026-07-25T00:00:00Z", "新对话乙"),
        _row("u-upd-1", "2026-07-24T00:00:00Z", "变更对话丙"),
        _row("u-done-1", "2026-07-23T00:00:00Z", "完成对话丁"),
        _row("u-exp-1", "2026-07-22T00:00:00Z", "过期对话戊"),
    ]
    (index / "library_alice.json").write_text(json.dumps({"threads": alice_rows}))
    (index / "library_bob.json").write_text(
        json.dumps({"threads": [_row("u-done-2", "2026-07-23T00:00:00Z", "完成对话己")]}))
    state = {
        "u-upd-1": _rec("ok", "2026-07-20T00:00:00Z", "2026-07-21T00:00:00Z", "变更对话丙"),
        "u-done-1": _rec("ok", "2026-07-23T00:00:00Z", "2026-07-23T01:00:00Z", "完成对话丁"),
        "u-exp-1": _rec("expired", "2026-07-22T00:00:00Z", "2026-06-01T00:00:00Z", "过期对话戊"),
        "u-done-2": _rec("ok", "2026-07-23T00:00:00Z", "2026-07-23T02:00:00Z", "完成对话己"),
        "u-err-1": _rec("error", "2026-07-20T00:00:00Z", "2026-07-21T00:00:00Z", "失败对话甲"),
        "u-del-1": _rec("deleted", "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z", "已删对话庚"),
        "u-orphan": _rec("ok", "2026-07-10T00:00:00Z", "2026-07-11T00:00:00Z", "孤儿记录辛"),
    }
    (index / "batch_state.json").write_text(json.dumps(state))
    return tmp_path


def _args(archive, verbose=0, account=None, as_json=False):
    """Assemble a cmd_status args namespace.

    组装 cmd_status 的参数命名空间。
    """
    return SimpleNamespace(account=account, out=archive, verbose=verbose, json=as_json)


def test_info_summary(archive, caplog):
    """INFO tier: per-account summary lines and the global batch_state account.

    INFO 层：分账户摘要行与全局 batch_state 状态账。
    """
    with caplog.at_level(logging.INFO, logger="pplx_export.cli"):
        cmd_status(_args(archive), archive)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert ("账户 alice：索引 5" in text and "ok 1 + expired 1 + deleted 0 + error 1" in text
            and "变更 new 1 / updated 2 / 早停 2" in text)
    assert "账户 bob：索引 1" in text and "变更 new 0 / updated 0 / 早停 1" in text
    assert "全局 batch_state：4 ok + 1 expired + 1 deleted + 1 error" in text
    # INFO must not leak detail titles
    # INFO 层不得泄露明细标题
    assert "新对话乙" not in text


def test_v_titles(archive, caplog):
    """-v tier: new/updated/error titles appear, done/expired/deleted stay hidden.

    -v 层：出现 new/updated/error 标题，done/expired/deleted 明细不出现。
    """
    with caplog.at_level(logging.DEBUG, logger="pplx_export.cli"):
        cmd_status(_args(archive, verbose=1), archive)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[status][new] u-new-1" in text and "新对话乙" in text
    assert text.count("[status][updated]") == 2
    assert "[status][error] u-err-1" in text and "将作为 updated 重导" in text
    assert "[status][done]" not in text and "[status][expired]" not in text


def test_vv_details(archive, caplog):
    """-vv tier: done/expired lines carry lastUpdated and exported_at.

    -vv 层：done/expired 明细行带 lastUpdated 与 exported_at。
    """
    with caplog.at_level(logging.DEBUG, logger="pplx_export.cli"):
        cmd_status(_args(archive, verbose=2), archive)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[status][done] u-done-1" in text and "exported_at=2026-07-23T01:00:00Z" in text
    assert "[status][expired] u-exp-1" in text
    assert "[status][deleted]" not in text


def test_vvv_full(archive, caplog):
    """-vvv tier: index fields shown and state-only lists the orphan, not the
    deleted record.

    -vvv 层：展示索引字段；state-only 列出孤儿记录而不含已删除记录。
    """
    with caplog.at_level(logging.DEBUG, logger="pplx_export.cli"):
        cmd_status(_args(archive, verbose=3), archive)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "mode=SEARCH search_mode=SEARCH" in text
    assert "[status][state-only] u-orphan" in text and "孤儿记录辛" in text
    assert "[status][state-only] u-del-1" not in text


def test_json_report(archive, capsys):
    """--json: stdout carries the full machine-readable report.

    --json：stdout 输出完整机器可读报告。
    """
    cmd_status(_args(archive, as_json=True), archive)
    report = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert report["totals"] == {"ok": 4, "expired": 1, "deleted": 1, "error": 1}
    alice = next(a for a in report["accounts"] if a["username"] == "alice")
    assert alice["changes"] == {"new": 1, "updated": 2, "n_stopped": 2}
    assert alice["state"] == {"ok": 1, "expired": 1, "deleted": 0, "error": 1}
    assert {t["action"] for t in alice["threads"]} == {"new", "updated", "done", "expired"}
    assert [s["uuid"] for s in report["state_only"]] == ["u-orphan"]


def test_account_filter(archive, caplog):
    """--account limits output to one account; an unknown account errors out.

    --account 只输出单账户；未知账户报错退出。
    """
    with caplog.at_level(logging.INFO, logger="pplx_export.cli"):
        cmd_status(_args(archive, account="bob"), archive)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "账户 bob" in text and "账户 alice" not in text
    with pytest.raises(SystemExit):
        cmd_status(_args(archive, account="carol"), archive)


def test_missing_index_dir(tmp_path):
    """Missing index directory -> SystemExit pointing at pplx-export index.

    索引目录缺失 -> 报错指向 pplx-export index。
    """
    with pytest.raises(SystemExit, match="pplx-export index"):
        cmd_status(_args(tmp_path), tmp_path)


def test_missing_state_file(archive, caplog):
    """Missing batch_state.json: every thread is new and totals are zero.

    batch_state.json 缺失：全部线程判 new，状态账为零。
    """
    (archive / "index" / "batch_state.json").unlink()
    with caplog.at_level(logging.INFO, logger="pplx_export.cli"):
        cmd_status(_args(archive), archive)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "变更 new 5 / updated 0 / 早停 0" in text
    assert "全局 batch_state：0 ok + 0 expired + 0 deleted + 0 error" in text
