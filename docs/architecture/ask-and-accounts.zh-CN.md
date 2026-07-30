# pplx-ask 与多账户

---

## pplx-ask 时序详图

`cmd_ask`（ask_cli.py:85-197）的完整时序：envelope 构造 → SSE 流 → 终态检查 →
BOT 空间 → 已读回执 → 人性化遥测 → 复用导出管线归档。

```mermaid
sequenceDiagram
    participant U as agent / 用户
    participant A as ask_cli.cmd_ask
    participant AK as ask_api
    participant P as Perplexity
    participant EX as cmd_export（复用导出管线）

    U->>A: pplx-ask ask "prompt" --mode M [--models ...] [--space S]
    A->>A: --space 非 home 时先解析空间 uuid<br/>_resolve_space_uuid（ask_cli.py:73-82）
    A->>AK: build_envelope(prompt, mode, models, target_uuid)（ask_api.py:71）
    Note over AK: mode → model_preference 映射（MODE_MODEL，ask_api.py:36-41）：<br/>search→pplx_pro / deep-research→pplx_alpha /<br/>council→pplx_agentic_research / study→pplx_study；<br/>mode 恒为 "copilot"；council 槽位校验 2–3 个模型<br/>（ask_api.py:85-90），缺省 COUNCIL_DEFAULT_MODELS
    AK-->>A: {"params": {模板参数}, "query_str": prompt}
    A->>AK: sse_ask(transport, envelope, on_event)（ask_api.py:153）
    AK->>P: POST /rest/sse/perplexity_ask（ASK_URL，ask_api.py:28）<br/>Accept: text/event-stream；复用 CookieTransport 内部 opener/cookie（ask_api.py:114-130）
    loop SSE 事件流（空行分隔，_parse_sse，ask_api.py:101-111）
        P-->>AK: data: {...backend_uuid / status / text 增量...}
        AK-->>A: on_event：首见 backend_uuid 记线程创建<br/>status 变化打印；text 每 +200 字符报进度（ask_cli.py:105-118）
    end
    AK-->>A: final_sse_message 终止，返回最终事件（ask_api.py:164-165）
    A->>A: 终态检查：final_status != COMPLETED → SystemExit<br/>不移空间/不遥测/不导出（ask_cli.py:133-139）
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
        A->>EX: cmd_export(adapter, writer, backend_uuid, force=True)（ask_cli.py:191）
        EX->>P: 走完整导出管线（export-pipeline.md §3）
        EX-->>A: web_archive 落盘
    end
    A-->>U: 机器可读 JSON：thread_uuid / thread_url /<br/>context_uuid / moved_to_bot / mark_read / telemetry（布尔）<br/>/ step_errors（仅失败步骤）/ exported（ask_cli.py 末段）
```

设计要点：

- **envelope 是实测参数模板**：`_BASE_PARAMS`（ask_api.py:44-68）25 个固定键
  （含 32 项 `supported_block_use_cases`、语言/时区/搜索焦点等），`build_envelope`
  再注入 mode/模型/frontend_uuid 等字段，与浏览器真实提交一致（对照
  [../reference/api/api-rest-endpoints.md](../reference/api/api-rest-endpoints.md) §3.9 与 `docs/perplexity-api-samples/` 的 39-params 样本）。
- **SSE 消费不走 Transport ABC**：流式接口不在 `get_json/post_json/download`
  抽象内，`post_stream` 直接复用 `CookieTransport` 的 `_cookie_header`/`_opener`
  （ask_api.py:126-130）——这是 [§1](overview.md) 提到的刻意耦合。
- **遥测的人性化**：`_DEVICE_POOL` 三设备随机（ask_api.py:210-214）、随机停顿、
  随机阅读时长，事件 schema 与浏览器实测逐项对齐（`_telemetry_event`，
  ask_api.py:217-231）；已读回执与遥测分离——analytics 的 "thread viewed" 不翻转
  unread，真回执是 `mark_viewed`（ask_api.py:194-201 注释）。

---

## 多账户 cookie 切换流程

cookie 解析与账户校验在 `commands/common.py:make_transport`（common.py:93-155）；
来源枚举在 `core/cookies/loaders.py`；webbridge 通路校验在 `_validate_bridge_account`
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

    MODE -->|"cookie（默认）"| SRC{"cookie 来源优先级<br/>cookies.resolve（cookies/loaders.py:270-302）"}
    SRC -->|"1. --cookies-from 指定浏览器"| F1["from_browser（cookies/loaders.py:107）"]
    SRC -->|"2. --cookies 文件"| F2["from_file：Netscape / JSON 两种格式<br/>#HttpOnly_ 前缀还原（cookies/loaders.py:209-249）"]
    SRC -->|"3. 新鲜缓存"| F3["CookieCache.load<br/>&lt;out&gt;/index/.cookies.json，12h 新鲜期<br/>（cookies/cache.py:33-47）"]
    SRC -->|"4. auto-detect"| F4["edge → chrome → firefox → safari<br/>（AUTO_DETECT_ORDER，cookies/loaders.py:39）<br/>browser_cookie3 解密"]
    F1 --> SESS
    F2 --> SESS
    F3 --> SESS
    F4 --> SESS
    SESS{"GET /api/auth/session<br/>取当前 email（common.py:126-128）"}
    SESS -->|"email == ACCOUNT_EMAIL[account]<br/>（用户级配置 accounts.&lt;名&gt;.email）"| OK(("CookieTransport 就绪<br/>+ CookieCache.save 刷新缓存（common.py:150）"))
    SESS -->|"未登记 email"| WARN2["log.warning 提示登记，放行（common.py:146-149）"] --> OK
    SESS -->|"email 不符"| SW["_try_switch_account（common.py:190-215）"]
    SW --> ENUM["list_account_tokens（cookies/loaders.py:175-206）<br/>枚举浏览器 __Secure-pplx.session.&lt;uid&gt;<br/>（www 子域条目优先）"]
    ENUM --> LOOP{"逐令牌：替换<br/>__Secure-next-auth.session-token<br/>（ACTIVE_SESSION_COOKIE，cookies/loaders.py:172）"}
    LOOP --> PROBE["新 CookieTransport 探测<br/>GET /api/auth/session（common.py:207-208）"]
    PROBE -->|"email 匹配"| SWOK(("切换成功：用新 cookie 表<br/>重建 CookieTransport（common.py:136-140）"))
    PROBE -->|"不匹配"| LOOP
    LOOP -->|"全部失败"| ERR["SystemExit：列出目标 email 与当前 email<br/>提示先在浏览器登录（common.py:142-145）"]
```

要点：

- **多账户模型**：同浏览器每账户一条 `__Secure-pplx.session.<uid>` cookie；
  切换 = 把目标账户那条的值写进 `__Secure-next-auth.session-token`（cookies/loaders.py:180-187
  注释；机制实测见 [../reference/api/api-authentication.md](../reference/api/api-authentication.md) §1.2）。无需操作浏览器 UI。
- **缓存跟随 `--out`**：`<out_root>/index/.cookies.json`（common.py:111），
  含 fetched_at/source/account_email，成功校验后总是刷新（common.py:150）。
- **webbridge 与 cookie 互斥**：`--cookies/--cookies-from` 与 `--transport webbridge`
  同给即报错（cli.py:228-232；common.py:112-116）。
- `core/auth.py:CredentialProvider`（WebBridge 提取 cookie：CDP Storage.getCookies
  优先、document.cookie 兜底，auth.py:42-68）属**预留降级链**，当前唯一调用方是
  `cookies.from_webbridge`（cookies/loaders.py:252-267）。
