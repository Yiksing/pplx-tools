---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/troubleshooting.zh-CN.md"
translation_source_sha256: "acbc884bfd36c355b9390405dcc2875b1bfb8d762e0fd7cf01f740fd3f2edc7c"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="故障排查" data-pplx-source-anchor="true"></a>
# 문제 해결

FAQ 형식: 각 항목은 **문제 → 원인 → 해결** 순서로 구성됩니다. 전체 오류 의미 참조(상태 코드, 최종 상태, 재시도 규칙)는 [응답 및 오류](../reference/api/api-responses-errors.md) 및 [속도 제한 및 오류](../architecture/rate-limiting-errors.md)를 참조하세요.

<a id="裸请求-api-遭遇-cloudflare-403" data-pplx-source-anchor="true"></a>
## 원시 요청 API에서 Cloudflare 403 발생

**문제**: 수동 `curl` / 스크립트 요청 `www.perplexity.ai`의 REST 엔드포인트가 403 및 Cloudflare 챌린지 페이지를 반환합니다. 브라우저에서 복사한 쿠키를 사용해도 마찬가지이며, 동일한 엔드포인트를 도구로 호출하면 정상 작동합니다.

**원인**: Cloudflare가 사이트 앞단에서 보호하며, `cf_clearance` / `__cf_bm`는 브라우저의 TLS 지문과 연결됩니다. 원시 클라이언트의 지문이 일치하지 않으면 챌린지가 트리거됩니다. 도구가 통과하는 이유는 Python `urllib` + 브라우저에서 가져온 쿠키 + 데스크톱 Chrome `User-Agent` (`pplx_export/core/http/cookie_transport.py:29`)을 사용하기 때문입니다. Cloudflare가 속도 제한 시에도 403을 반환할 수 있으며, 이때 응답은 동일한 챌린지 형태를 띱니다.

**해결**:

- 도구의 transport를 우회하지 마십시오. 임시 스크립트를 작성하지 말고 `pplx-export` / `pplx-ask`를 사용하여 호출하십시오.
- 도구 내부에서 HTTP 200이지만 JSON이 아닌 응답 본문(Cloudflare 통과 페이지)을 데이터가 아닌 전송 오류로 분류합니다 (`pplx_export/core/http/cookie_transport.py:133`).
- 도구 내에서 403이 발생하기 시작하면 속도를 늦추고([속도 제한](rate-limiting.md) 참조) 쿠키를 새로 고치십시오. 지속적인 챌린지는 브라우저에서 다시 로그인해야 합니다.
- 403의 두 가지 유형에 주의하십시오: Cloudflare 속도 제한 챌린지(속도만 늦추면 해결됨)와 API 수준 403(쿠키 만료 - 즉시 발생, 백오프 없음, 다음 섹션 참조). 설계 페이지는 후자를 매핑합니다 ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

배경: [API 인증](../reference/api/api-authentication.md).

<a id="401-错误-cookie-过期" data-pplx-source-anchor="true"></a>
## 401 오류 / 쿠키 만료

**문제**: 명령이 인증 오류로 실패합니다. `pplx-export`가 `AuthTransportError: 鉴权失败 401`를 발생시키거나, `pplx-ask ask`가 HTTP 401/403과 함께 "쿠키 업데이트" 메시지를 출력하며 종료됩니다.

**원인**: 세션 쿠키가 만료되었거나 유효하지 않습니다. `401`/`403`는 인증 실패로 간주되어 즉시 발생합니다. 백오프하지 않습니다. 백오프로는 만료된 세션을 복구할 수 없기 때문입니다 (`pplx_export/core/http/cookie_transport.py:82`; `pplx_export/core/errors.py:68`). `batch`는 연속 3회 인증 실패 후 fail-fast하여 만료된 쿠키가 전체 큐를 소진하는 것을 방지합니다.

**해결**:

1. 브라우저에서 다시 로그인(또는 사이트 재방문)하여 세션 쿠키를 갱신합니다.
2. 도구의 쿠키 캐시를 새로 고칩니다. `<out>/index/.cookies.json`는 12시간의 신선도 기간 내에 재사용됩니다 (`pplx_export/core/cookies/cache.py:22`). 따라서 다시 로그인한 후 다음 중 하나를 수행하십시오:
   - `--cookies-from <browser>` 플래그와 함께 실행하여 브라우저에서 강제로 다시 가져오기; 또는
   - `<out>/index/.cookies.json`를 삭제하여 다음 실행 시 자동으로 다시 가져오도록 합니다.
