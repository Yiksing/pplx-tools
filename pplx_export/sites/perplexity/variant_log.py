"""Detection logging and central registry for answer-rewrite variants (ANSWER_VARIANT_DETECTED).

Background (precedent in docs/reference/api/api-responses-errors.md §5.2): after the platform rewrites an
answer, the web side keeps only the currently effective version; alternate variants
are invisible on the API side, and sibling threads are proven dead links (403
VIEW_THREAD_NOT_ALLOWED on both accounts + browser redirect to the home page) — a hit
usually cannot be remedied via the API. This module's value is therefore "alert at
first sight + guide manual handling", preserving evidence manually before the
platform purges it for good.

Two outputs:
- Log: single WARNING line with the uniform grep-able marker
  ANSWER_VARIANT_DETECTED, carrying all locating fields (full thread uuid + uuid8,
  title, entry_uuid, sibling_uuid, selection_status, experiment_role) plus handling
  guidance;
- Registry: <out>/index/answer_variants_log.jsonl (an archived data file, not a
  logs/ runtime log), deduped by (web_uuid, entry_uuid) — re-exports/re-renders do
  not append endlessly; detected_at keeps the first-seen time.

答案重写变体的检测日志与集中登记（ANSWER_VARIANT_DETECTED）。

背景（先例见 docs/reference/api/api-responses-errors.md §5.2）：平台重写答案后网页端只保留
当前生效版本，备选变体在 API 侧不可见，sibling 线程已实证为死链（双账户 403
VIEW_THREAD_NOT_ALLOWED + 浏览器重定向首页）——命中后通常无法经 API 补救。
因此本模块的价值是「第一时间告警 + 指引人工处置」，赶在平台彻底清理前人工留存。

两处产出：
- 日志：WARNING 级单行，统一可 grep 标记 ANSWER_VARIANT_DETECTED，含全部定位字段
  （thread 全量 uuid + uuid8、标题、entry_uuid、sibling_uuid、selection_status、
  experiment_role）与处置指引；
- 登记：<out>/index/answer_variants_log.jsonl（入库文件，非 logs/ 运行日志），
  按 (web_uuid, entry_uuid) 去重——重复导出/重渲不无限追加，detected_at 保留首见时间。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ...core.logging import get_logger

log = get_logger("variants")

MARKER = "ANSWER_VARIANT_DETECTED"

GUIDANCE = ("处置：备选答案已被平台替换，sibling 已实证多为死链（API 不可补救）——"
            "请尽快人工确认备选答案是否仍可获取并人工补录留存；登记见 "
            "thread.json.answer_variants 与 "
            "index/answer_variants_log.jsonl；字段语义与补录流程见 docs/reference/api/api-responses-errors.md §5.2")


def format_detection(web_uuid: str, title: str, rec: dict) -> str:
    """Single-line warning text: MARKER + all locating fields + handling guidance (title is JSON-quoted to survive spaces).

    单行告警文本：MARKER + 全部定位字段 + 处置指引（title 经 JSON 引号防空格断词）。
    """
    return (f"{MARKER} thread={web_uuid} uuid8={(web_uuid or '')[:8]} "
            f"title={json.dumps(title or '', ensure_ascii=False)} "
            f"entry={rec.get('entry_uuid', '')} sibling={rec.get('sibling_uuid', '')} "
            f"selection_status={rec.get('selection_status') or 'UNSPECIFIED'} "
            f"experiment_role={rec.get('experiment_role') or ''} | {GUIDANCE}")


def warn_detections(web_uuid: str, title: str, variants: list[dict]) -> None:
    """Emit one WARNING line per hit. Online fetching (adapter.get_thread) calls this
    on every actual hit; offline re-render calls it only after the caller determines
    "registry content newly added/changed" (idempotent reruns without log spam).

    每条命中输出一行 WARNING。在线抓取（adapter.get_thread）每次实际命中都调用；
    离线 re-render 由调用方判「登记内容新增/变化」后才调用（幂等重跑不刷屏）。"""
    for rec in variants or []:
        log.warning(format_detection(web_uuid, title, rec))


def append_registry(out_root: Path, web_uuid: str, title: str, variants: list[dict],
                    source: str) -> int:
    """Append hits to <out_root>/index/answer_variants_log.jsonl (deduped by thread+entry).

    source: online (real export) / offline (re-render). Already-registered
    (web_uuid, entry_uuid) pairs are not appended again; detected_at keeps the
    first-seen time. Returns the number of newly registered entries.

    追加命中到 <out_root>/index/answer_variants_log.jsonl（按 thread+entry 去重）。

    source：online（真实导出）/ offline（re-render 离线重渲）。已登记的
    (web_uuid, entry_uuid) 不重复追加，detected_at 保留首见时间。返回新登记条数。
    """
    if not variants:
        return 0
    p = Path(out_root) / "index" / "answer_variants_log.jsonl"
    seen: set[tuple] = set()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                # Skip bad lines without crashing (registry fault tolerance).
                # 坏行跳过不崩（登记处容错）
                continue
            seen.add((j.get("web_uuid"), j.get("entry_uuid")))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new: list[dict] = []
    for rec in variants:
        key = (web_uuid, rec.get("entry_uuid", ""))
        if key in seen:
            continue
        seen.add(key)
        new.append({"detected_at": now, "source": source,
                    "web_uuid": web_uuid, "uuid8": (web_uuid or "")[:8],
                    "title": title or "",
                    "entry_uuid": rec.get("entry_uuid", ""),
                    "sibling_uuid": rec.get("sibling_uuid", ""),
                    "selection_status": rec.get("selection_status", ""),
                    "experiment_role": rec.get("experiment_role", "")})
    if not new:
        return 0
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for j in new:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    return len(new)
