---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/ask-and-accounts.zh-CN.md"
translation_source_sha256: "b3f3a26e4ef469a9d1cc9d69acd466cfff37203888b388014ad69bc162b4118c"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="pplx-ask-与多账户" data-pplx-source-anchor="true"></a>
# pplx-ask 및 다중 계정

---

<a id="pplx-ask-时序详图" data-pplx-source-anchor="true"></a>
## pplx-ask 시퀀스 상세 다이어그램

`cmd_ask`(ask_cli.py:86-198)의 전체 시퀀스: envelope 구성 → SSE 스트림 → 최종 상태 확인 →
BOT 공간 → 읽음 확인 → 인간화된 원격 측정 → 재사용 내보내기 파이프라인 아카이브.

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

설계 포인트:

- **envelope은 실제 측정된 매개변수 템플릿**입니다: `_BASE_PARAMS`(ask_api.py:44-68) 25개의 고정 키
  (32개 항목의 `supported_block_use_cases`, 언어/시간대/검색 포커스 등 포함), `build_envelope`가
  mode/모델/frontend_uuid 등의 필드를 추가로 주입하며, 브라우저의 실제 제출과 일치합니다(참조:
  [../reference/api/api-rest-endpoints.md](../reference/api/api-rest-endpoints.md) §3.9 및 `docs/perplexity-api-samples/`의 39-params 샘플).
- **SSE 소비는 Transport ABC를 따르지 않음**: 스트리밍 인터페이스는 `get_json/post_json/download`
  추상화 내에 있지 않으며, `post_stream`는 `CookieTransport`의 `_cookie_header`/`_opener`를 직접 재사용합니다
  (ask_api.py:126-130) — 이는 [§1](overview.md)에서 언급된 의도적인 결합입니다.
- **원격 측정의 인간화**: `_DEVICE_POOL` 세 장치 무작위(ask_api.py:210-214), 무작위 지연,
  무작위 읽기 시간, 이벤트 스키마는 브라우저 실제 측정과 항목별로 정렬됩니다(`_telemetry_event`,
  ask_api.py:217-231); 읽음 확인과 원격 측정은 분리됨 — analytics의 "thread viewed"는 unread를
  변경하지 않으며, 실제 확인은 `mark_viewed`입니다(ask_api.py:194-201 주석).

---

<a id="多账户-cookie-切换流程" data-pplx-source-anchor="true"></a>
## 다중 계정 쿠키 전환 흐름

쿠키 파싱 및 계정 검증은 `commands/common.py:make_transport`(common.py:93-155)에서 수행;
소스 열거는 `core/cookies/loaders.py`에서; webbridge 경로 검증은 `_validate_bridge_account`에서
(common.py:158-187).

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

요점:

- **다중 계정 모델**: 동일 브라우저에서 계정당 하나의 `__Secure-pplx.session.<uid>` 쿠키;
  전환 = 대상 계정의 값을 `__Secure-next-auth.session-token`에 쓰기(cookies/loaders.py:113-120
  주석; 메커니즘 실제 측정은 [../reference/api/api-authentication.md](../reference/api/api-authentication.md) §1.2 참조). 브라우저 UI 조작 불필요.
- **캐시는 `--out`를 따름**: `<out_root>/index/.cookies.json`(common.py:111),
  fetched_at/source/account_email 포함, 성공적인 검증 후 항상 새로고침(common.py:150).
- **webbridge와 쿠키는 상호 배타적**: `--cookies/--cookies-from`와 `--transport webbridge`를
  동시에 제공하면 오류 발생(cli.py:229-233; common.py:112-116).
- `core/auth.py:CredentialProvider`(WebBridge 쿠키 추출: CDP Storage.getCookies
  우선, document.cookie 대체, auth.py:41-67)는 **예비 폴백 체인**이며, 현재 유일한 호출자는
  `cookies.from_webbridge`(cookies/loaders.py:185-200)입니다.
