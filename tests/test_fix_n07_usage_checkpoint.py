"""N-07 regression: usage-backfill's mid-run flush is triggered by the actual
processed count (ok+err).

Scenario: most threads already recorded (skipped) + a few new ones. The new
threads' global indices i all avoid multiples of 25 (the old formula
`i % 25 == 0` never flushed mid-run); verifies the new formula
`(ok + err) % 25 == 0` triggers one mid-run checkpoint at the 25th actually
processed item. Fully offline: fake transport + tmp_path, no network.

N-07 回归测试：usage-backfill 中途落盘按实际处理数（ok+err）触发。

场景：多数线程已记录（跳过）+ 少量新增。构造使新增线程的全局序号 i
均避开 25 的倍数（旧口径 `i % 25 == 0` 中途绝不落盘），验证新口径
`(ok + err) % 25 == 0` 在第 25 个实际处理项处触发一次中途 checkpoint。
全离线：fake transport + tmp_path，不打网络。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pplx_export.commands.usage_backfill_cmd import cmd_usage_backfill

FOLDER = "Acc"
# Simulates a cross-account 403: recorded as error and written into records
# 模拟跨账户 403：记 error 并写入 records
FORBIDDEN_PSC = "p030"


class FakeTransport:
    def get_json(self, url, timeout=30):
        if FORBIDDEN_PSC in url:
            raise RuntimeError("403 thread_usage_forbidden")
        return {"usage_cents": 123, "meter_usage": []}


def _make_thread(out_root: Path, n: int) -> None:
    d = out_root / FOLDER / "search" / f"t{n:03d}_标题_t{n:03d}"
    d.mkdir(parents=True)
    (d / "thread.json").write_text(json.dumps(
        {"web_uuid": f"w{n:03d}", "psc_uuid": f"p{n:03d}",
         "mode": "search", "title": f"标题{n}"}))


def _run(out_root: Path):
    account = SimpleNamespace(folder=FOLDER, username="acc")
    adapter = SimpleNamespace(transport=FakeTransport())
    out_path = out_root / "index" / f"credit_usage_{account.username}.json"
    # Snapshot of the records count at each flush
    # 每次落盘时 records 的条目数快照
    writes: list[int] = []
    orig_write = Path.write_text
    # Since V6 flushes go through fsio.atomic_write_text (hidden same-directory
    # temp + os.replace); observe the temp write of out_path
    # V6 起落盘经 fsio.atomic_write_text（同目录隐藏临时文件 + os.replace）；
    # 探针改观测 out_path 的临时文件写入
    tmp_path_of_out = out_path.with_name(f".{out_path.name}.tmp")

    def spy(self, data, *a, **kw):
        if self == tmp_path_of_out:
            writes.append(len(json.loads(data)))
        return orig_write(self, data, *a, **kw)

    with patch.object(Path, "write_text", spy), \
         patch("pplx_export.commands.usage_backfill_cmd.time.sleep"):
        cmd_usage_backfill(adapter, account, out_root, None)
    return out_path, writes


def test_checkpoint_triggers_on_processed_count(tmp_path):
    # 51 threads: i=1..25 already recorded (skipped), i=26..49 new (24),
    # i=50 already recorded (skipped), i=51 new (1) — 25 actually processed
    # items in total. The new items' global i ∈ {26..49, 51} are never
    # multiples of 25: under the old i%25 formula there was no mid-run flush
    # (only the final write).
    # 51 线程：i=1..25 已记录（跳过），i=26..49 新增（24 个），
    # i=50 已记录（跳过），i=51 新增（1 个）——共 25 个实际处理项。
    # 新增项的全局 i ∈ {26..49, 51}，均非 25 倍数：旧口径 i%25 中途不落盘（仅末尾 1 次写）。
    for n in range(1, 52):
        _make_thread(tmp_path, n)
    idx = tmp_path / "index"
    idx.mkdir()
    pre = {f"w{n:03d}": {"psc_uuid": f"p{n:03d}", "usage_cents": 1}
           for n in list(range(1, 26)) + [50]}
    (idx / "credit_usage_acc.json").write_text(json.dumps(pre))

    out_path, writes = _run(tmp_path)

    # New formula: the 25th actually processed item (ok=24 + err=1) triggers
    # one mid-run flush + the final write = 2 writes
    # 新口径：第 25 个实际处理项（ok=24 + err=1）触发一次中途落盘 + 末尾终写 = 2 次
    assert len(writes) == 2, f"中途 checkpoint 未触发（落盘次数={len(writes)}）"
    # At the mid-run flush, 26 old records + 25 newly processed (incl. the
    # forbidden one) are all present in records
    # 中途落盘时 26 条旧记录 + 25 条新处理（含 forbidden）已全部在 records 中
    assert writes[0] == 51

    # ok/err counts match the records writes: all 51 entries; the forbidden
    # entry carries an error field
    # ok/err 计数与 records 写入一致：51 条全量，forbidden 条带 error 字段
    records = json.loads(out_path.read_text())
    assert len(records) == 51
    assert records["w030"]["error"].startswith("forbidden")
    assert "usage_cents" not in records["w030"]
    assert records["w051"]["usage_cents"] == 123


def test_checkpoint_not_triggered_below_25_processed(tmp_path):
    # Fewer than 25 actually processed items: only the final write (same as
    # the old behavior, no extra writes)
    # 少于 25 个实际处理项：只末尾终写一次（与旧行为一致，不多写）
    for n in range(1, 11):
        _make_thread(tmp_path, n)
    _, writes = _run(tmp_path)
    assert len(writes) == 1
    assert writes[0] == 10