3. 각 성공적인 실행은 캐시를 다시 저장합니다 (`pplx_export/commands/common.py:150`). 일상적인 실행은 스스로 신선도를 유지합니다.

설정 세부 사항: [빠른 시작](getting-started.md) · [설정](configuration.md).

<a id="linux-cookie-解密" data-pplx-source-anchor="true"></a>
## Linux 쿠키 복호화

**문제**: Linux에서 auto-detect(또는 `--cookies-from chrome` 등)가 브라우저 쿠키 데이터베이스를 읽지 못합니다. 브라우저가 로그인 상태임에도 불구하고 발생합니다.

**메커니즘**: Linux의 Chromium 계열 브라우저는 OS 키링에 저장된 키로 쿠키 데이터베이스를 암호화하며, 런타임에 Secret Service D-Bus API를 통해 해당 키를 가져옵니다. `browser_cookie3`는 순수 Python `jeepney`을 통해 D-Bus에 접근합니다. 이는 도구와 함께 Linux에 설치되며 추가 설정이 필요 없습니다. 키링 응답이 없으면 레거시 `peanuts` 비밀번호로 폴백하며, 이 비밀번호는 Chrome이 키링 없이 기록한 쿠키만 해독할 수 있습니다. 키링이 존재하지만 D-Bus 쿼리 자체가 전송 계층에서 실패하는 경우(예: 세션 버스가 익명 접근을 거부), `browser_cookie3` 자체의 폴백 체인이 작동하지 않습니다. 도구는 이 상황을 감지하고 키링을 우회하여 Chromium 기본 비밀번호로 한 번 재시도합니다. 이는 Chromium이 키링을 사용할 수 없을 때 자체적으로 사용하는 키입니다 (`pplx_export/core/cookies/loaders.py:62-104`, 로드 경로는 `loaders.py:136-153`). Firefox는 이와 관련이 없습니다. `cookies.sqlite`는 암호화되지 않습니다.

**매트릭스**:

| 계층 | 상황 | 결과 |
|---|---|---|
| 브라우저 | Firefox | 문제 없음 - `cookies.sqlite` 암호화되지 않음 |
| 브라우저 | Chromium + 키링 접근 가능 | 정상 - Secret Service를 통해 키 획득 |
| 브라우저 | Chromium + 키링 없음 | `peanuts` 경로 - Chrome이 키링 없이 기록한 경우에만 유효 |
| 브라우저 | Chromium + 키링 접근 불가 (D-Bus 계층 실패) | 도구가 자동으로 Chromium 기본 비밀번호로 재시도 - 접근성은 `peanuts` 경로와 동일 |
| 설치 방식 | 네이티브 패키지 | auto-detect (browser_cookie3 내장 경로) |
| 설치 방식 | snap / flatpak | auto-detect - 내장 프로필 레지스트리가 `~/snap/<name>/...` 및 `~/.var/app/<app-id>/...` 아래 프로필을 포함 (`pplx_export/core/cookies/profiles.py:37-67`) |
| 데스크톱 환경 | GNOME | 일반적으로 즉시 사용 가능 (gnome-keyring) |
| 데스크톱 환경 | KDE | KWallet 설정에서 **Use KWallet for the Secret Service interface** 체크 |
| 데스크톱 환경 | 헤드리스 / 최소 | D-Bus 세션 버스 없음 → `peanuts` 경로 |
| 배포판 | Debian / Ubuntu | `libsecret-1-0` + `gnome-keyring` 설치 |
| 배포판 | Fedora / RHEL | `libsecret` + `gnome-keyring` 설치; 최소/서버 설치는 종종 키링이 전혀 없음 - 가장 흔한 실패 원인 |
| 배포판 | Arch | 동일한 메커니즘, 패키지 이름만 다름 |

샌드박스 설치는 추가 인수가 필요 없습니다: 먼저 네이티브 경로를 탐색한 다음, 레지스트리에 따라 명시적 `cookie_file=`로 snap/flatpak의 쿠키 데이터베이스를 탐색합니다 (`pplx_export/core/cookies/loaders.py:155-168`).

**시나리오 → 권장 채널**:

| 시나리오 | 권장 채널 |
|---|---|
| Firefox 사용 | `--cookies-from firefox` - 문제 없음 |
| 데스크톱 GNOME / KDE | auto-detect 사용 |
| snap / flatpak 브라우저 | auto-detect - 레지스트리 포함; 그렇지 않으면 브라우저 확장으로 `--cookies FILE` 내보내기 |
| 헤드리스 서버 | `--cookies FILE` - 일반 폴백; 최후의 수단은 `--transport webbridge` |

<a id="导出用了错误的账户多账户" data-pplx-source-anchor="true"></a>
## 잘못된 계정으로 내보내기 (다중 계정)

**문제**: 아카이브 스레드가 잘못된 계정의 세션으로 가져와졌습니다. 예를 들어 `--account alice` 실행이 실제로 `bob`로 데이터를 가져오거나, 아카이브에 대상 계정이 아닌 스레드가 포함됩니다.

**원인**: 동일한 브라우저에 여러 계정이 로그인된 경우, 활성 세션 토큰 (`__Secure-next-auth.session-token`)이 다른 계정에 속할 수 있습니다. 대상 계정의 `email`가 사용자 수준 설정에 등록되지 않으면 도구가 이를 인식하지 못하고 경고만 기록합니다.

**도구의 방지 메커니즘** (`pplx_export/commands/common.py:93`): 시작 시 transport가 `GET /api/auth/session`를 호출하여 실시간 이메일을 등록된 값과 비교합니다. 일치하지 않으면 브라우저에 있는 각 계정의 세션 쿠키를 열거하고 (`__Secure-pplx.session.<user_id>`), 활성 토큰을 하나씩 교체하며 세션을 탐색하여 대상 이메일을 찾을 때까지 진행합니다 (`pplx_export/commands/common.py:190`; `pplx_export/core/cookies/loaders.py:175`). 일치하는 토큰이 없으면 명령이 명확한 오류 메시지와 함께 중단됩니다. 잘못된 계정으로 조용히 계속 진행하지 않습니다.

**해결**:

- `[accounts.<name>]` 아래에 각 계정의 `email`를 등록하고 ([설정](configuration.md) 참조), 명시적으로 `--account`를 전달하십시오.
- 시작 로그 라인 `[auth] cookie 来源 …，当前账户: …`를 확인하십시오. 데이터를 가져오기 전에 실시간 세션 이메일을 보고합니다.
- 기존 아카이브 감사: 각 스레드의 `thread.json`에는 `export_via` 필드가 포함되어 내보내기를 수행한 계정을 기록합니다 (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted`도 이 필드를 사용하여 온라인 확인할 계정을 선택합니다.

메커니즘 심층 분석: [API 인증](../reference/api/api-authentication.md) · [질문 및 계정](../architecture/ask-and-accounts.md).

<a id="找不到配置文件降级模式" data-pplx-source-anchor="true"></a>
## "설정 파일을 찾을 수 없음" - 폴백 모드

**문제**: 시작 경고: 사용자 수준 설정 파일을 찾을 수 없어 명령이 폴백 모드로 실행됩니다. 또는 명시적 `--account alice`가 오류를 발생시키며 `config.example.toml`를 가리킵니다.

**원인**: 세 가지 검색 위치 모두에 설정 파일이 없습니다: `--config PATH`, 환경 변수 `PPLX_EXPORT_CONFIG`, 기본 `~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). 두 가지 관련되지만 다른 상황: **명시적으로 지정된** 설정 경로가 없으면 `ConfigError`가 발생합니다. 설정이 손상된 경우(구문 분석 불가)는 항상 `ConfigError`가 발생합니다. 손상된 설정은 절대 조용히 폴백되지 않습니다.

**폴백 모드의 영향**:

- 계정 레지스트리가 비어 있으며, 쿠키 소유권 확인이 건너뛰고 경고가 표시됩니다. 명령은 플레이스홀더 계정 `default`로 실행됩니다 (`pplx_export/commands/common.py:51`). 명시적 `--account`는 직접 오류를 발생시킵니다.
- `pplx-ask ask`는 BOT 공간으로의 자동 이동을 건너뜁니다 (결과 JSON에서 `moved_to_bot`는 `false`로 유지됨). 텔레메트리는 빈 사용자 ID를 전송합니다. 질문 및 아카이브 자체는 정상 작동합니다.
- 아카이브는 사용자 이름으로 폴백된 계정 디렉토리에 저장됩니다.

**해결**: `config.example.toml`를 `~/.config/pplx-export/config.toml`로 복사하고, `[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]` 및 `default_account`를 입력하십시오. [설정](configuration.md)을 참조하십시오.

