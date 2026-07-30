"""Perplexity render layer: renders domain models into human-readable markdown.

computer mode uses the full workflow_block detail (narration / tools / sub-agent
prompt+steps / per-step citations); search/deep-research use text steps. Rendering is
separated from parsing, so the output can be regenerated offline from raw JSON.

Perplexity 渲染层：把领域模型渲染为人读 markdown。

computer 模式用 workflow_block 全细节（旁白/工具/子代理 prompt+步骤/逐步引文），
search/deep-research 用文本步骤。渲染与解析分离，可离线从 raw JSON 重生成。
"""

from __future__ import annotations

from ...core.logging import get_logger
from ...core.models import Conversation, Step, SubAgent, Turn
from .normalize import normalize_math_delims, ts_us_to_iso
from . import parsers

log = get_logger("render")


def _chunks_text(tp: dict) -> str:
    t = tp.get("text") or ""
    return t if t else "".join(tp.get("chunks") or [])


def _fence_for(body: str) -> str:
    """Return a fence that fully wraps body: one more backtick than the longest
    backtick run in the content (minimum 3).

    Tool output often carries its own ``` lines (shell examples, quoted markdown);
    a fixed triple-backtick fence gets closed early by the content and the pairing
    flips (the earlier unpaired fences in computer turns came from this).

    返回能完整包裹 body 的围栏：比内容中最长反引号连续段多 1（最少 3 个）。

    工具输出里常自带 ``` 行（shell 示例、quoted markdown），固定三反引号会被
    内容提前闭合、配对翻转（此前 computer turns 围栏不配对即源于此）。
    """
    import re as _re
    longest = max((len(m.group(0)) for m in _re.finditer(r"`+", body)), default=0)
    return "`" * max(3, longest + 1)


