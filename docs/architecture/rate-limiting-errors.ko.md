---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/rate-limiting-errors.zh-CN.md"
translation_source_sha256: "9c19c03d4ae62113daaab5c670d6160363ca68fd7ec1684ae5bf842883da8754"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="限频与错误处理" data-pplx-source-anchor="true"></a>
# 속도 제한 및 오류 처리

<a id="限频与错误处理_1" data-pplx-source-anchor="true"></a>
## 속도 제한 및 오류 처리

두 계층의 속도 제한: `Throttle`(core/throttle.py:15) + `CookieTransport._request`
(core/http/cookie_transport.py:63-126)의 오류 분기; 배치 계층에 추가로 fail-fast.

```mermaid
flowchart TD
    REQ["_request 发起请求<br/>max_retries=3（cookie_transport.py:48）"] --> R{结果}
    R -->|"2xx"| OK["throttle.reset 清零退避计数<br/>（cookie_transport.py:77）<br/>避免跨请求单调累积"]
    R -->|"401 / 403"| AUTH["AuthTransportError 立即抛<br/>（cookie_transport.py:82-85）<br/>鉴权失败退避无法自愈"]
    R -->|"429"| RL["RateLimitError + throttle.backoff<br/>继续重试（cookie_transport.py:86-92）"]
    R -->|"400 且 body 含 ENTRY_DELETED"| DEL["EntryDeletedError 终态（cookie_transport.py:93-95）<br/>继承 EntryExpiredError——batch 须先于<br/>EXPIRED 捕获（batch_cmd.py:163-174）<br/>标 mark_deleted 不再重试（offline-operations.md §17）"]
    R -->|"400 且 body 含 ENTRY_EXPIRED"| EXP["EntryExpiredError 终态<br/>（cookie_transport.py:96-98）<br/>batch 标 mark_expired 不再重试"]
    R -->|"500 / 502 / 503 / 504"| S5["TransportError + backoff<br/>至少退避重试一次（cookie_transport.py:99-107）<br/>504 为 Cloudflare 常见瞬态"]
    R -->|"404 等其他码"| NF["TransportError，break 不再重试<br/>（cookie_transport.py:108-116）<br/>绝不映射 EntryExpiredError：pplx-ask<br/>建线程后立即导出可能瞬态 404（传播延迟），<br/>终态会把暂不可见的活线程误葬"]
    R -->|"网络层异常"| NET["TransportError + backoff<br/>继续重试（cookie_transport.py:117-125）"]
    RL --> REQ
    S5 --> REQ
    NET --> REQ

    subgraph THR["Throttle（throttle.py:15-53）"]
        D1["delay：uniform(delay_min, delay_max)<br/>batch 默认 10–20s（cli.py:126-129）"]
        D2["backoff：delay_max × 3^N<br/>±20% jitter 防同步，封顶 300s<br/>N = 连续失败计数（throttle.py:38-50）"]
        D3["reset：成功清零（throttle.py:52）"]
    end

    subgraph BF["batch 层三连 fail-fast（batch_cmd.py）"]
        F1["AuthTransportError：auth_fails += 1<br/>连续 3 次（_AUTH_FAIL_FAST，batch_cmd.py:43）<br/>→ save + SystemExit 中止<br/>（cookie 失效时空转会让数百线程各失败一遍）"]
        F2["其他异常：auth_fails 清零<br/>mark_error + throttle.backoff 继续（batch_cmd.py:195-200）"]
        F3["KeyboardInterrupt：save 后抛出（batch_cmd.py:158-161）"]
    end

    AUTH --> F1
    DEL --> DONE1
    EXP --> DONE1(["终态登记"])
    OK --> DONE2(["mark_ok"])

    subgraph LIM["限频纪律（用户明确要求的防封号红线）"]
        L1["线程间随机 10–20s，无并发"]
        L2["翻页 ≥3s（rest.py:39）<br/>blocks 补抓前 ≥4s（adapter.py:28,88）<br/>空间元数据 ≥3s（spaces_cmd.py:328）<br/>usage / backfill 元数据 ≥3s"]
        L3["资产下载间隔 0.5s（assets.py:28,103）<br/>backfill 在线阶段 CDN 下载并发 6 线程<br/>（CDN 非 API，assets_backfill_cmd.py:460-475）"]
    end
```

- **WebBridgeTransport**는 429 백오프 정렬, 성공 시 `throttle.reset()` 초기화
  (bridge_transport.py); 오류 분류는 CookieTransport에 정렬됨——401/403 →
  `AuthTransportError`, 400 및 본문에 ENTRY_EXPIRED 포함 → `EntryExpiredError`,
  5xx 백오프 재시도, 배치의 인증 fail-fast와 만료 최종 상태는
  `--transport webbridge`에서도 동일하게 적용됨; 데몬의 비-JSON 응답은
  TransportError로 수렴(URLError/JSONDecodeError/OSError 통합 캐치); 나머지 200이 아닌 응답은 직접
  TransportError.
- **공유 Throttle**: 배치가 동일 인스턴스를 CookieTransport에 전달(cli.py:280-282),
  전송 계층과 배치 계층의 백오프 카운트 통합; **계정 자동 전환 후 재구축해도 손실되지 않음**
  (common.py:139에도 동일하게 전달); 단일 명령 시 전달하지 않으면 CookieTransport가 기본 인스턴스 자체 생성
  (cookie_transport.py:49).
