---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/pplx-export.zh-CN.md"
translation_source_sha256: "cfcbe706189f0fab04bbc01ac4a17e4fc93919d8ae48dc59a755f266447953c1"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export`는 아카이브 CLI입니다: Perplexity에서 대화 인덱스를 가져오고, 스레드를 로컬 아카이브로 내보내며, 파생 뷰(공간 인덱스, cron 스니펫)를 유지 관리합니다. 이 페이지는 수집 측 하위 명령어인 `index`, `space-index`, `export`, `batch`, `spaces`, `sync-space`, `schedule`와 일회성 초기화 명령어 `init`을 다룹니다. 보완/수정 관련 하위 명령어는 [maintenance-commands.zh-CN.md](maintenance-commands.md)를 참조하고, 쿼리 CLI는 [pplx-ask.zh-CN.md](pplx-ask.md)를 참조하세요.

<a id="通用选项" data-pplx-source-anchor="true"></a>
## 공통 옵션

모든 하위 명령어는 다음 매개변수를 허용합니다(`pplx_export/commands/common.py`에서 통합 정의됨):

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--account NAME` | 대상 계정. 쿠키 소유 이메일과 등록 이메일이 일치하지 않을 때 브라우저의 각 계정 세션 토큰을 자동으로 열거하여 전환 | 사용자 수준 구성의 `default_account` |
| `--config PATH` | 사용자 수준 구성 파일(계정 레지스트리). 우선순위: `--config` > 환경 변수 `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | 기본 검색 체인 |
| `--site NAME` | 사이트 어댑터 | `perplexity` |
| `--out DIR` | 아카이브 출력 루트 디렉터리 | `./web_archive` |
| `--cookies-from BROWSER` | 지정된 브라우저에서 쿠키 가져오기 (`edge`/`chrome`/`firefox`/`safari`/`brave`…) | — |
| `--cookies FILE` | Netscape 쿠키 파일 또는 JSON 쿠키 파일 | — |
| `--transport MODE` | `cookie` = 쿠키 직접 요청; `webbridge` = 브라우저 페이지 컨텍스트 내에서 fetch 실행 | `cookie` |
| `-v`, `--verbose` | DEBUG 출력 (요청 추적, 내부 결정); 반복 가능 | 꺼짐 |
| `--log-file [PATH]` | 전체 로그를 디스크에 기록; 값 없으면 자동으로 `<out>/index/logs/<cmd>-<timestamp>.log`에 기록 | 꺼짐 |

- `--cookies-from` / `--cookies`와 `--transport webbridge`는 상호 배타적입니다. 브리지는 페이지 컨텍스트에서 실행되며 브라우저 쿠키를 자동으로 가져옵니다.
- `pplx-export --version`는 패키지 버전을 출력하고 종료합니다(최상위 전용, 하위 명령어 매개변수 아님).
- 계정 등록, 쿠키 출처 및 다중 계정 전환은 [configuration.zh-CN.md](configuration.md)를 참조하고, 각 파일의 디스크 위치는 [archive-layout.zh-CN.md](archive-layout.md)를 참조하세요.

## init

브라우저 쿠키에서 계정을 자동으로 발견하여 사용자 수준 구성에 기록합니다. `config.example.toml`을 수동으로 복사하는 대신 자동화된 방법입니다([configuration.zh-CN.md](configuration.md) 참조).

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--force` | 기존 구성 파일 덮어쓰기 | 꺼짐 (덮어쓰기 거부) |
| `--create-bot-space [标题]` | 공간 제목이 일치하지 않을 때 API를 통해 BOT 공간 생성 (계정에 대한 쓰기 작업 한 번); 명시적 제목이 제공되면 일치 및 생성 모두 해당 제목 사용, 그렇지 않으면 제목은 `--bot-title`에서 가져옴; 이 플래그가 없으면 `[bot_space]`는 비워서 기록 | 꺼짐 |
| `--bot-title TITLE` | 기존 공간 일치 및 생성 시 이름 지정에 모두 사용되는 공간 제목 | `BOT` |
| *(공통 옵션 적용)* | 쿠키 출처 플래그는 계정 발견 위치를 결정합니다. `init`인 경우에만 `--config`는 **쓰기** 경로입니다 (엄격한 구성 로딩 건너뜀) | |