def _render_nested_wf(wp: dict, depth: int = 0, seen=None, label: str = "🧩 嵌套工作流",
                      locked_reason: str | None = None) -> str:
    """Nested workflow_payload -> <details> collapsible block.

    steps are rendered recursively via render_wf_item (depth limited to 2 levels + an id
    set guarding against self-referential loops); TEXT with variant=="answer" is collected
    into a "Conclusion" section; the SOURCES text_payload body goes inline into the step
    (aligned with render_wf_item; previously only URLs were collected and the sub-agent's
    extracted body text was dropped), while URLs are aggregated into the trailing citation
    list (deduplicated by url). When there is nothing renderable, return a
    "（无工作步骤记录）" placeholder shell (faithfully recording sub-agents interrupted
    right at startup). Non-completed status (interrupted/cancelled) is annotated in the
    summary (parsers.wf_status_tag).

    嵌套 workflow_payload → <details> 折叠块。

    steps 递归用 render_wf_item 渲染（深度限 2 层 + id 集合防自引用循环）；
    variant=="answer" 的 TEXT 收为「结论」段；SOURCES 的 text_payload 正文进步骤内联
    （对齐 render_wf_item；此前只收 URL 导致子代理提取正文被丢弃），URL 聚合为末尾引文列表（按 url 去重）。
    无任何可渲染内容时返回 "（无工作步骤记录）" 占位壳（如实记录启动即中断的子代理）。
    非 completed 状态（中断/取消）在 summary 加注（parsers.wf_status_tag）。
    """
    steps = [s for s in (wp.get("steps") or []) if isinstance(s, dict)]
    headline = (wp.get("headline") or "").strip() or "未命名"
    answer = ""
    srcs: list[dict] = []
    seen_urls: set = set()
    body: list[str] = []
    for s in steps:
        step_parts = []
        for it in (s.get("items") or []):
            if not isinstance(it, dict):
                continue
            tp_ = it.get("type")
            pl = it.get("payload") or {}
            if tp_ == "WORKFLOW_ITEM_TEXT":
                tpp = pl.get("text_payload") or {}
                if tpp.get("variant") == "answer":
                    txt = tpp.get("text") or "".join(tpp.get("chunks") or [])
                    if txt.strip():
                        answer = txt
                    continue
            if tp_ == "WORKFLOW_ITEM_SOURCES":
                # The body text (the sub-agent's page extraction / comparison table) goes
                # inline into the step; URLs are still aggregated into the trailing citations.
                # 正文（子代理对页面的提取/对比表）进步骤内联，URL 仍聚合到末尾引文
                _txt = _chunks_text(pl.get("text_payload") or {})
                if _txt.strip():
                    step_parts.append(normalize_math_delims(_txt))
                for x in ((pl.get("sources_payload") or {}).get("sources") or []):
                    if isinstance(x, dict) and x.get("url") and x["url"] not in seen_urls:
                        seen_urls.add(x["url"])
                        srcs.append(x)
                # Citations are aggregated at the end, not repeated inline in the step.
                # 引文聚合到末尾，不在步骤内联重复
                continue
            b = render_wf_item(it, depth=depth + 1, seen=seen)
            if b and b.strip():
                step_parts.append(b)
        if step_parts:
            title = (s.get("title") or "").strip()
            tool = (s.get("tool_name") or "").strip()
            if title or tool:
                head = f"**{title}**" if title else ""
                head += f"（`{tool}`）" if tool else ""
                body.append(head)
            body.extend(step_parts)
    stat = f"{len(steps)} 步骤 · " + ("有结论" if answer else "无结论")
    if srcs:
        stat += f" · 引文 {len(srcs)}"
    tag = parsers.wf_status_tag(wp.get("status"), locked_reason)
    if tag:
        stat += f" · {tag}"
    out = ["<details>", f"<summary>{label}：{headline}（{stat}）</summary>", ""]
    if body:
        out.append("\n\n".join(body))
    elif steps:
        # Steps have no item details (title-only records, e.g. an expanded
        # "completed N steps" list): list them as-is.
        # 步骤无 items 细节（仅标题记录，如"已完成 N 步骤"展开列表）：如实列出
        titles = []
        for s in steps:
            st_title = (s.get("title") or "").strip()
            st_tool = (s.get("tool_name") or "").strip()
            if st_title or st_tool:
                line = f"- {st_title}" + (f"（`{st_tool}`）" if st_tool else "")
                titles.append(line)
        if titles:
            out.append("\n".join(titles))
        else:
            out.append("（无工作步骤记录）")
    else:
        out.append("（无工作步骤记录）")
    if answer:
        out += ["", "**结论：**", "", normalize_math_delims(answer)]
    if srcs:
        out += ["", "**引文：**", ""]
        # List all citations (citation fidelity is an archival principle; the old [:20]
        # cap showed only the first 20 of a research sub-agent's hundreds of citations).
        # 全量列出（引文保真是归档原则；此前 [:20] 封顶导致研究子代理数百条引文只见前 20）
        for s in srcs:
            out.append(f"- [{s.get('name') or s.get('url')}]({s.get('url')})")
    out += ["", "</details>"]
    return "\n".join(out)


