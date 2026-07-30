---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/configuration.zh-CN.md"
translation_source_sha256: "0e237ed1c2465d1d1496878708fadd64d1f0459788f85ba8063dffbca1c5329d"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="配置" data-pplx-source-anchor="true"></a>
# 구성

pplx-export는 신원 데이터(계정 레지스트리: 표시 이름, 로그인 이메일, 사용자 ID)와 BOT 공간을 저장소 외부의 사용자 수준 TOML 파일에 보관합니다. 이 페이지에서는 해당 파일의 위치, 모든 필드, 파일이 없을 때의 동작, 그리고 레지스트리가 다중 계정 쿠키 처리를 어떻게 구동하는지 설명합니다.

<a id="为什么配置外置在仓库之外" data-pplx-source-anchor="true"></a>
## 구성이 저장소 외부에 있는 이유

계정 레지스트리와 BOT 공간은 개인 데이터이므로 **절대** 저장소에 커밋하지 않습니다(`pplx_export/config.py:7-12`). 저장소에는 자리 표시자 템플릿 `config.example.toml`만 첨부되어 있습니다. 실제 값은 사용자의 개인 복사본에 기록됩니다. 도구에 필요한 나머지 내용(사이트 도메인, API URL, 기본 아카이브 루트)은 코드 상수(`pplx_export/config.py:50-58`)이며 사용자 구성에 속하지 않습니다.

