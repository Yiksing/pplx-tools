---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/rate-limiting-errors.zh-CN.md"
translation_source_sha256: "8862ac055e64ad50ae8040283ae348b19913ee27457417be687f1b9edc200e48"
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
  (bridge_transport.py); 오류 분류는 CookieTransport에 맞춰 정렬됨—401/403 →
  `AuthTransportError`, 400 및 body에 ENTRY_EXPIRED 포함 → `EntryExpiredError`,
  5xx 백오프 재시도, 배치의 인증 fail-fast와 만료 최종 상태는
  `--transport webbridge`에서도 동일하게 적용; 데몬의 비-JSON 응답은
  TransportError로 수렴(URLError/JSONDecodeError/OSError 통합 캐치); 나머지 200이 아닌 응답은 직접
  TransportError.
- **공유 Throttle**: 배치는 동일 인스턴스를 CookieTransport에 전달(cli.py:280-282),
  전송 계층과 배치 계층의 백오프 카운트가 통일됨; **계정 자동 전환 후 재구축해도 손실되지 않음**
  (common.py:139에도 동일하게 전달); 단일 명령 시 전달하지 않으면 CookieTransport가 기본 인스턴스 자체 생성
  (cookie_transport.py:49).
- **하트비트(기본 설정)**. 세 가지 긴 대기—`Throttle.backoff` 수면, 중단된 진행 중 요청
  (`CookieTransport._open_read`), 유휴 `pplx-ask` SSE 스트림(`ask_api.post_stream`)
  —이제 모두 INFO "아직 대기 중" 하트비트를 출력하여 대기를 중단으로 오인하지 않도록 함. 백오프는 분할 수면
  (`Throttle._sleep_with_heartbeat`)으로 수행되며, 각 분할의 합은 동일한 총 시간이므로 리스크 관리
  리듬/예산은 변경되지 않고 가시성만 향상됨; `-v`는 여전히 전체 DEBUG 추적을 포함.
- **`--skip-auth-check` + 지연 검증**. 시작 시 계정 소유 세션 탐지(`common.py`,
  `make_transport`)를 건너뛸 수 있어 네트워크 상태가 나쁠 때 초기 장시간 대기를 방지. 안전망으로 `batch`는
  일반 오류가 누적된 후 일회성 `report_account_status`(`common.py`; `batch_cmd.py`)을 수행하여
  쿠키 만료/계정 불일치/계정 정상(즉, 오류가 네트워크 또는 속도 제한으로 인한 경우)을 알림.