def render_wf_item(it: dict, depth: int = 0, seen=None) -> str:
    t = it.get("type", "?")
    p = it.get("payload") or {}
    if t == "WORKFLOW_ITEM_WORKFLOW":
        wp = p.get("workflow_payload") or {}
        if wp.get("mode") == "LLM_COUNCIL":
            # Council nesting is rendered by the council_research branch (avoid duplication).
            # 委员会嵌套由 council_research 分支渲染（避免重复）
            return ""
        if wp.get("objective_chunks") or wp.get("is_background_anchor"):
            # Sub-agent anchors are rendered via the sub_map/render_subagent path (avoid duplication).
            # 子代理锚点由 sub_map/render_subagent 路径渲染（避免重复）
            return ""
        steps = [s for s in (wp.get("steps") or []) if isinstance(s, dict)]
        if not steps:
            # Keep the placeholder for an empty anchor.
            # 空锚点保持占位
            return f"（{t}）"
        wid = wp.get("id")
        if depth >= 2 or (wid and seen and wid in seen):
            return f"（嵌套工作流：{(wp.get('headline') or '未命名').strip()}，已达递归上限）"
        seen2 = (seen | {wid}) if seen is not None else ({wid} if wid else None)
        return _render_nested_wf(wp, depth=depth, seen=seen2)
    if t == "WORKFLOW_ITEM_TEXT":
        tp = p.get("text_payload") or {}
        variant = tp.get("variant")
        if variant == "answer":
            return ""
        body = _chunks_text(tp)
        if not body.strip():
            return ""
        if variant in ("thought", "thinking"):
            return "> " + normalize_math_delims(body).replace("\n", "\n> ")
        if tp.get("is_mono") or tp.get("header") == "Output":
            fence = _fence_for(body)
            return f"{fence}\n{body.rstrip()}\n{fence}"
        return normalize_math_delims(body)
    if t == "WORKFLOW_ITEM_SOURCES":
        out = []
        txt = _chunks_text(p.get("text_payload") or {})
        if txt.strip():
            out.append(txt)
        srcs = (p.get("sources_payload") or {}).get("sources") or []
        if srcs:
            out.append("**来源：**")
            for s in srcs:
                if isinstance(s, dict):
                    out.append(f"- [{s.get('name') or s.get('url')}]({s.get('url')})")
        return "\n".join(out)
    if t == "WORKFLOW_ITEM_TODO_LIST":
        tl = p.get("todo_list_payload") or {}
        lines = [f"**{tl.get('title') or '任务清单'}**"]
        for it2 in (tl.get("items") or []):
            mark = {"COMPLETED": "x", "IN_PROGRESS": "/", "PENDING": " "}.get(it2.get("status"), " ")
            lines.append(f"- [{mark}] {it2.get('description')}")
        return "\n".join(lines)
    if t == "WORKFLOW_ITEM_QUERIES":
        qs = (p.get("queries_payload") or {}).get("queries") or []
        return "**检索：**\n" + "\n".join(f"- {q}" for q in qs) if qs else ""
    if t == "WORKFLOW_ITEM_TABLE":
        tp = p.get("table_payload") or {}
        cols = tp.get("columns") or []
        rows = tp.get("rows") or []
        if not cols:
            return ""
        # Escape | and newlines in column headers and cell values (:182/:190) alike,
        # to avoid breaking the markdown table structure.
        # 列头与单元格值（:182/:190）同样转义 | 与换行，避免破坏 markdown 表格结构
        head = [str(c).replace("|", "｜").replace("\n", " ") for c in cols]
        lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(cols)]
        for r in rows:
            if isinstance(r, dict):
                cells = r.get("cells") or {}
                vals = []
                for c in cols:
                    v = cells.get(c)
                    if isinstance(v, dict):
                        v = v.get("value", "")
                    vals.append(str(v or "").replace("|", "｜").replace("\n", " "))
            elif isinstance(r, list):
                # The row is directly a list of values: take values in column order.
                # 行直接是值列表：按列序取值
                vals = []
                for i in range(len(cols)):
                    v = r[i] if i < len(r) else ""
                    if isinstance(v, dict):
                        v = v.get("value", "")
                    vals.append(str(v or "").replace("|", "｜").replace("\n", " "))
            else:
                continue
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)
    if t == "WORKFLOW_ITEM_USER_QUESTIONS":
        uq = p.get("user_questions_payload") or {}
        qs = uq.get("questions") or []
        out = ["**向用户提问：**"]
        for q in qs:
            if isinstance(q, dict):
                out.append(f"- {q.get('question') or q.get('text') or ''}")
        return "\n".join(out) if len(out) > 1 else ""
    if t == "WORKFLOW_ITEM_USER_RESPONSE":
        ur = p.get("user_response_payload") or {}
        out = []
        for r in (ur.get("responses") or []):
            if not isinstance(r, dict):
                continue
            q = (r.get("question") or "").strip()
            a = (r.get("answer") or "").strip()
            if q:
                out.append(f"**问：** {q}")
            if a:
                out.append(f"**答：** {a}")
        return "\n\n".join(out)
    if t == "WORKFLOW_ITEM_CONTENT":
        cp = p.get("content_payload") or {}
        descs = [(e.get("description") or "").strip()
                 for e in (cp.get("entities") or []) if isinstance(e, dict)]
        return "\n\n".join(normalize_math_delims(d) for d in descs if d)
    return f"（{t}）"