주요 동작:

- 토큰 열거: 브라우저 저장소에서 각 계정 세션 쿠키 수집 (`__Secure-pplx.session.<uid>`); `--cookies FILE`가 제공되면 해당 쿠키 파일을 대신 스캔합니다 (전체 내보내기는 여러 계정을 포함할 수 있음). 열거 가능한 토큰이 없으면 현재 활성 세션만 감지하는 것으로 대체됩니다.
- 세션 감지: 각 토큰에 대해 `GET /api/auth/session`에 요청하여 계정 이메일/표시 이름을 가져옵니다. 실패하거나 이메일을 반환하지 않은 토큰은 경고와 함께 건너뜁니다.
- 레지스트리 조립: 계정 키는 이메일 로컬 부분에서 파생됩니다 (이름 충돌 시 `-2`/`-3`… 접미사 추가); `default_account`는 현재 활성 계정을 가져오고, 그렇지 않으면 첫 번째로 발견된 계정을 가져옵니다.
- BOT 공간: `list_user_collections`를 통해 제목을 정확히 일치시킵니다 (대소문자 구분 안 함); 일치하는 항목이 없으면 `--create-bot-space [标题]`가 즉시 생성합니다 (명시적 제목이 `--bot-title`를 재정의하며, 일치 및 생성 모두에 사용됨), 그렇지 않으면 `[bot_space]`는 비워 둡니다.
- TOML 원자적 쓰기 (임시 파일 + 이름 변경), 권한 0600; 기존 파일이 있으면 `--force` 없이 절대 덮어쓰지 않습니다. 명령어 끝에 구성 경로, 계정 키, 기본 계정, BOT 공간 uuid/slug를 포함한 요약 JSON 한 줄을 출력합니다.
- `--transport webbridge`는 거부됩니다. 페이지 컨텍스트 채널은 각 계정 토큰을 열거할 수 없습니다.

```bash
pplx-export init                          # 写入默认 ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --config /path/to/config.toml --force   # 自定义路径，允许覆盖
```

## index

계정의 전체 대화 목록을 가져와서 (GraphQL) 기본 인덱스 `index/library_<account>.json`에 기록합니다. 다른 모든 명령어의 비교 기준선입니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| *(공통 옵션만 해당)* | | |

주요 동작:

- `search-mode-backfill`가 기록한 `search_mode` 보강 결과를 유지합니다. 인덱스 행 자체는 해당 필드를 전달하지 않으며, 새로 고침 시 `entryUUID`에 따라 이전 인덱스에서 병합됩니다.
- `batch`, `sync-space`, `sync-deleted`를 실행하기 전에 먼저 실행하세요. 이러한 명령어의 비교 결과는 인덱스의 최신 상태에 따라 달라집니다.

```bash
pplx-export index --account alice
```

## space-index

특정 공간의 "모든" 대화 목록을 추출합니다. 공유 공간의 다른 구성원 스레드를 포함하여 `index/space_<slug>.json`에 기록합니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `SPACE_URL` (위치 매개변수) | 공간 페이지 URL | 필수 |
| `--transport webbridge` | REST 대신 이전 브라우저 렌더링 경로 사용 | `cookie` (REST 직접 연결) |

주요 동작:

- 기본적으로 REST 직접 연결 사용: 쿠키 채널을 통해 `list_collection_threads` 호출, offset 페이지 매김; 행에는 `context_uuid`와 `answer_preview`가 포함됩니다.
- `--transport webbridge`인 경우 스크롤 렌더링 공간 페이지로 대체하여 행 속성을 가져오는 이전 경로로 전환합니다. REST 구조 변경 시 대체 채널입니다.
- 행은 `lastUpdated`에 따라 최신순으로 디스크에 기록됩니다.

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

