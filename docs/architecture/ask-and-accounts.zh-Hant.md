---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/ask-and-accounts.zh-CN.md"
translation_source_sha256: "b3f3a26e4ef469a9d1cc9d69acd466cfff37203888b388014ad69bc162b4118c"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="pplx-ask-与多账户" data-pplx-source-anchor="true"></a>
# pplx-ask 與多帳戶

---

<a id="pplx-ask-时序详图" data-pplx-source-anchor="true"></a>
## pplx-ask 時序詳圖

`cmd_ask`（ask_cli.py:86-198）的完整時序：envelope 構造 → SSE 流 → 終態檢查 →
BOT 空間 → 已讀回執 → 人性化遙測 → 複用匯出管線歸檔。

```mermaid
sequenceDiagram
    participant U as agent / 用户
    participant A as ask_cli.cmd_ask
    participant AK as ask_api
    participant P as Perplexity
    participant EX as cmd_export（复用导出管线）

    U->>A: pplx-ask ask "prompt" --mode M [--models ...] [--space S]
    A->>A: --space 非 home 时先解析空间 uuid<br/>_resolve_space_uuid（ask_cli.py:74-83）
    A->>AK: build_envelope(prompt, mode, models, target_uuid)（ask_api.py:71）
    Note over AK: mode → model_preference 映射（MODE_MODEL，ask_api.py:36-41）：<br/>search→pplx_pro / deep-research→pplx_alpha /<br/>council→pplx_agentic_research / study→pplx_study；<br/>mode 恒为 "copilot"；council 槽位校验 2–3 个模型<br/>（ask_api.py:85-90），缺省 COUNCIL_DEFAULT_MODELS
    AK-->>A: {"params": {模板参数}, "query_str": prompt}
    A->>AK: sse_ask(transport, envelope, on_event)（ask_api.py:153）
    AK->>P: POST /rest/sse/perplexity_ask（ASK_URL，ask_api.py:28）<br/>Accept: text/event-stream；复用 CookieTransport 内部 opener/cookie（ask_api.py:114-130）
    loop SSE 事件流（空行分隔，_parse_sse，ask_api.py:101-111）
        P-->>AK: data: {...backend_uuid / status / text 增量...}
        AK-->>A: on_event：首见 backend_uuid 记线程创建<br/>status 变化打印；text 每 +200 字符报进度（ask_cli.py:106-119）
    end
    AK-->>A: final_sse_message 终止，返回最终事件（ask_api.py:164-165）
    A->>A: 终态检查：final_status != COMPLETED → SystemExit<br/>不移空间/不遥测/不导出（ask_cli.py:134-140）
    A->>AK: move_threads([context_uuid], BOT_SPACE_UUID)（ask_api.py:169）
    AK->>P: POST /rest/collections/batch_move_threads<br/>（用 context_uuid 不是 entryUUID；BOT 空间取自用户级配置 bot_space.uuid）
    opt --mark-read
        A->>AK: mark_read(context_uuid)（ask_api.py:190）
        AK->>P: POST /rest/thread/mark_viewed（unread 立即翻转）
    end
    opt 默认开启（--no-telemetry 关闭）
        A->>AK: send_view_telemetry（ask_api.py:234）
        AK->>P: POST /rest/event/analytics ×4：<br/>ask context pane viewed → thread viewed<br/>→ ask context pane viewed → thread entry exited<br/>（设备池随机 + 事件间 0.6–2.4s 随机停顿<br/>+ timeOnEntryMs 12–45s，ask_api.py:266-278）
    end
    opt 默认开启（--no-export 关闭）
        A->>EX: cmd_export(adapter, writer, backend_uuid, force=True)（ask_cli.py:192）
        EX->>P: 走完整导出管线（export-pipeline.md §3）
        EX-->>A: web_archive 落盘
    end
    A-->>U: 机器可读 JSON：thread_uuid / thread_url /<br/>context_uuid / moved_to_bot / mark_read / telemetry（布尔）<br/>/ step_errors（仅失败步骤）/ exported（ask_cli.py 末段）
```

設計要點：

- **envelope 是實測參數模板**：`_BASE_PARAMS`（ask_api.py:44-68）25 個固定鍵
  （含 32 項 `supported_block_use_cases`、語言/時區/搜尋焦點等），`build_envelope`
  再注入 mode/模型/frontend_uuid 等欄位，與瀏覽器真實提交一致（對照
  [../reference/api/api-rest-endpoints.md](../reference/api/api-rest-endpoints.md) §3.9 與 `docs/perplexity-api-samples/` 的 39-params 樣本）。
- **SSE 消費不走 Transport ABC**：流式介面不在 `get_json/post_json/download`
  抽象內，`post_stream` 直接複用 `CookieTransport` 的 `_cookie_header`/`_opener`
  （ask_api.py:126-130）——這是 [§1](overview.md) 提到的刻意耦合。