def _render_code_step(c: dict) -> str:
    """CODE step: script + stdout/stderr fenced blocks (previously the whole block was
    silently dropped; 509 occurrences observed in archival testing).

    CODE 步骤：脚本 + stdout/stderr 围栏块（此前整块静默丢失，归档实测 509 处）。"""
    out = []
    script = (c.get("script") or "").rstrip()
    lang = (c.get("language") or "").strip()
    if script:
        fence = _fence_for(script)
        head = f"**代码**（{lang}）" if lang else "**代码**"
        out.append(f"{head}\n\n{fence}{lang}\n{script}\n{fence}")
    stdout = (c.get("stdout") or "").rstrip()
    if stdout:
        fence = _fence_for(stdout)
        out.append(f"**输出**\n\n{fence}\n{stdout}\n{fence}")
    stderr = ((c.get("stderr") or "") or (c.get("error") or "")).rstrip()
    if stderr:
        fence = _fence_for(stderr)
        out.append(f"**错误输出**\n\n{fence}\n{stderr}\n{fence}")
    return "\n\n".join(out)


def render_step(step: Step) -> str:
    st = step.step_type
    c = step.content or {}
    if st in ("INITIAL_QUERY", "FINAL"):
        return ""
    if st in ("ASI_TOOL_INPUT", "ASI_TOOL_OUTPUT"):
        items = c.get("workflow_items") or []
        body = "\n\n".join(filter(None, (render_wf_item(it) for it in items)))
        if not body.strip():
            return ""
        label = "工具输入" if st == "ASI_TOOL_INPUT" else "工具输出"
        ts = (c.get("timestamp") or "")[:19].replace("T", " ")
        return f"**{label}**（{ts}）\n\n{body}"
    if st == "THOUGHT":
        txt = c.get("thought") or c.get("text") or ""
        return f"**思考**\n\n{txt}" if txt else ""
    if st == "SEARCH_WEB":
        qs = c.get("queries") or []
        body = "\n".join(f"- {q.get('query') if isinstance(q, dict) else q}" for q in qs)
        return f"**检索网页**\n\n{body}"
    if st == "SEARCH_RESULTS":
        wr = c.get("web_results") or []
        lines = ["**检索结果**", ""]
        for r in wr:
            if isinstance(r, dict):
                lines.append(f"- [{r.get('name') or r.get('url')}]({r.get('url')})")
        return "\n".join(lines)
    if st == "GET_URL_CONTENT":
        pages = c.get("pages") or []
        urls = [p.get("url") for p in pages if isinstance(p, dict) and p.get("url")]
        return "**读取页面**\n\n" + "\n".join(f"- {u}" for u in urls) if urls else ""
    if st in ("LOAD_SKILL", "LOAD_SKILL_RESPONSE"):
        skills = c.get("skill_names") or c.get("loaded_skills") or []
        return f"**{st}**：{'、'.join(skills)}"
    if st == "RESEARCH_ANSWER":
        return f"**生成研究报告**：{c.get('title') or ''}"
    if st == "CODE":
        return _render_code_step(c)
    if st == "ATTACHMENT":
        lines = ["**附件**"]
        for a in (c.get("attachments") or []):
            if isinstance(a, dict) and (a.get("url") or a.get("name")):
                lines.append(f"- [{a.get('name') or a.get('url')}]({a.get('url')})")
        return "\n".join(lines) if len(lines) > 1 else ""
    if st == "URL_NAVIGATE":
        urls = [u for u in (c.get("urls") or []) if isinstance(u, str) and u]
        return "**打开页面**\n\n" + "\n".join(f"- {u}" for u in urls) if urls else ""
    if st == "CREATE_CHART":
        cap = (c.get("caption") or "").strip()
        return f"**创建图表**：{cap}" if cap else "**创建图表**"
    if st == "GENERATE_IMAGE_RESULTS":
        lines = ["**生成图片结果**"]
        for im in (c.get("image_results") or []):
            if isinstance(im, dict) and im.get("url"):
                wh = (f"（{im['image_width']}×{im['image_height']}）"
                      if im.get("image_width") and im.get("image_height") else "")
                lines.append(f"- [{im['url']}]({im['url']}){wh}")
        return "\n".join(lines) if len(lines) > 1 else ""
    if not st:
        return ""
    # Unknown types are no longer silently dropped: placeholder line + debug log
    # (observed: DOCX/MCP_TOOL_*/READ etc.).
    # 未知类型不再静默丢弃：占位行 + debug 日志（实测 DOCX/MCP_TOOL_*/READ 等）
    log.debug(f"[render] 未渲染 step_type={st}")
    return f"**{st}**（未渲染类型）"