단일 스레드(URL 또는 원시 UUID)를 아카이브 디렉터리 `<out>/<account-folder>/<mode>/<thread-dir>/`로 내보냅니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `THREAD` (위치 매개변수) | 스레드 URL 또는 UUID | 필수 |
| `--force` | `lastUpdated`가 변경되지 않았어도 강제로 다시 내보내기 | 꺼짐 |

주요 동작:

- 아카이브 복사본이 이미 최신이면 건너뛰고 파일을 쓰지 않습니다. `--force`는 이 검사를 재정의합니다.
- 로컬 라이브러리 인덱스에 스레드 행이 있으면 `lastUpdated`는 인덱스 값을 가져옵니다 (`batch`와 동일한 의미 및 형식). 그렇지 않으면 플랫폼 실제 값으로 대체됩니다.
- 최종 상태는 정상적으로 등록되며 traceback을 발생시키지 않습니다. `ENTRY_DELETED`는 `batch_state.json`에서 `deleted`를 표시하고, `ENTRY_EXPIRED`는 `expired`를 표시합니다. 두 경우 모두 로컬에 이미 있는 아카이브는 그대로 유지됩니다.
- 내보내기가 성공하면 `ok`를 `index/batch_state.json`에 기록합니다. 증분 계획은 이에 따라 해당 스레드를 "내보내졌으며 변경되지 않음"으로 간주합니다.
- 스레드 디렉터리 내 파일 구성은 [archive-layout.zh-CN.md](archive-layout.md)를 참조하고, 내보내기 파이프라인 자체는 [../architecture/export-pipeline.zh-CN.md](../architecture/export-pipeline.md)를 참조하세요.

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

계정 스레드를 일괄 내보냅니다. 일상적인 주요 명령어로, 증분 조기 중단 및 중단점 재개 기능이 있습니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--force` | 모든 스레드 다시 내보내기 (최종 상태 제외) | 꺼짐 |
| `--full` | 전체 검사: 변경되지 않은 스레드는 여전히 건너뛰지만 조기 중단하지 않음 | 꺼짐 |
| `--limit N` | 목록에서 처음 N개만 처리 (최신순) | 전체 |
| `--mode MODE` | `search` / `deep-research` / `computer` / `council` / `study` 스레드만 내보내기 | 전체 모드 |
| `--delay-min SEC` | 스레드 간 무작위 간격 하한 | `10` |
| `--delay-max SEC` | 스레드 간 무작위 간격 상한 | `20` |

주요 동작:

- `index/library_<account>.json`에 의존합니다. 먼저 `index`를 실행하세요.
- 기본적으로 **증분 조기 중단**: 목록을 최신순으로 정렬하고, 끝부분에서 "내보내졌으며 변경되지 않음"의 연속된 세그먼트를 전체적으로 잘라냅니다. 이전 중단으로 인한 간격 (오류/내보내지 않음)은 최종 상태 접미사 위에 있으며 여전히 수정됩니다. `--full`는 조기 중단을 비활성화합니다 (정기적인 안전망 또는 아카이브에 간격이 의심될 때 사용). `--force`는 최종 상태를 제외한 모든 스레드를 다시 내보내며, 최종 상태는 재시도하지 않습니다. 전체 의미는 [incremental-sync.zh-CN.md](incremental-sync.md)를 참조하세요.
- `--mode` 필터링: 인덱스 행에 `search_mode` (`search-mode-backfill`가 보강한 플랫폼 권위 필드)가 있으면 `SEARCH_MODE_MAP`를 통해 정확히 일치시킵니다. 이 경로에서는 `--mode search`가 더 이상 deep-research/council/study 스레드를 혼합하지 않습니다. `search_mode`가 없는 행은 인덱스 필드 휴리스틱으로 대체됩니다: `computer` = mode `COMPUTER`; `deep-research` = displayModel `pplx_alpha`; `council` = `pplx_agentic_research`; `study` = `pplx_study`; `search` = 나머지 mode가 `SEARCH`인 행 (위 세 가지 포함 — 정확히 제외하려면 해당 모드를 개별적으로 내보내기 사용).
- 각 스레드를 내보낸 후 상태를 `index/batch_state.json`에 기록합니다. 언제든지 중단하고 다시 실행할 수 있습니다.
- 인증 빠른 실패: 연속 3번의 401/403 후 중단 (쿠키 만료 시 백오프로 자가 치유 불가능, 빈 회전은 수백 개의 스레드가 각각 실패하게 만듦).
- 속도: 스레드 간 무작위 간격 `--delay-min`–`--delay-max`; 429/5xx는 전송 계층에서 백오프 처리. 자세한 내용은 [rate-limiting.zh-CN.md](rate-limiting.md)를 참조하세요.
- 재작성된 답변 변형이 있는 스레드는 `index/answer_variants_log.jsonl`에 등록되고 경고가 발생하므로 가능한 한 빨리 수동 처리가 필요합니다 ([../reference/api/api-responses-errors.zh-CN.md](../reference/api/api-responses-errors.md) 참조).

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

로컬 라이브러리 인덱스에서 공간 뷰 인덱스를 재구성합니다. 각 공간에 대해 하나의 Markdown 페이지와 `spaces.json` 레지스트리가 생성됩니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--fetch-meta` | 재구성 전에 소유자/구성원 메타데이터 새로 고침 | 꺼짐 |