- **遙測的人性化**：`_DEVICE_POOL` 三設備隨機（ask_api.py:210-214）、隨機停頓、
  隨機閱讀時長，事件 schema 與瀏覽器實測逐項對齊（`_telemetry_event`，
  ask_api.py:217-231）；已讀回執與遙測分離——analytics 的 "thread viewed" 不翻轉
  unread，真回執是 `mark_viewed`（ask_api.py:194-201 註釋）。

---

<a id="多账户-cookie-切换流程" data-pplx-source-anchor="true"></a>
## 多帳戶 cookie 切換流程

cookie 解析與帳戶校驗在 `commands/common.py:make_transport`（common.py:93-155）；
來源列舉在 `core/cookies/loaders.py`；webbridge 通路校驗在 `_validate_bridge_account`
（common.py:158-187）。

```mermaid
flowchart TD
    START(["make_transport(account, ...)"]) --> MODE{"transport_mode？"}
    MODE -->|"webbridge（显式指定）"| WB1["WebBridgeTransport（bridge_transport.py:22）"]
    WB1 --> WB2{"_validate_bridge_account<br/>GET /api/auth/session（common.py:173）"}
    WB2 -->|"email 匹配或未登记"| WBOK(("返回 bridge"))
    WB2 -->|"email 不符"| WBERR["SystemExit：请先切换浏览器账户（common.py:177-179）"]
    WB2 -->|"bridge 不可达"| WBWARN["仅 log.warning 放行<br/>（备用通路不硬失败，common.py:186-187）"]
    WBWARN --> WBOK

    MODE -->|"cookie（默认）"| SRC{"cookie 来源优先级<br/>cookies.resolve（cookies/loaders.py:203-235）"}
    SRC -->|"1. --cookies-from 指定浏览器"| F1["from_browser（cookies/loaders.py:51）"]
    SRC -->|"2. --cookies 文件"| F2["from_file：Netscape / JSON 两种格式<br/>#HttpOnly_ 前缀还原（cookies/loaders.py:142-182）"]
    SRC -->|"3. 新鲜缓存"| F3["CookieCache.load<br/>&lt;out&gt;/index/.cookies.json，12h 新鲜期<br/>（cookies/cache.py:33-47）"]
    SRC -->|"4. auto-detect"| F4["edge → chrome → firefox → safari<br/>（AUTO_DETECT_ORDER，cookies/loaders.py:32）<br/>browser_cookie3 解密"]
    F1 --> SESS
    F2 --> SESS
    F3 --> SESS
    F4 --> SESS
    SESS{"GET /api/auth/session<br/>取当前 email（common.py:126-128）"}
    SESS -->|"email == ACCOUNT_EMAIL[account]<br/>（用户级配置 accounts.&lt;名&gt;.email）"| OK(("CookieTransport 就绪<br/>+ CookieCache.save 刷新缓存（common.py:150）"))
    SESS -->|"未登记 email"| WARN2["log.warning 提示登记，放行（common.py:146-149）"] --> OK
    SESS -->|"email 不符"| SW["_try_switch_account（common.py:190-215）"]
    SW --> ENUM["list_account_tokens（cookies/loaders.py:108-139）<br/>枚举浏览器 __Secure-pplx.session.&lt;uid&gt;<br/>（www 子域条目优先）"]
    ENUM --> LOOP{"逐令牌：替换<br/>__Secure-next-auth.session-token<br/>（ACTIVE_SESSION_COOKIE，cookies/loaders.py:105）"}
    LOOP --> PROBE["新 CookieTransport 探测<br/>GET /api/auth/session（common.py:207-208）"]
    PROBE -->|"email 匹配"| SWOK(("切换成功：用新 cookie 表<br/>重建 CookieTransport（common.py:136-140）"))
    PROBE -->|"不匹配"| LOOP
    LOOP -->|"全部失败"| ERR["SystemExit：列出目标 email 与当前 email<br/>提示先在浏览器登录（common.py:142-145）"]
```

要點：

- **多帳戶模型**：同瀏覽器每帳戶一條 `__Secure-pplx.session.<uid>` cookie；
  切換 = 把目標帳戶那條的值寫進 `__Secure-next-auth.session-token`（cookies/loaders.py:113-120
  註釋；機制實測見 [../reference/api/api-authentication.md](../reference/api/api-authentication.md) §1.2）。無需操作瀏覽器 UI。
- **快取跟隨 `--out`**：`<out_root>/index/.cookies.json`（common.py:111），
  含 fetched_at/source/account_email，成功校驗後總是重新整理（common.py:150）。
- **webbridge 與 cookie 互斥**：`--cookies/--cookies-from` 與 `--transport webbridge`
  同給即報錯（cli.py:229-233；common.py:112-116）。
- `core/auth.py:CredentialProvider`（WebBridge 提取 cookie：CDP Storage.getCookies
  優先、document.cookie 兜底，auth.py:41-67）屬**預留降級鏈**，當前唯一呼叫方是
  `cookies.from_webbridge`（cookies/loaders.py:185-200）。