def render_subagent(idx: int, sub: SubAgent, dur: str = "") -> str:
    # Non-completed status (interrupted/cancelled) is annotated in the title;
    # COMPLETED yields an empty string (zero diff).
    # 非 completed（中断/取消）在标题加注；COMPLETED 为空串（零 diff）
    tag = parsers.wf_status_tag(sub.status, sub.locked_reason)
    out = [f"### 步骤 {idx} · 🤖 子代理：{sub.headline}{dur}{f' · {tag}' if tag else ''}", ""]
    if sub.prompt:
        out += ["**Prompt（任务指令）：**", ""]
        out += ["> " + sub.prompt.replace("\n", "\n> "), ""]
    if sub.steps:
        blocks = [render_step(s) for s in sub.steps]
        blocks = [b for b in blocks if b]
        if blocks:
            out += ["**子代理工作过程：**", ""]
            for b in blocks:
                out += [b, ""]
    if sub.answer:
        out += ["**子代理结论：**", "", sub.answer, ""]
    if sub.sources:
        out += ["**子代理引文：**", ""]
        # List all citations (citation fidelity; the [:20] cap was removed here
        # together with _render_nested_wf).
        # 全量列出（引文保真；同 _render_nested_wf 一并去 [:20] 封顶）
        for s in sub.sources:
            out.append(f"- [{s.name or s.url}]({s.url})")
        out.append("")
    return "\n".join(out)


def _wf_step_subagent(step: dict) -> dict | None:
    return parsers.wf_subagent_payload(step)


def _md_model_links(md: str) -> str:
    """`[label](pplx://action/model_info?id=X&provider=Y)` → `**label**` (model links in council tables).

    `[label](pplx://action/model_info?id=X&provider=Y)` → `**label**`（委员会表格里的模型链接）。"""
    import re as _re
    return _re.sub(r"\[([^\]]+)\]\(pplx://action/[^)]+\)", r"**\1**", md)