TOML은 신원 데이터만 전달합니다. 쿠키 소스와 데이터 경로 선택은 각 호출의 CLI 플래그이며 구성 필드가 아닙니다. [CLI 플래그 vs 구성 필드](#cli-标志而非配置字段)를 참조하세요.

<a id="位置与加载优先级" data-pplx-source-anchor="true"></a>
## 위치 및 로딩 우선순위

`configure()`(`pplx_export/config.py:113`)는 다음 우선순위로 구성 경로를 확인합니다(`pplx_export/config.py:95-110`):

| 우선순위 | 출처 | 명시적 지정 여부 |
|---|---|---|
| 1 | `--config PATH` CLI 플래그 | 예 |
| 2 | 환경 변수 `PPLX_EXPORT_CONFIG` | 예 |
| 3 | `~/.config/pplx-export/config.toml`(기본 경로) | 아니요 |

'명시적'은 파일이 없을 때 오류 보고 동작에 영향을 미칩니다. [구성 누락: 저하 모드](#配置缺失降级模式)를 참조하세요. 두 CLI 진입점 모두 인수 구문 분석 후 strict 모드로 다시 로드합니다(`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`). import 시 로딩(`pplx_export/config.py:174-179`)은 오류 허용이므로 패키지를 import만 하면 파일이 없어도 실패하지 않습니다.

<a id="创建你的配置" data-pplx-source-anchor="true"></a>
## 구성 생성

!!! tip "자동 대안"
    `pplx-export init`는 이 파일을 자동으로 생성할 수 있습니다. 브라우저 쿠키에서 로그인된 계정을 발견하고 0600 권한으로 TOML을 작성합니다. [pplx-export → init](pplx-export.md#init)를 참조하세요.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

그런 다음 해당 복사본을 편집합니다. 템플릿은 모두 자리 표시자입니다. 구조를 그대로 따르고 각 값을 바꾸세요:

```toml
# --account 未给出时使用的默认账户（对应下方 [accounts.<名>] 的键）
default_account = "alice"

# 账户注册表：键 = 账户用户名（thread URL / library 中的 username）
[accounts.alice]
# 完整显示名：用于归档目录命名（web_archive/<显示名>/…）
display_name = "Alice Example"
# 登录 email：校验 cookie 归属
email = "alice@example.com"
# 账户 uid（thread viewed 遥测需要）
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT 空间：pplx-ask 发问完成后线程的集中收纳处
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

자리 표시자 스타일: `alice`/`bob`은 가상의 계정 사용자 이름이고, 이메일은 `example.com`, UUID는 모두 0인 `00000000-0000-4000-8000-…` 형식입니다. 실제 파일에서 테이블 키는 **실제 계정 사용자 이름**이어야 합니다. 즉, 스레드 URL과 라이브러리에 나타나는 그 이름입니다.

!!! warning "비공개 유지"
    실제 구성에는 개인 데이터(이메일, 사용자 ID)가 포함됩니다. 권한 `0o600`를 권장합니다. 어떤 git 저장소에도 커밋하지 마십시오(`config.example.toml:4-6`).

<a id="字段参考" data-pplx-source-anchor="true"></a>
## 필드 참조

<a id="顶层" data-pplx-source-anchor="true"></a>
### 최상위

| 필드 | 유형 | 의미 |
|---|---|---|
| `default_account` | string | `[accounts.<name>]` 테이블의 키로, `--account`가 주어지지 않았을 때 사용됩니다(`pplx_export/commands/common.py:84-85`). 비어 있거나 없으면 저하 모드입니다. |
| `archive_root` | string | 선택 사항. 아카이브 출력 루트로, `--out`의 대체 역할을 하며 일상적인 명령에서 `--out`를 생략할 수 있습니다. 우선순위: `--out` > `archive_root` > `./web_archive`(`pplx_export/config.py`, `ARCHIVE_ROOT` 로드; `cli.py` / `ask_cli.py`에서 구문 분석). `~`는 확장됩니다. |

### `[accounts.<name>]`

각 계정마다 하나의 테이블입니다. `<name>`는 계정 사용자 이름입니다. 레지스트리는 사용자 이름을 키로 하는 세 개의 dict(`ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID`)로 로드됩니다(`pplx_export/config.py:65-75`).

| 필드 | 유형 | 필수 여부 | 의미 |
|---|---|---|---|
| `display_name` | string | 아니요 | 전체 표시 이름으로, 아카이브 디렉터리 이름 지정에 사용됩니다(`web_archive/<显示名>/…`). 기본값은 사용자 이름 자체입니다. [아카이브 레이아웃](archive-layout.md)을 참조하세요. |
| `email` | string | 권장 | 로그인 이메일입니다. transport는 이를 사용하여 쿠키 소유권을 확인하고 '계정 B의 내보내기가 계정 A의 세션을 사용하는' 상황을 방지합니다(`pplx_export/config.py:69-72`). 일치하지 않으면 브라우저에서 계정 세션 토큰을 자동으로 열거하고 전환합니다. [다중 계정 쿠키 모델](#多账户-cookie-模型)을 참조하세요. |
| `user_id` | string | `pplx-ask` 원격 측정에 필요 | 계정 uid로, 스레드 조회 원격 측정에 필요합니다(`pplx_export/config.py:73-75`). `GET /api/auth/linked-accounts`를 통해 볼 수 있으며, 이 인터페이스는 로그인된 각 계정의 `user_id` / `email` / `display_name`를 반환합니다. [API 인증](../reference/api/api-authentication.md)을 참조하세요. |

### `[bot_space]`

BOT 공간은 `pplx-ask`가 질문을 완료한 후 스레드를 중앙에 모아두는 곳입니다(`pplx_export/config.py:76-79`). 공간 자체는 `pplx-ask space-create`를 통해 실제로 생성할 수 있으며([pplx-ask](pplx-ask.md) 참조), 그런 다음 여기에 등록합니다.

| 필드 | 유형 | 의미 |
|---|---|---|
| `uuid` | string | 공간 UUID. `pplx-ask`는 완료된 스레드를 여기로 이동합니다(`pplx_export/ask_cli.py:156-158`). 비어 있으면 이동 단계를 건너뜁니다. |
| `slug` | string | 공간의 URL slug. `BOT_SPACE_SLUG`로 로드됩니다(`pplx_export/config.py:79`). 런타임 CLI는 이를 읽지 않습니다. fixture 유지 관리 도구가 이를 사용하여 ID 대체 쌍을 구성합니다(`tests/scrub_fixtures.py:446-447`). |

<a id="cli-标志而非配置字段" data-pplx-source-anchor="true"></a>
### CLI 플래그 vs 구성 필드

TOML에는 경로나 쿠키 설정이 없습니다. 이들은 호출 시 선택됩니다:

| 관심사 | 설정 위치 |
|---|---|
| 구성 파일 경로 | `--config PATH` 또는 `PPLX_EXPORT_CONFIG` |
| 쿠키 소스 | `--cookies-from BROWSER` / `--cookies FILE` |
| 데이터 경로 | `--transport cookie\|webbridge`(`pplx-export`만 해당, 기본값 `cookie`) |
| 시작 계정 확인 건너뛰기 | `--skip-auth-check`(두 진입점 모두) — [다중 계정 쿠키 모델](#多账户-cookie-模型) 참조 |

전체 플래그 참조는 [pplx-export](pplx-export.md)를 참조하세요.

<a id="配置缺失降级模式" data-pplx-source-anchor="true"></a>
## 구성 누락: 저하 모드

아무것도 로드되지 않으면 모듈 수준 레지스트리는 비어 있고 `LOADED_CONFIG_PATH`는 `None`입니다(`pplx_export/config.py:83-85`). 시나리오별 동작(`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| 시나리오 | 동작 |
|---|---|
| 기본 경로에 구성 없음, `--account` 제공 안 함 | 저하 모드: 경고를 기록하고 명령이 자리 표시자 계정(`username='default'`)으로 실행됩니다. 이메일 소유권 확인이 건너뛰어집니다. 일상적인 오프라인 명령에는 영향을 미치지 않습니다(`pplx_export/commands/common.py:86-90`). |
| 구성 없음, 명시적 `--account` | `SystemExit`, 검색 순서를 제공하고 `config.example.toml`를 가리킵니다(`pplx_export/commands/common.py:67-74`). |
| 구성 로드됨, `--account` 미등록 | `SystemExit`, 로드된 파일 경로를 제공하고 `[accounts.<name>]` 추가를 요청합니다(`pplx_export/commands/common.py:77-82`). |
| 명시적 경로(`--config` / 환경 변수)가 존재하지 않음 | strict 모드에서 `ConfigError`를 발생시킵니다(`pplx_export/config.py:140-146`). |
| 파일은 존재하지만 구문 분석 실패 | 항상 `ConfigError`를 발생시킵니다. 구성 손상은 자동으로 저하되어서는 안 됩니다(`pplx_export/config.py:147-150`). |
| `--account` 제공 안 함, 구성 로드됨 | `default_account`를 사용합니다(`pplx_export/commands/common.py:84-85`). |

'오프라인 명령'의 범위와 저하 모드 실행이 아카이브와 상호 작용하는 방식에 대한 자세한 내용은 [오프라인 작업](../architecture/offline-operations.md)을 참조하세요.

<a id="多账户-cookie-模型" data-pplx-source-anchor="true"></a>
## 다중 계정 쿠키 모델

여러 계정이 동일한 브라우저에 로그인되어 있을 때 쿠키 라이브러리는 **각 계정**에 대해 하나의 세션 쿠키를 저장합니다. 구성의 `email` 필드는 도구에 필요한 계정을 알려줍니다:

- 로그인된 각 계정에는 하나의 `__Secure-pplx.session.<uid>` 쿠키가 있습니다(`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`). `<uid>` 접미사는 계정의 `user_id`입니다.
- **현재 활성** 계정은 토큰이 현재 `__Secure-next-auth.session-token`에 기록된 계정입니다(`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). 계정 전환 = 대상 계정의 계정별 쿠키 값을 해당 쿠키에 기록합니다. 브라우저 UI가 필요하지 않습니다(`pplx_export/core/cookies/loaders.py:180-187`).
- 시작 시 transport는 `GET https://www.perplexity.ai/api/auth/session`를 검색하고 반환된 이메일을 `accounts.<name>.email`와 비교합니다(`pplx_export/commands/common.py:126-130`).
- 일치하지 않으면 `_try_switch_account`(`pplx_export/commands/common.py:190-215`)가 `list_account_tokens`(`pplx_export/core/cookies/loaders.py:175-206`, `www.` 하위 도메인의 항목 우선)을 통해 브라우저의 모든 계정 토큰을 열거하고 각각을 `__Secure-next-auth.session-token`에 기록하여 시도합니다. 첫 번째 일치 항목으로 transport를 재구성합니다.
- 모두 일치하지 않으면 명령이 종료되고 두 이메일을 나열하며 브라우저에서 대상 계정에 먼저 로그인하도록 요청합니다(`pplx_export/commands/common.py:142-145`). [문제 해결](troubleshooting.md)을 참조하세요.
- `email`가 등록되지 않은 계정은 확인 없이 통과되며, 브라우저에 올바른 계정이 로그인되어 있는지 직접 확인하라는 경고가 표시됩니다(`pplx_export/commands/common.py:146-149`).

전체 전환 흐름과 세션 엔드포인트 의미 체계는 [질문 및 계정](../architecture/ask-and-accounts.md) 및 [API 인증](../reference/api/api-authentication.md)을 참조하세요.

**확인 건너뛰기(`--skip-auth-check`).** 위의 시작 세션 검색은 몇 초(네트워크 상태가 좋지 않으면 몇 분)를 소비하여 '계정 B를 A로 사용'하는 소유권 보호를 제공합니다. 브라우저에 대상 계정이 로그인되어 있다고 확신하는 경우 `--skip-auth-check`(`pplx-export` 및 `pplx-ask` 공유)는 이 검색을 완전히 건너뛰고 바로 작업을 시작합니다(`pplx_export/commands/common.py`, `make_transport`):

- 시작 시 `GET /api/auth/session`를 보내지 않으므로 네트워크 지터로 인해 첫 번째 실제 요청 전에 긴 침묵 대기가 발생하지 않습니다(이제 하트비트가 있음).
- 도구는 현재 로그인된 계정을 신뢰합니다. 위의 시작 이메일 소유권 확인 및 다중 계정 자동 전환이 수행되지 않습니다.
- **지연된 안전망**: `batch`에서 일반 내보내기 오류가 누적되면(3회 실패) 일회성 계정 확인을 수행하고 결과를 알려줍니다. 쿠키 만료, 계정 불일치 또는 계정 정상(오류가 네트워크/속도 제한으로 인한 것임을 나타냄)(`pplx_export/commands/common.py`, `report_account_status`; `pplx_export/commands/batch_cmd.py`).
- **절충**: 지연된 확인은 쿠키 만료를 포착할 수 있지만 **계정은 유효하지만 잘못 사용되어 오류 없이 내보내기가 가능한** 상황은 포착하지 못합니다. `--skip-auth-check`를 사용하면 대상 계정이 로그인되어 있는지 직접 확인해야 합니다.

로그인이 올바르다고 알려진 경우 빠르고 무인 실행에 적합합니다. 시작 소유권 보호 또는 자동 계정 전환에 의존하는 경우 사용하지 마십시오.

<a id="cookie-缓存" data-pplx-source-anchor="true"></a>
## 쿠키 캐시

확인 성공 후 구문 분석된 쿠키가 캐시되어 이후 실행에서 브라우저에 다시 접근하지 않습니다:

| 속성 | 값 |
|---|---|
| 경로 | `<归档根>/index/.cookies.json` — `--out`를 따릅니다(`pplx_export/commands/common.py:111`) |
| 신선 기간 | 12시간(`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`). 만료되거나 손상된 캐시는 캐시 없음으로 처리됩니다. |
| 내용 | `fetched_at`, `source`, `account_email`, `cookies`(`pplx_export/core/cookies/cache.py:62-66`) |
| 쓰기 | 원자적 쓰기: 임시 파일이 `0o600`로 생성된 후 `os.replace`(`pplx_export/core/cookies/cache.py:49-67`) |
| Git | `.gitignore`에 의해 무시됨(`**/index/.cookies.json`) |

쿠키 구문 분석 순서(`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`): 명시적 `--cookies-from` → 명시적 `--cookies` 파일 → 신선한 캐시 → 자동 감지 브라우저(edge → chrome → firefox → safari). 각 계정 확인 성공 후 캐시가 새로 고쳐집니다(`pplx_export/commands/common.py:150`).

<a id="保护你的文件" data-pplx-source-anchor="true"></a>
## 파일 보호

- `config.toml`에 대해 `chmod 600`를 실행하십시오. 개인 데이터(이메일, 사용자 ID)가 포함되어 있습니다.
- 쿠키 캐시는 도구에 의해 `0o600`로 기록됩니다. 세션 쿠키는 로그인 자격 증명과 동일합니다.
- `--cookies`에 사용할 쿠키 파일을 수동으로 만드는 경우에도 `chmod 600`를 실행하십시오.

<a id="认证失败时" data-pplx-source-anchor="true"></a>
## 인증 실패 시

쿠키 만료, 자동 전환에서 계정을 찾을 수 없음, 브라우저 키체인 권한 오류 및 기타 인증 실패는 [문제 해결](troubleshooting.md)을 참조하세요.