주요 동작:

- `--fetch-meta` 없으면 순수 로컬 (네트워크 없음): 모든 `library_*.json`에서 공간 slug별로 스레드를 집계하며, 참여 계정 통계 및 내보낸 스레드 디렉터리로의 역링크를 포함합니다.
- 출력은 현재 작업 디렉터리의 `./spaces/`에 저장됩니다. `web_archive/`가 포함된 디렉터리에서 실행하세요. 공간 페이지의 역링크가 올바르게 확인됩니다.
- `--fetch-meta`는 먼저 `get_collection`를 통해 각 공간의 소유자/구성원 캐시를 새로 고칩니다 (공간당 1회 요청, 3초 간격) `index/space_meta.json`에 저장. 현재 계정이 볼 수 없는 공간은 자동으로 볼 수 있는 계정으로 전환하여 재시도합니다 (쿠키 자동 전환).

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

이미 아카이브된 `thread.json`의 `space` 필드를 현재 인덱스와 정렬합니다. 순수 로컬, 네트워크 없음.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| *(공통 옵션만 해당; `--out`만 작동)* | | |

주요 동작:

- 사전 조건: 먼저 `index`를 실행하세요. 새로 고쳐진 `library_*.json`는 현재 공간 소속의 진정한 출처입니다.
- 스레드별로 공간 slug를 비교하고, 차이가 있으면 `thread.json`를 제자리에서 패치합니다. 처음 30개의 변경 사항이 로그에 기록됩니다.
- 변경 사항이 있으면 자동으로 `spaces/` 인덱스 재구성을 트리거합니다.

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

이번 증분 내보내기 계획을 계산하고 시스템 cron에서 직접 호출할 수 있는 명령어 스니펫을 생성합니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| *(공통 옵션만 해당)* | | |

주요 동작:

- 실시간 인덱스를 가져와 총계/신규/업데이트별로 계획을 보고하며, `batch`와 동일한 조기 중단 순수 함수 (`plan_incremental`)를 사용합니다. [incremental-sync.zh-CN.md](incremental-sync.md) 참조.
- `<out>/index/cron_snippet.txt`에 기록하며, 내용은 `17 3 * * *` 행 하나로, 형식은 `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'`와 같습니다. 경로는 절대 경로를 사용하고 따옴표로 묶습니다. cron의 cwd와 PATH를 예측할 수 없기 때문입니다. 실행 파일 경로는 `shutil.which`를 통해 확인되며, 확인에 실패하면 원시 명령어 이름 `pplx-export`로 대체됩니다.
- 정기적인 일괄 실행은 설계상 증분만 실행합니다. `batch --full`는 정기적인 안전망으로 수동 실행됩니다.

```bash
pplx-export schedule --account alice
```