def render_wf_step(idx: int, step: dict, sub_map: dict, locked_reason: str | None = None) -> str:
    tool = step.get("tool_name")
    if tool == "council_research":
        # Model council: items are the per-model nested LLM_COUNCIL workflows.
        # Each model's details are folded into <details> (search rounds + all sources +
        # full answer), avoiding a flood of #### headings clashing with the document
        # outline while losing no information.
        # 模型委员会：items 为各模型的嵌套 LLM_COUNCIL 工作流。
        # 各模型细节折叠进 <details>（检索轮次+全部来源+答案完整呈现），
        # 避免大量 #### 与文档大纲层级冲突，同时不丢任何信息。
        title = (step.get("title") or "").strip()
        parts = [f"### 步骤 {idx} · 🏛️ 模型委员会：{title}" if title else f"### 步骤 {idx} · 🏛️ 模型委员会"]
        models_seen = []
        for it in step.get("items") or []:
            wp = (it.get("payload") or {}).get("workflow_payload") or {}
            if wp.get("mode") == "LLM_COUNCIL" and wp.get("model"):
                models_seen.append(wp["model"])
        if models_seen:
            parts.append("**模型：** " + " · ".join(f"`{m}`" for m in models_seen))
        for it in step.get("items") or []:
            wp = (it.get("payload") or {}).get("workflow_payload") or {}
            if wp.get("mode") != "LLM_COUNCIL":
                continue
            model = wp.get("model") or ""
            sub = sub_map.get(model)
            if not sub:
                continue
            n_q = sum(len(st.content.get("queries") or []) for st in sub.steps
                      if st.step_type == "COUNCIL_ROUND")
            head = f"**{wp.get('headline') or model}**（检索 {n_q} 词 · 来源 {len(sub.sources)} · 答案 {len(sub.answer)} 字符）"
            block = ["<details>", f"<summary>{head}</summary>", ""]
            for st in sub.steps:
                if st.step_type != "COUNCIL_ROUND":
                    continue
                qs = st.content.get("queries") or []
                srcs = st.content.get("sources") or []
                if qs:
                    block.append("- " + "、".join(f"`{q}`" for q in qs))
                for i, c in enumerate(srcs, 1):
                    block.append(f"  {i}. [{c.name or c.url}]({c.url})")
            if sub.answer:
                block += ["", "**答案：**", "", _md_model_links(normalize_math_delims(sub.answer))]
            block += ["", "</details>"]
            parts.append("\n".join(block))
        return "\n\n".join(parts)
    wp = _wf_step_subagent(step)
    if tool == "run_subagent" or step.get("icon") == "subagent" or wp:
        sid = (wp.get("id") if wp else None) or (step.get("id") or "").removesuffix(":workflow")
        sub = sub_map.get(sid)
        started = (step.get("started_at") or "")[:19].replace("T", " ")
        completed = (step.get("completed_at") or "")[:19].replace("T", " ")
        dur = f" — {started} → {completed}" if started != completed and started else ""
        if sub:
            return render_subagent(idx, sub, dur)
        tag = parsers.wf_status_tag((wp or {}).get("status"), locked_reason)
        out = [f"### 步骤 {idx} · 🤖 子代理：{(wp or {}).get('headline') or step.get('title') or ''}{dur}{f' · {tag}' if tag else ''}", ""]
        prompt = "".join((wp or {}).get("objective_chunks") or [])
        if prompt:
            out += ["**Prompt（任务指令）：**", "", "> " + prompt.replace("\n", "\n> "), ""]
        # When there is no background match, the step's own items (sub-agent summary
        # TEXT often lands here) must also be rendered, excluding only the
        # workflow_payload anchor itself (observed 1cef522e: no thread, all 5 steps lost).
        # 无 background 匹配时 step 自身的 items（子代理总结 TEXT 常落在这里）也要渲染，
        # 仅排除 workflow_payload 锚点自身（实测 1cef522e 无线程 5 步全丢）
        body_parts = [render_wf_item(it) for it in step.get("items") or []
                      if not (it.get("payload") or {}).get("workflow_payload")]
        body_parts = [b for b in body_parts if b and b.strip()]
        if body_parts:
            out += ["\n\n".join(body_parts), ""]
        return "\n".join(out)
    items = step.get("items") or []
    body_parts = [render_wf_item(it) for it in items]
    body_parts = [b for b in body_parts if b and b.strip()]
    title = (step.get("title") or "").strip()
    head = f"### 步骤 {idx} · {title}" if title else f"### 步骤 {idx}"
    if tool:
        head += f"（`{tool}`）"
    started = (step.get("started_at") or "")[:19].replace("T", " ")
    completed = (step.get("completed_at") or "")[:19].replace("T", " ")
    if started and completed and started != completed:
        head += f" — {started} → {completed}"
    body = "\n\n".join(body_parts)
    return head + ("\n\n" + body if body else "")