<a id="entry_expired-与-entry_deleted-的区别" data-pplx-source-anchor="true"></a>
## ENTRY_EXPIRED와 ENTRY_DELETED의 차이

**문제**: 스레드 내보내기 또는 증분 동기화 중 `ENTRY_EXPIRED` 또는 `ENTRY_DELETED`가 보고되며, 해당 스레드를 더 이상 가져올 수 없습니다.

**원인**: 둘 다 `GET /rest/thread/<uuid>`의 HTTP 400으로 반환되며 오류 코드가 다릅니다. 둘 다 최종 상태입니다. 스레드가 플랫폼에 더 이상 존재하지 않습니다:

| 오류 코드 | 의미 | 도구 매핑 | 최종 상태 |
|---|---|---|---|
| `ENTRY_EXPIRED` | 플랫폼이 스레드를 제거함 (약 3개월 보존 기간) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | 스레드가 사용자/원격에 의해 삭제됨 (`DELETE /rest/thread/delete_thread_by_entry_uuid`의 하위 표현) | `EntryDeletedError`, `EntryExpiredError`의 하위 클래스 (`pplx_export/core/errors.py:30`) | `deleted` |

**아카이브에 미치는 의미**:

- 두 상태 모두 절대 재시도하지 않습니다. 증분 동기화도, `--force`를 추가해도 마찬가지입니다. 최종 상태 표시는 `<out>/index/batch_state.json`에 존재합니다.
- 도구는 **절대 로컬 아카이브를 삭제하거나 이동하지 않습니다**. 저장소 사본이 백업입니다. 내보내기 명령은 최종 상태를 기록한 후 정상 종료됩니다 (`pplx_export/commands/export_cmd.py:51`).
- 하위 클래스 관계는 의도적으로 설계되었습니다. `EntryExpiredError`만 인식하는 기존 경로는 여전히 `ENTRY_DELETED`를 최종 상태로 처리합니다. 하위 클래스를 인식하는 경로(batch / export / sync-deleted / search-mode-backfill)는 정확히 `deleted`로 분류합니다.
- 실용적인 요점: 적시에 내보내십시오. 약 3개월의 제거 기간이 지나면 산출물/보고서 소스 링크도 복구 불가능하게 만료됩니다.

관련: [증분 동기화](incremental-sync.md) · [응답 및 오류](../reference/api/api-responses-errors.md).

<a id="无法下载的资产toolu_-句柄" data-pplx-source-anchor="true"></a>
## 다운로드할 수 없는 자산 (`toolu_` 핸들)

**문제**: `assets/assets_manifest.json`에서 일부 항목의 버전이 `"no_download_channel": true`로 표시되고, `assets/files/` 아래에 해당 파일이 없습니다.

**원인**: `toolu_` 접두사가 있는 cloud-workspace 핸들(URL 형태가 없는 DOC_FILE / CODE_FILE / UNKNOWN)에는 API 다운로드 채널이 없습니다. `GET /rest/assets/<asset_uuid>/data`는 이들에 대해 404 `ASSET_NOT_FOUND`를 반환하고, `file-repository/download`는 `file:repo/...` 핸들을 거부합니다(400). 이는 **알려진 아카이브 무결성 경계**이며 내보내기 결함이 아닙니다. `pplx-export assets-backfill`는 이러한 버전을 `no_download_channel`로 표시하고 건너뜁니다 (`pplx_export/commands/assets_backfill_cmd.py:356`).

**해결**:

- 현재 다운로드할 수 없습니다. 해당 표시는 이 경계에 대한 의도적인 기록입니다.
- 콘텐츠는 종종 인라인으로 보존됩니다: 하위 에이전트의 페이지 추출 텍스트와 단계 페이로드는 스레드의 raw JSON (`raw_entries.json` / `raw_blocks.json`) 및 렌더링된 `turns/`에 저장됩니다. 먼저 거기서 확인하십시오.
- `file-repository/list-files`는 잠재적인 향후 복구 경로로 추적되고 있습니다. [API 발견 로드맵](../reference/api/api-discovery-roadmap.md)을 참조하십시오.

매니페스트 레이아웃: [아카이브 레이아웃](archive-layout.md).

<a id="命令看似卡住-长时间无输出" data-pplx-source-anchor="true"></a>
## 명령이 멈춘 것처럼 보임 / 오랜 시간 출력 없음

