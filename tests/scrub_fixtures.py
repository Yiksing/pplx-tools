#!/usr/bin/env python3
"""Deterministic maintenance tool for tests/fixtures/: positional replacement,
identifier remapping, and golden snapshot regeneration.

Usage:
    uv run python tests/scrub_fixtures.py [--check]

Design principles:
- **No environment-specific literals committed**. Account identities
  (username / display name / email / user_id / BOT space) are read at runtime
  from the user-level config (pplx_export.config →
  ~/.config/pplx-export/config.toml); content-class replacement sources are
  read from a local override mapping `tests/scrub_pairs.local.json` (not
  committed; template: `tests/scrub_pairs.example.json`). This script itself
  embeds no environment-specific literals.
- **Positional extraction**: titles / queries / related_queries / Q&A
  payloads / space fields are pulled from each fixture's JSON structure by
  path and paired with the **synthetic replacement values** configured in this
  script (generic, no personal information).
- **Deterministic UUID mapping**: every remaining UUID → a uuid5 synthetic
  value tagged with the `5cbeef00` prefix, consistent repo-wide (the same
  input always maps to the same output, preserving cross-references); values
  already carrying the marker prefix are skipped (idempotent).
- **toolu_ run ids** → sha256-derived synthetic ids tagged with `5crub0`
  (fixed 24-char length, idempotent skip).
- **read_write_token** → one fixed placeholder value; CloudFront/S3 signed
  URLs have their query strings stripped.
- After replacement, golden/ is **regenerated** via the pplx_export offline
  rerender (keeping snapshots byte-identical), then a zero-residue gate runs.
  Repeatable and idempotent.

Replacement scope: positional pairs apply only inside their fixture directory;
local content pairs and identity / token / UUID / toolu_ mappings apply globally.

---

tests/fixtures/ 的确定性维护工具：位置式替换、标识符重映射与 golden 快照重生成。

用法：
    uv run python tests/scrub_fixtures.py [--check]

设计原则：
- **环境相关字面量一律不入库**。账户身份（用户名/显示名/email/user_id/BOT
  空间）运行时读自用户级配置（pplx_export.config →
  ~/.config/pplx-export/config.toml）；内容类替换源读自本地覆盖映射
  `tests/scrub_pairs.local.json`（不入库，模板见
  `tests/scrub_pairs.example.json`）。本脚本自身不内嵌任何环境相关字面量。
- **位置式提取**：标题/query/related_queries/问答负载/空间字段等从 fixtures
  的 JSON 结构中按路径取出，与脚本内配置的**合成替换值**配对（通用、无个人信息）。
- **确定性 UUID 映射**：其余 UUID → 带 `5cbeef00` 前缀标记的 uuid5 合成值，
  全库一致（同一原值处处同新值，保关联性）；已带标记前缀的值跳过（幂等）。
- **toolu_ 运行 id** → 带 `5crub0` 标记的 sha256 合成 id（等长 24 位，幂等跳过）。
- **read_write_token** → 统一固定占位值；CloudFront/S3 签名 URL 剥离查询串。
- 替换完成后用 pplx_export 离线 rerender **重生成 golden/**（保证快照逐字节一致），
  最后跑零残留门禁。可重复运行，幂等。

替换作用域：位置式对只作用于所属 fixture 目录；本地内容对与身份/token/UUID/toolu_ 映射全局作用。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import uuid as uuidlib
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"
PAIRS_LOCAL = TESTS_DIR / "scrub_pairs.local.json"
RAW_NAMES = ("raw_entries.json", "raw_blocks.json", "thread.json")

# ── Shared placeholders (aligned with the pplx-tools migration convention; all synthetic, committable)
# Assigned in order of sorted account usernames
# ── 共享占位符（与 pplx-tools 迁移约定一致；均为合成值，可入库）────────────────
# 按账户用户名排序依次指派
PLACEHOLDER_ACCOUNTS = [
    {"key": "alice", "display": "Alice Example", "email": "alice@example.com",
     "uid": "00000000-0000-4000-8000-0000000000aa"},
    {"key": "bob", "display": "Bob Example", "email": "bob@example.com",
     "uid": "00000000-0000-4000-8000-0000000000bb"},
]
FAKE_TOKEN = "00000000-0000-4000-8000-0000000000ff"
BOT_PLACEHOLDER_UUID = "00000000-0000-4000-8000-0000000000b0"
BOT_PLACEHOLDER_SLUG = "bot-EXAMPLE"

# Synthetic UUID marker prefix (hex; natural collision probability 2^-32)
# 合成 UUID 标记前缀（hex，自然碰撞概率 2^-32）
UUID_MARK = "5cbeef00"
# Synthetic toolu_ id marker prefix (base62)
# 合成 toolu_ id 标记前缀（base62）
TOOLU_MARK = "5crub0"
UUID_NS = uuidlib.UUID("12345678-1234-5678-1234-567812345678")
UUID_SALT = "pplx-cli-fixture-scrub/"

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TOOLU_RE = re.compile(r"toolu_[0-9A-Za-z]{24}\b")
TOKEN_RE = re.compile(r'"read_write_token":\s*"([0-9a-f-]{36})"')
SIGNED_URL_RE = re.compile(
    r"(https://[A-Za-z0-9.-]*(?:cloudfront\.net|amazonaws\.com)[^\"?\\\s]*)\?[^\"\\\s]*")

# ── Synthetic replacement text per fixture (generic synthetic content only, committable)
# title/queries are paired positionally with the fixture's current values;
# None = keep as-is (already judged generic synthetic content).
# ── 各 fixture 的合成新文本（仅含通用合成内容，可入库）────────────────────────
# title/queries 按位置与 fixtures 中现有值配对；None = 保留原值（已判定为通用合成内容）。
COUNCIL_QUERY = (
    "示例提问（合成文本）：请演示模型委员会导出流程，比较三个示例模型在同一示例任务上的回答，"
    "并给出选择建议与理由。")
SEARCH_QUERY = "示例提问段落（其一）：演示单轮搜索导出的合成问题文本？"
DEEP_QUERY = "示例研究问题（合成）：演示深度研究报告与工作流程的导出格式。"

FIXTURE_TEXT: dict[str, dict] = {
    "search_demo": {
        "title": SEARCH_QUERY, "queries": [SEARCH_QUERY],
        "space": ("示例专题空间", "example-topic-space-a1b2c3"),
    },
    "deep_research_demo": {
        "title": DEEP_QUERY, "queries": [DEEP_QUERY],
        "space": ("示例阅读空间", "example-reading-space-d4e5f6"),
    },
    "council_demo": {
        "title": COUNCIL_QUERY, "queries": [COUNCIL_QUERY],
        "related_queries": [
            "示例相关检索词（一）",
            "示例相关检索词（二）",
            "示例相关检索词（三）",
            "示例相关检索词（四）",
            "示例相关检索词（五）",
        ],
    },
    # Generic study question (synthetic teaching prompt); already synthetic, kept as-is
    # 通用教学提问（合成占位文本），已是合成内容，保留
    "study_demo": {},
    "computer_demo": {
        # The existing title is a generic synthetic computer-task title; kept
        # 原标题为通用合成计算机任务标题，保留
        "title": None,
        "queries": [
            "示例查询段落（其一）：演示计算机模式首轮提问的合成占位文本，包含示例参数与示例背景说明。",
            "示例查询段落（其二）：演示后续追问的导出格式。",
            "示例查询段落（其三）：演示含示例数值追问的占位文本。",
            "示例查询段落（其四）：演示多句追问的合成占位文本，包含示例现象描述与示例疑问。",
            "示例查询段落（其五）：演示风险类追问的占位文本。",
            "示例查询段落（其六）：演示规格类追问的合成占位文本。",
            "示例查询段落（其七）：演示收尾追问的占位文本。",
        ],
    },
    "scenario_computer_answer_fallback": {"title": "完善课程报告规划"},
    # Generic development task; kept as-is
    # 通用开发任务，保留
    "scenario_subagent_fallback": {},
    "scenario_canceled": {"title": "报告分析与代码优化"},
    "scenario_limit_interrupted": {
        "title": "章节提纲规划",
        "queries": ["请先用子代理按大纲结合已有文字完成初稿"],
    },
    "scenario_user_response": {
        "title": "示例工作流规划标题（合成）",
        "space": ("示例学科空间", "example-subject-space-g7h8i9"),
        "user_questions": [
            {"title": "示例提问组标题（其一）：演示关键决策提问", "fields": [
                {"field_name": "示例问题（其一）：演示第一项单选提问的占位文字？", "options": [
                    ("示例选项（一·甲）",
                     "示例选项说明（一·甲）：演示该选项取舍的占位描述。"),
                    ("示例选项（一·乙）",
                     "示例选项说明（一·乙）：演示该选项取舍的占位描述。"),
                    ("示例选项（一·丙）",
                     "示例选项说明（一·丙）：演示该选项取舍的占位描述。"),
                    ("示例选项（一·丁）",
                     "示例选项说明（一·丁）：演示该选项取舍的占位描述。"),
                ]},
                {"field_name": "示例问题（其二）：演示第二项单选提问的占位文字？", "options": [
                    ("示例选项（二·甲）",
                     "示例选项说明（二·甲）：演示该选项取舍的占位描述。"),
                    ("示例选项（二·乙）",
                     "示例选项说明（二·乙）：演示该选项取舍的占位描述。"),
                    ("示例选项（二·丙）",
                     "示例选项说明（二·丙）：演示该选项取舍的占位描述。"),
                ]},
                {"field_name": "示例问题（其三）：演示第三项单选提问的占位文字？", "options": [
                    ("示例选项（三·甲）",
                     "示例选项说明（三·甲）：演示该选项取舍的占位描述。"),
                    ("示例选项（三·乙）",
                     "示例选项说明（三·乙）：演示该选项取舍的占位描述。"),
                    ("示例选项（三·丙）",
                     "示例选项说明（三·丙）：演示该选项取舍的占位描述。"),
                ]},
                {"field_name": "示例问题（其四）：演示第四项单选提问的占位文字？", "options": [
                    ("示例选项（四·甲）",
                     "示例选项说明（四·甲）：演示该选项取舍的占位描述。"),
                    ("示例选项（四·乙）",
                     "示例选项说明（四·乙）：演示该选项取舍的占位描述。"),
                    ("示例选项（四·丙）",
                     "示例选项说明（四·丙）：演示该选项取舍的占位描述。"),
                ]},
            ]},
            {"title": "示例提问组标题（其二）：演示补充细节提问", "fields": [
                {"field_name": "示例问题（其五）：演示第五项单选提问的占位文字？", "options": [
                    ("示例选项（五·甲）",
                     "示例选项说明（五·甲）：演示该选项取舍的占位描述。"),
                    ("示例选项（五·乙）",
                     "示例选项说明（五·乙）：演示该选项取舍的占位描述。"),
                    ("示例选项（五·丙）",
                     "示例选项说明（五·丙）：演示该选项取舍的占位描述。"),
                ]},
                {"field_name": "示例问题（其六）：演示第六项单选提问的占位文字？", "options": [
                    ("示例选项（六·甲）",
                     "示例选项说明（六·甲）：演示该选项取舍的占位描述。"),
                    ("示例选项（六·乙）",
                     "示例选项说明（六·乙）：演示该选项取舍的占位描述。"),
                    ("示例选项（六·丙）",
                     "示例选项说明（六·丙）：演示该选项取舍的占位描述。"),
                ]},
            ]},
        ],
        "responses": [
            ("示例问题（其一）：演示第一项单选提问的占位文字？", "示例选项（一·丁）"),
            ("示例问题（其二）：演示第二项单选提问的占位文字？", "示例选项（二·甲）"),
            ("示例问题（其三）：演示第三项单选提问的占位文字？", "示例选项（三·乙）"),
            ("示例问题（其四）：演示第四项单选提问的占位文字？", "示例选项（四·甲）"),
        ],
        "plan_summary": (
            "示例计划摘要（合成）：演示对用户决策的汇总段落。\n\n"
            "- **示例决策项（其一）**：示例选项（一·丁）\n"
            "- **示例决策项（其二）**：示例选项（二·甲）\n"
            "- **示例决策项（其三）**：示例选项（三·乙）\n"
            "- **示例决策项（其四）**：示例选项（四·甲）\n\n"
            "示例收尾段落（合成）：演示后续步骤说明的占位文字。"),
    },
}

# Marker items whose values are kept as-is in generic Q&A payloads
# 通用问答负载中保留原值的标记项
_PASSTHROUGH = {"OTHER", "handle_asi_answers"}


# ── Multi-level escape replacement
# ── 多级转义替换 ─────────────────────────────────────────────
def _variants(s: str) -> list[str]:
    """All possible representations of s in a file (deepest level first):
    - nested JSON layers (raw_entries entries[].text etc., internally serialized
      with ensure_ascii=True, backslashes doubling per nesting level):
      level_k = k rounds of ensure_ascii escaping;
    - outer JSON strings (raw_blocks / thread.json, ensure_ascii=False: literal
      CJK characters, escaped newlines);
    - plain literals (markdown etc.).

    s 在文件中的全部可能表示（深→浅）：
    - 嵌套 JSON 层（raw_entries 的 entries[].text 等，内部序列化 ensure_ascii=True，
      每深一层反斜杠翻倍）：level_k = k 重 ensure_ascii 转义；
    - 外层 JSON 字符串（raw_blocks/thread.json，ensure_ascii=False：中文字面、换行转义）；
    - 字面量（markdown 等）。
    """
    chain = [json.dumps(s, ensure_ascii=True)[1:-1]]
    for _ in range(3):
        chain.append(json.dumps(chain[-1], ensure_ascii=True)[1:-1])
    out = list(reversed(chain))
    out.append(json.dumps(s, ensure_ascii=False)[1:-1])
    out.append(s)
    return out


def replace_pair(text: str, old: str, new: str) -> tuple[str, int]:
    """Replace old→new across all representations (incl. nested JSON escape
    layers and URL percent-encoded variants); return the replacement count.

    全表示替换 old→new（含 JSON 嵌套转义层与 URL 百分号编码变体），返回替换次数。"""
    n = 0
    for ov, nv in zip(_variants(old), _variants(new)):
        if ov == nv:
            continue
        c = text.count(ov)
        if c:
            text = text.replace(ov, nv)
            n += c
    if any(ord(ch) > 127 for ch in old):
        from urllib.parse import quote
        eo, en = quote(old, safe=""), quote(new, safe="")
        c = text.count(eo)
        if c:
            text = text.replace(eo, en)
            n += c
    return text, n


# ── Positional extraction from JSON structures
# ── JSON 结构位置式提取 ─────────────────────────────────────
def _load(d: Path, fn: str):
    p = d / fn
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def collect_fixture_pairs(name: str, d: Path, cfg: dict) -> list[tuple[str, str]]:
    """Extract original values from a fixture's JSON structure per config and
    pair them with the synthetic replacement values.

    按配置从 fixture 的 JSON 结构中提取原值，与合成新值配对。"""
    pairs: list[tuple[str, str]] = []

    def add(old, new):
        if old and new and old != new:
            pairs.append((old, new))

    re_j = _load(d, "raw_entries.json")
    rb_j = _load(d, "raw_blocks.json")
    tj = _load(d, "thread.json")

    if cfg.get("title"):
        new_title = cfg["title"]
        for j in (re_j, rb_j):
            if j:
                add((j.get("thread_metadata") or {}).get("title"), new_title)
                for e in j.get("entries") or []:
                    add(e.get("thread_title"), new_title)
        if tj:
            add(tj.get("title"), new_title)
            add((tj.get("metadata") or {}).get("title"), new_title)

    if cfg.get("queries") and rb_j:
        olds = [e.get("query_str") for e in rb_j.get("entries") or [] if e.get("query_str")]
        news = cfg["queries"]
        if len(olds) != len(news):
            raise SystemExit(f"{name}: query 数 {len(olds)} 与配置 {len(news)} 不一致")
        for o, nq in zip(olds, news):
            add(o, nq)

    if cfg.get("related_queries") and rb_j:
        for e in rb_j.get("entries") or []:
            rq = e.get("related_queries")
            if rq:
                news = cfg["related_queries"]
                if len(rq) != len(news):
                    raise SystemExit(f"{name}: related_queries 数不一致")
                for o, nq in zip(rq, news):
                    add(o, nq)
                break

    if cfg.get("space") and tj and tj.get("space"):
        add(tj["space"].get("title"), cfg["space"][0])
        add(tj["space"].get("slug"), cfg["space"][1])

    # WORKFLOW_ITEM_USER_QUESTIONS / USER_RESPONSE / plan summary (scenario_user_response)
    # WORKFLOW_ITEM_USER_QUESTIONS / USER_RESPONSE / plan 摘要（scenario_user_response）
    if cfg.get("user_questions") and rb_j:
        payloads, responses, plan_descs = [], [], []
        for e in rb_j.get("entries") or []:
            for b in e.get("blocks") or []:
                wb = (b or {}).get("workflow_block") or {}
                for st in wb.get("steps") or []:
                    for it in st.get("items") or []:
                        p = (it or {}).get("payload") or {}
                        if p.get("user_questions_payload"):
                            payloads.append(p["user_questions_payload"])
                        if p.get("user_response_payload"):
                            responses.extend(p["user_response_payload"].get("responses") or [])
                pb = (b or {}).get("plan_block") or {}
                for g in pb.get("goals") or []:
                    desc = g.get("description") or ""
                    if "汇总一下你的决策" in desc:
                        plan_descs.append(desc)
        if len(payloads) != len(cfg["user_questions"]):
            raise SystemExit(f"{name}: user_questions 负载数 {len(payloads)} 与配置不一致")
        for old_p, new_p in zip(payloads, cfg["user_questions"]):
            add(old_p.get("title"), new_p["title"])
            of, nf = old_p.get("fields") or [], new_p["fields"]
            if len(of) != len(nf):
                raise SystemExit(f"{name}: user_questions 字段数不一致")
            for ofld, nfld in zip(of, nf):
                add(ofld.get("field_name"), nfld["field_name"])
                oopts = [o for o in (ofld.get("options") or [])
                         if o.get("title") and o.get("title") not in _PASSTHROUGH]
                if len(oopts) != len(nfld["options"]):
                    raise SystemExit(f"{name}: 选项数不一致: {ofld.get('field_name')!r}")
                for oopt, (nt, nd) in zip(oopts, nfld["options"]):
                    add(oopt.get("title"), nt)
                    add(oopt.get("description"), nd)
        nresp = cfg["responses"]
        if len(responses) != len(nresp):
            raise SystemExit(f"{name}: responses 数 {len(responses)} 与配置不一致")
        for r, (nq, na) in zip(responses, nresp):
            add(r.get("question"), nq)
            add(r.get("answer"), na)
        for desc in plan_descs:
            add(desc, cfg["plan_summary"])
    return pairs


# ── Identity pairs (read from the user-level config at runtime; nothing embedded)
# ── 身份对（运行时读用户级配置；脚本不内嵌任何字面量）──────────────
def collect_identity_pairs() -> tuple[list[tuple[str, str]], list[str]]:
    # The account registry is loaded from the user-level TOML via configure()
    # 账户注册表经 configure() 从用户级 TOML 加载
    from pplx_export import config

    pairs: list[tuple[str, str]] = []
    missing: list[str] = []
    usernames = sorted(config.ACCOUNT_EMAIL.keys() | config.ACCOUNT_DISPLAY_NAMES.keys())
    if not usernames:
        missing.append("账户注册表为空（未加载用户级配置），跳过身份替换")
    for uname, ph in zip(usernames, PLACEHOLDER_ACCOUNTS):
        pairs.append((uname, ph["key"]))
        disp = config.ACCOUNT_DISPLAY_NAMES.get(uname)
        if disp and disp != uname:
            pairs.append((disp, ph["display"]))
        email = config.ACCOUNT_EMAIL.get(uname)
        if email:
            pairs.append((email, ph["email"]))
        uid = config.ACCOUNT_UID.get(uname)
        if uid:
            pairs.append((uid, ph["uid"]))
        else:
            missing.append(f"账户 {ph['key']} 缺 user_id（配置 accounts.{uname}.user_id）")
    # Longest username first (prevents prefix shadowing)
    # 长用户名优先（防前缀吞噬）
    pairs.sort(key=lambda p: -len(p[0]))
    if config.BOT_SPACE_UUID:
        pairs.append((config.BOT_SPACE_UUID, BOT_PLACEHOLDER_UUID))
    if config.BOT_SPACE_SLUG:
        pairs.append((config.BOT_SPACE_SLUG, BOT_PLACEHOLDER_SLUG))
    return pairs, missing


def collect_local_pairs() -> list[tuple[str, str]]:
    """Content-class replacement pairs (local override mapping file, not committed).

    内容类替换对（本地覆盖映射文件，不入库）。"""
    if not PAIRS_LOCAL.is_file():
        return []
    data = json.loads(PAIRS_LOCAL.read_text(encoding="utf-8"))
    return [(str(o), str(n)) for o, n in data.get("pairs") or []]


def local_gate_patterns() -> list[str]:
    if not PAIRS_LOCAL.is_file():
        return []
    data = json.loads(PAIRS_LOCAL.read_text(encoding="utf-8"))
    return [str(x) for x in data.get("gate") or []]


def pinned_uuid_exclusions() -> set[str]:
    """Fixture UUIDs pinned in test code (read dynamically from test_relations.py, not embedded).

    测试代码中钉死的 fixture UUID（从 test_relations.py 动态读取，不内嵌）。"""
    out = {FAKE_TOKEN, BOT_PLACEHOLDER_UUID,
           *(p["uid"] for p in PLACEHOLDER_ACCOUNTS)}
    tr = TESTS_DIR / "test_relations.py"
    if tr.is_file():
        out |= set(UUID_RE.findall(tr.read_text(encoding="utf-8")))
    return out


def synth_uuid(orig: str) -> str:
    h = str(uuidlib.uuid5(UUID_NS, UUID_SALT + orig))
    return UUID_MARK + h[8:]


_B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def synth_toolu(orig: str) -> str:
    digest = hashlib.sha256((UUID_SALT + orig).encode()).digest()
    num = int.from_bytes(digest, "big")
    chars = []
    for _ in range(24 - len(TOOLU_MARK)):
        num, r = divmod(num, 62)
        chars.append(_B62[r])
    return "toolu_" + TOOLU_MARK + "".join(chars)


# ── Golden regeneration
# ── golden 重生成 ────────────────────────────────────────────
def regenerate_golden(d: Path) -> None:
    from pplx_export.commands.rerender_cmd import rerender

    golden = d / "golden"
    if not golden.is_dir():
        return
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / d.name
        work.mkdir()
        for fn in RAW_NAMES:
            if (d / fn).exists():
                shutil.copy2(d / fn, work / fn)
        if not rerender(work):
            raise SystemExit(f"rerender 失败: {d.name}")
        if (golden / "conversation.md").exists():
            shutil.copy2(work / "conversation.md", golden / "conversation.md")
        for g in sorted(golden.rglob("turn_*.md")):
            src = work / "turns" / g.name
            if not src.exists():
                raise SystemExit(f"{d.name}: 重渲缺 {src.name}")
            shutil.copy2(src, g)
        n_work = len(list((work / "turns").glob("turn_*.md"))) if (work / "turns").is_dir() else 0
        n_gold = len(list(golden.rglob("turn_*.md")))
        if n_work != n_gold:
            raise SystemExit(f"{d.name}: 轮数不一致 work={n_work} golden={n_gold}")


# ── Main flow
# ── 主流程 ───────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Deterministic fixture maintenance (idempotent) / fixtures 确定性维护（幂等）")
    ap.add_argument("--check", action="store_true",
                    help="Run the gate only, no file writes / 只跑门禁，不写文件")
    args = ap.parse_args()

    fixture_dirs = sorted(p for p in FIXTURES.iterdir() if p.is_dir())
    scoped_pairs: dict[str, list[tuple[str, str]]] = {}
    for d in fixture_dirs:
        cfg = FIXTURE_TEXT.get(d.name, {})
        scoped_pairs[d.name] = collect_fixture_pairs(d.name, d, cfg)

    identity_pairs, missing = collect_identity_pairs()
    for m in missing:
        print(f"[warn] {m}", file=sys.stderr)
    local_pairs = collect_local_pairs()
    if not local_pairs:
        print("[warn] 未找到 tests/scrub_pairs.local.json，内容类字面量替换跳过", file=sys.stderr)

    files_of = {d.name: [d / fn for fn in RAW_NAMES if (d / fn).exists()] for d in fixture_dirs}
    all_raw = [p for ps in files_of.values() for p in ps]

    # Original token values (collected before the UUID mapping; also feeds the gate)
    # token 原值（先于 UUID 映射收集；同时作为门禁模式）
    token_vals = sorted({m for p in all_raw for m in TOKEN_RE.findall(p.read_text(encoding="utf-8"))
                         if m != FAKE_TOKEN})

    stats: dict[str, int] = {}
    problems: list[str] = []

    def apply(pairs, paths, label, required):
        for old, new in pairs:
            total = 0
            for p in paths:
                t = p.read_text(encoding="utf-8")
                t, n = replace_pair(t, old, new)
                if n:
                    p.write_text(t, encoding="utf-8")
                    total += n
            stats[f"{label}: {old[:40]!r}"] = total
            if total == 0:
                # Idempotent rerun: new value already present counts as replaced; otherwise record a problem
                # 幂等重跑：新值已存在视为已替换；否则记问题
                if not any(new in p.read_text(encoding="utf-8") for p in paths):
                    problems.append(f"未命中且新值不存在: {old[:60]!r} ({label})")

    if not args.check:
        for name, pairs in scoped_pairs.items():
            apply(pairs, files_of[name], f"fixture:{name}", required=True)
        apply(local_pairs, all_raw, "local", required=True)
        apply(identity_pairs, all_raw, "identity", required=False)
        apply([(v, FAKE_TOKEN) for v in token_vals], all_raw, "token", required=True)
        # Strip query strings from signed URLs
        # 签名 URL 剥离查询串
        for p in all_raw:
            t = p.read_text(encoding="utf-8")
            t2, n = SIGNED_URL_RE.subn(r"\1", t)
            if n:
                p.write_text(t2, encoding="utf-8")
                stats[f"signed-url: {p.parent.name}/{p.name}"] = n
        # Repo-wide consistent UUID mapping (skips synthetic markers and pinned/placeholder values)
        # UUID 全库一致映射（跳过合成标记与钉死/占位值）
        excl = pinned_uuid_exclusions()
        uuid_map: dict[str, str] = {}
        for p in all_raw:
            for v in UUID_RE.findall(p.read_text(encoding="utf-8")):
                if v.startswith(UUID_MARK) or v in excl:
                    continue
                uuid_map.setdefault(v, synth_uuid(v))
        for p in all_raw:
            t = p.read_text(encoding="utf-8")
            for o, n in uuid_map.items():
                t = t.replace(o, n)
            p.write_text(t, encoding="utf-8")
        stats["uuid-remap"] = len(uuid_map)
        # toolu_ run id mapping
        # toolu_ 运行 id 映射
        toolu_map: dict[str, str] = {}
        for p in all_raw:
            for v in TOOLU_RE.findall(p.read_text(encoding="utf-8")):
                if v[len("toolu_"):].startswith(TOOLU_MARK):
                    continue
                toolu_map.setdefault(v, synth_toolu(v))
        for p in all_raw:
            t = p.read_text(encoding="utf-8")
            for o, n in toolu_map.items():
                t = t.replace(o, n)
            p.write_text(t, encoding="utf-8")
        stats["toolu-remap"] = len(toolu_map)
        # Regenerate golden snapshots
        # golden 重生成
        for d in fixture_dirs:
            regenerate_golden(d)

    # ── Gate: zero residue
    # ── 门禁：零残留 ─────────────────────────────────────────
    gate = set(local_gate_patterns())
    gate |= {o for o, _ in identity_pairs}
    gate |= {o for o, _ in local_pairs}
    gate |= set(token_vals)
    gate |= {o for ps in scoped_pairs.values() for o, _ in ps}
    gate |= {"/Users/", "?Policy=", "&Signature=", "Key-Pair-Id="}
    hits = []
    for f in sorted(FIXTURES.rglob("*")):
        if not f.is_file():
            continue
        t = f.read_text(encoding="utf-8")
        for g in gate:
            if g and g in t:
                hits.append(f"{f.relative_to(FIXTURES)}: 残留 {g[:60]!r}")
    # Synthetic marker prefixes must not survive in unmapped form
    # (spot check: no unmarked old tokens remain after mapping)
    # 合成标记前缀不应残留未映射形态（抽查：映射后无未标记的旧 token）
    for k, v in sorted(stats.items()):
        print(f"  {v:6d}  {k}")
    if problems:
        print("\n[problems]", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
    if hits:
        print("\n[gate FAILED]", file=sys.stderr)
        for h in hits[:50]:
            print("  " + h, file=sys.stderr)
        return 1
    if problems:
        return 1
    print("\n门禁通过：fixtures 零残留。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