def _turn_answer(turn: Turn, sub_map: dict) -> str:
    """Final answer of a turn: plain extraction first; when empty, fall back in order —
    1) TEXT with variant=="answer" in the schematized workflow_block (parsers.wf_block_answer);
    2) the answer of the sub-agent matching a sub-agent anchor (when the main turn only
    does wait_for_subagents, the answer lives on the sub-agent side).
    computer's plain FINAL often contains only workflow_snapshots and is skipped by the
    guard (observed 65/486 empty answers).

    一轮最终答案：plain 提取优先；空时按序兜底——
    1) schematized workflow_block 中 variant=="answer" 的 TEXT（parsers.wf_block_answer）；
    2) 子代理锚点对应的子代理答案（主 turn 只 wait_for_subagents 时答案在子代理侧）。
    computer 的 plain FINAL 常仅含 workflow_snapshots 被守卫跳过（实测 65/486 空答案）。
    """
    if (turn.answer or "").strip():
        return turn.answer
    wf = turn.wf_block or {}
    ans = parsers.wf_block_answer(wf)
    if ans:
        return ans
    for s in wf.get("steps") or []:
        wp = parsers.wf_subagent_payload(s)
        if not wp:
            continue
        sid = wp.get("id") or (s.get("id") or "").removesuffix(":workflow")
        sub = (sub_map or {}).get(sid)
        if sub and (sub.answer or "").strip():
            return sub.answer
    return ""


def _work_process_computer(turn: Turn, sub_map: dict, parts: list) -> None:
    """computer/council work-process section: full wf_block detail; without a block,
    fall back to plain steps (blocks separated by blank lines).

    subagent_result stub turns (zero-workflow notification turns) additionally render the
    time-associated background sub-agent records (turn.stub_wfs, attached by
    parsers.match_stub_workflows); the answer is not backfilled because of this and
    remains (无).

    computer/council 工作过程段：wf_block 全细节；无块时退 plain 步骤（块间空行分隔）。

    subagent_result 桩轮（零工作流通知轮）额外渲染时间关联到的后台子代理记录
    （turn.stub_wfs，parsers.match_stub_workflows 挂载）；答案不因此回填，仍为 (无)。
    """
    wb = turn.wf_block
    if wb:
        steps = wb.get("steps") or []
        wstat = wb.get("status", "")
        # Non-completed status (quota-interrupted/to-be-continued/cancelled) is annotated
        # in the title; COMPLETED yields an empty string (zero diff).
        # 非 completed（限额中断/待续/已取消）在标题加注；COMPLETED 为空串（零 diff）
        wtag = parsers.wf_status_tag(wstat, turn.metadata.get("locked_reason"))
        parts.append(f"## 工作过程（{len(steps)} 步骤 · {wstat}{f' · {wtag}' if wtag else ''}）")
        parts.append("")
        for i, s in enumerate(steps, 1):
            block = render_wf_step(i, s, sub_map, locked_reason=turn.metadata.get("locked_reason"))
            if block.strip():
                parts.append(block)
                parts.append("")
    else:
        blocks = [render_step(s) for s in turn.steps]
        blocks = [b for b in blocks if b]
        if blocks:
            parts.append("## 工作过程")
            parts.append("")
            for b in blocks:
                parts += [b, ""]
    if turn.stub_wfs:
        parts.append(f"## 子代理工作（{len(turn.stub_wfs)} 个）")
        parts.append("")
        parts.append("> 本轮为 subagent_result 通知（自身无工作过程）；以下为按时间关联到的后台子代理记录。")
        parts.append("")
        for wp in turn.stub_wfs:
            wid = wp.get("id")
            block = _render_nested_wf(wp, depth=0,
                                      seen=frozenset({wid}) if wid else None,
                                      label="🤖 子代理",
                                      locked_reason=turn.metadata.get("locked_reason"))
            if block.strip():
                parts.append(block)
                parts.append("")