**증상**: `index` / `batch` / `export`가 멈춘 것처럼 보입니다. 외부 작업 관리자가 "시간 초과"로 종료할 수 있습니다.

**원인**: 거의 항상 백오프 또는 진행 중인 요청 대기이며, 교착 상태가 아닙니다. 429 / 5xx / 네트워크 오류 시 전송 계층이 시도 사이에 대기합니다. 단일 대기는 최대 300초입니다 (`pplx_export/core/throttle.py`, `Throttle.backoff`).

**이제 볼 수 있는 것 (기본 수준, `-v` 불필요)**: 대기는 INFO 하트비트로 표시됩니다. 백오프는 시작 라인을 먼저 출력한 후 약 10초마다 카운트다운을 출력합니다 (`Throttle.heartbeat_interval`). 응답 전에 단일 요청이 멈춘 경우 "여전히 응답 대기 중"을 출력합니다. `pplx-ask`는 심층 연구/공동 작업 침묵 중에 "여전히 응답 스트림 대기 중"을 출력합니다:

```
22:27:24 [auth] 正在校验账户 cookie（来源 cache）…
22:27:40 退避 ~51s（连续失败 1 次，网络异常重试中）
22:27:50 仍在等待重试，剩余 ~41s
22:28:00 仍在等待重试，剩余 ~31s
```

총 대기 시간은 변경되지 않습니다. 하트비트는 단지 가시성을 높입니다. 언제든지 중단해도 안전합니다 (상태가 원자적으로 기록되며, 다음 실행 시 자동으로 누락된 부분을 채웁니다). `-v` / `--log-file`는 여전히 전체 DEBUG 요청 추적을 포함합니다.

**시작 탐지 건너뛰기**: `index` / `batch`는 세션 탐색으로 시작하며, 이는 동일한 백오프 규칙을 따릅니다. 따라서 네트워크 상태가 좋지 않을 때 첫 번째 대기 시간이 이 계정 확인 단계일 수 있습니다. `--skip-auth-check`를 전달하여 이를 건너뛰고 현재 로그인된 계정을 신뢰할 수 있습니다. [설정](configuration.md)을 참조하십시오.

**안티 패턴**: CLI를 짧은 하드 타임아웃이 있는 작업 관리자(에이전트 백그라운드 작업, `timeout(1)` 스타일 cron 래퍼)에 넣고 `&&`로 여러 계정을 연결하는 경우. 첫 번째 계정의 백오프가 전체 타임아웃을 소진하여 이후 계정이 실행되지 않습니다. 한 번에 한 계정씩 호출하고 충분한 예산을 확보하십시오. [호출자 런타임 예산](rate-limiting.md#调用方运行时预算)을 참조하십시오.

<a id="日志在哪里" data-pplx-source-anchor="true"></a>
## 로그는 어디에 있습니까?

**콘솔**: 기본 INFO 수준 진행 상황; `-v` / `--verbose`는 DEBUG로 전환 (요청 추적, 내부 결정); 경고 및 오류는 항상 표시됩니다.

**파일**: `--log-file`를 전달하여 전체 DEBUG 스트림을 파일에 기록합니다 (`pplx_export/core/logging.py:45`):

- `--log-file`에 값이 없으면 `<out>/index/logs/<cmd>-<timestamp>.log` (`pplx_export/commands/common.py:218`)에 기록합니다. 예: `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH`는 지정된 경로에 기록합니다.

**진단에 도움이 되는 기타 상태 파일** (모두 `<out>/index/` 아래):

| 파일 | 내용 |
|---|---|
| `.cookies.json` | 쿠키 캐시 (12시간 신선도; 0o600 원자적 쓰기 - 로그인 자격 증명과 동등하므로 기밀 유지) |
| `batch_state.json` | 스레드별 내보내기 상태, `expired` / `deleted` 최종 상태 표시 포함 |
| `answer_variants_log.jsonl` | 답변 재작성 변형 레지스트리 |
| `library_*.json` | 각 계정의 라이브러리 인덱스 스냅샷 |

<a id="参见" data-pplx-source-anchor="true"></a>
## 참조

- [빠른 시작](getting-started.md) — 최초 설정 및 쿠키 가져오기
- [설정](configuration.md) — 계정, BOT 공간, 폴백 모드
- [pplx-ask](pplx-ask.md) — 대화형 쿼리 CLI
- [pplx-export](pplx-export.md) — 아카이브 CLI
- [속도 제한](rate-limiting.md) — 속도 및 백오프 규칙
