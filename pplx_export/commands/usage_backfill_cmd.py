"""cmd: usage-backfill — backfill credit usage records (credits/thread-usage).

cmd：usage-backfill —— 补全积分用量记录（credits/thread-usage）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..core.logging import get_logger

log = get_logger("cli")


def cmd_usage_backfill(adapter, account, out_root: Path, limit):
    """Backfill credit usage records for all threads of the account
    (credits/thread-usage, thread_id uses psc_uuid, i.e. the platform context_uuid).

    Idempotent: already-recorded threads are skipped; 403 (cross-account) is recorded
    as error and not retried; other exceptions are left for the next round.
    Output: web_archive/index/credit_usage_<account>.json.

    补全账户全部线程的积分用量记录（credits/thread-usage，thread_id 用 psc_uuid，即平台 context_uuid）。

    幂等：已记录的线程跳过；403（跨账户）记 error 不重试；其他异常保留待下轮。
    输出 web_archive/index/credit_usage_<account>.json。
    """
    idx_dir = out_root / "index"
    out_path = idx_dir / f"credit_usage_{account.username}.json"
    records: dict = {}
    if out_path.exists():
        try:
            records = json.loads(out_path.read_text())
        except Exception:
            records = {}
    folder = account.folder
    thread_dirs = sorted(out_root.glob(f"{folder}/*/*/thread.json"))
    if limit:
        thread_dirs = thread_dirs[:limit]
    ok = skip = err = zero = 0
    for i, tj in enumerate(thread_dirs, 1):
        try:
            d = json.loads(tj.read_text())
        except Exception:
            continue
        wu = d.get("web_uuid") or ""
        psc = d.get("psc_uuid") or ""
        if not wu or not psc:
            continue
        if wu in records:
            skip += 1
            continue
        try:
            j = adapter.transport.get_json(
                f"https://www.perplexity.ai/rest/billing/credits/thread-usage"
                f"?thread_id={psc}&version=2.18&source=default", timeout=30)
            records[wu] = {"psc_uuid": psc, "usage_cents": j.get("usage_cents"),
                           "meter_usage": j.get("meter_usage") or [],
                           "mode": d.get("mode"), "title": (d.get("title") or "")[:80],
                           "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            ok += 1
            if not j.get("usage_cents"):
                zero += 1
            log.info(f"[usage {i}/{len(thread_dirs)}] {(d.get('title') or '')[:40]} "
                  f"→ {j.get('usage_cents') or 0:.0f} cents")
        except Exception as e:
            msg = str(e)
            if "403" in msg or "thread_usage_forbidden" in msg:
                records[wu] = {"psc_uuid": psc, "error": "forbidden（非本账户线程）",
                               "mode": d.get("mode"),
                               "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                err += 1
            else:
                log.warning(f"[usage] {wu[:8]}: {msg[:80]}（下轮重试）")
        time.sleep(3.0)
        # Trigger the mid-run save based on the actually processed count (ok+err,
        # including forbidden entries recorded in records): skipped entries continue
        # before i%25, so on incremental reruns (mostly already recorded) the global
        # i rarely lands on a multiple of 25
        # 按实际处理数（ok+err，含 forbidden 记 records 的条目）触发中途落盘：
        # 跳过项在 i%25 前 continue，增量重跑（多数已记录）时全局 i 几乎不落在 25 倍数上
        if (ok + err) % 25 == 0:
            idx_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(records, ensure_ascii=False, indent=1))
            log.info(f"[usage {i}/{len(thread_dirs)}] ok={ok} skip={skip} err={err}")
    idx_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=1))
    log.info(f"[usage] 完成: ok={ok}（其中 0 用量 {zero}）skip={skip} err={err} → {out_path}")