def _render_turn_body(turn: Turn, mode: str, sub_map: dict) -> str:
    """Body of one turn: Query → work process → Answer → turn citations (scaffolding
    shared by both modes).

    一轮正文：Query → 工作过程 → Answer → 本轮引文（两模式共享脚手架）。"""
    parts = ["## Query", "", turn.query or "(空)", ""]
    if mode in ("computer", "council"):
        _work_process_computer(turn, sub_map, parts)
        answer = _turn_answer(turn, sub_map)
    else:
        blocks = [render_step(s) for s in turn.steps]
        blocks = [b for b in blocks if b]
        if blocks:
            parts += ["## 工作过程", ""] + blocks + [""]
        answer = turn.answer
    parts += ["## Answer", "", _md_model_links(normalize_math_delims(answer)) or "(无)", ""]
    if turn.citations:
        parts += ["## 本轮引文", ""]
        for c in turn.citations:
            parts.append(f"- [{c.name or c.url}]({c.url})")
        parts.append("")
    return "\n".join(parts)


def render_turn(turn: Turn, mode: str, sub_map: dict) -> str:
    head = f"# Turn {turn.index} — {ts_us_to_iso(turn.created_us)}\n\n"
    return head + _render_turn_body(turn, mode, sub_map)


def render_bg_appendix(items: list[dict]) -> list[str]:
    """Thread appendix (attribution waterfall level-3 fallback): background payloads not
    attributed to any turn.

    Each entry carries headline, status annotation, time range, the full steps <details>
    block and citations (reuses _render_nested_wf). It always sits at the end of
    conversation.md (turns/ is not appended to — the appendix is thread-level); no
    time-based attribution guessing; unconsumed payloads of any status
    (interrupted/cancelled/completed/future values) are faithfully archived here.

    线程附录（归属瀑布第三级兜底）：未归入轮次的后台负载。

    每条含 headline、状态标注、时间范围、完整 steps 折叠块与引文（复用 _render_nested_wf）。
    位置恒在 conversation.md 末尾（turns/ 不追加——附录属线程级）；不做时间归属猜测；
    任何状态的未消费负载（中断/取消/已完成/未来取值）都在此如实归档。
    """
    lines = ["## 后台任务（未归入轮次）", "",
             "> 以下后台子代理负载既无轮次内锚点、也未等到 subagent_result 完成通知",
             ">（限额中断/取消等原因），无法归入具体轮次，如实归档于线程末尾。", ""]
    for it in items:
        wp = it["wp"]
        tag = parsers.wf_status_tag(wp.get("status"), it.get("locked_reason"))
        started = (wp.get("started_at") or "")[:19].replace("T", " ")
        ended = (wp.get("completed_at") or it.get("updated") or "")[:19].replace("T", " ")
        meta = f"> 状态：`{wp.get('status') or '未知'}`"
        if tag:
            meta += f" · {tag}"
        if it.get("locked_reason"):
            meta += f" · locked_reason: `{it['locked_reason']}`"
        if started or ended:
            meta += f" · 时间：{started or '?'} → {ended or '?'}"
        lines += [meta, ""]
        wid = wp.get("id")
        lines += [_render_nested_wf(wp, depth=0,
                                    seen=frozenset({wid}) if wid else None,
                                    label="🤖 后台任务",
                                    locked_reason=it.get("locked_reason")), ""]
    return lines


def render_conversation(conv: Conversation, sub_map: dict) -> str:
    lines = [f"# {conv.title}", "",
             f"> 模式: {conv.mode} | 作者: {conv.author} | 轮次: {conv.n_turns} | 引文: {len(conv.citations)}", ""]
    for t in conv.turns:
        # Answers are rendered in full (no longer truncated; the old [:4000] cap cut
        # sentences off mid-way).
        # 答案完整呈现（不再截断；此前 [:4000] 导致断句未完）
        answer = _md_model_links(normalize_math_delims(_turn_answer(t, sub_map)))
        lines += [f"## Turn {t.index} — {ts_us_to_iso(t.created_us)}", "",
                  "### Query", t.query or "(空)", "",
                  "### Answer", answer or "(无)", ""]
    if conv.unconsumed_bgs:
        lines += render_bg_appendix(conv.unconsumed_bgs)
    return "\n".join(lines)
