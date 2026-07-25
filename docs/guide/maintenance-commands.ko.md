---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/maintenance-commands.zh-CN.md"
translation_source_sha256: "ed280b2fa84c7dfed83da45f6fa05dbee6191c9ce3542ffaca92686cb1fab5fc"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="维护命令" data-pplx-source-anchor="true"></a>
# 유지 관리 명령어

`pplx-export`의 유지 관리 하위 명령어는 기존 아카이브를 정상 상태로 유지하는 역할을 합니다. 렌더링 계층 수정 후 페이지 재렌더링, 자산/사용량/모드 메타데이터 보완, 원격에서 삭제된 스레드에 툼스톤 표시, 관계 그래프 재구축 등을 수행합니다. 대부분의 명령어는 오프라인 우선이며, 온라인 단계에서는 `batch`와 동일한 속도 제한 규칙을 따릅니다([rate-limiting.zh-CN.md](rate-limiting.md) 참조). 모든 명령어는 [공통 옵션](pplx-export.md)(`--account`, `--out`, `--cookies-from`, `--transport` 등)을 허용합니다.

- 로컬 아카이브 보존 원칙: 어떤 유지 관리 명령어도 아카이브된 스레드 콘텐츠를 삭제하거나 이동하지 않습니다. 아카이브는 곧 백업입니다.
- 오프라인 명령어(`re-render`, `relations`, `sync-space`, `--fetch-meta` 없는 `spaces`, 및 아래 각 명령어의 기본 단계)는 데이터 경로가 전혀 필요하지 않습니다. [../architecture/offline-operations.zh-CN.md](../architecture/offline-operations.md) 참조.

## re-render

아카이브된 원본 JSON(`raw_entries.json` / `raw_blocks.json`)에서 `conversation.md`와 `turns/`를 재생성합니다. 네트워크 사용 없음, 나머지 파일은 전혀 건드리지 않습니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--limit N` | 처음 N개 스레드 디렉터리만 처리 | 전체 |
| `--dry-run` | 처리할 디렉터리만 나열하고 파일 쓰지 않음 | 끄기 |
| `--thread-json` | 동시에 `thread.json`의 `interruptions` 및 `answer_variants` 키를 제자리에서 추가/제거 | 끄기 |

주요 동작:

- 내보내기와 동일한 파이프라인을 사용하여 오프라인으로 turns 재구성: 파싱, `created_us` 기준 정렬, 인용 중복 제거; computer/council의 경우 workflow blocks, 하위 에이전트 매핑, 소비되지 않은 백업 부록을 추가로 포함.
- `conversation.md`와 `turns/turn_*.md`만 (재)쓰기; `sources*`, `assets/`, `report.md`, `thread.json`는 그대로 유지. 현재 라운드 번호보다 높은 번호의 잔여 `turn_*.md`는 삭제됨. 그 외에는 건드리지 않으며, 변경되지 않은 파일의 mtime은 유지.
- `--thread-json`는 콘텐츠가 변경된 경우에만 디스크에 기록; `answer_variants`가 새로 추가/변경되면 `ANSWER_VARIANT_DETECTED` 경고를 발생시키고 `index/answer_variants_log.jsonl`에 추가 등록(멱등 재실행 시 화면이 넘치지 않음).
- `raw_entries.json`가 없는 스레드 디렉터리는 건너뛰고 개수 계산.

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

아카이브 시 서명 URL을 얻지 못한 자산을 보완합니다. 세 단계로 보완: blocks 재확보, 오프라인 인라인 추출, 선택적 온라인 새로고침.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--fetch-blocks` | 먼저 누락된 `raw_blocks.json` 및 해당 서명 URL 자산 재확보(온라인) | 끄기 |
| `--online` | 누락/만료된 자산의 온라인 새로고침 활성화 | 끄기(오프라인 인라인 추출만, 요청 없음) |
| `--limit N` | 처음 N개 스레드 디렉터리만 처리 | 전체 |

주요 동작:

- 기본 단계(오프라인, 요청 없음): `raw_blocks.json`에서 인라인 자산(`ASSET_DIFF` / `CODE_ASSET`)을 추출하여 `assets/files/*.md`로 디스크에 저장하고, 클라우드 작업 공간 핸들 클래스(`DOC_FILE` / `CODE_FILE` / `UNKNOWN` — 현재 다운로드 채널 없음)를 `assets/assets_manifest.json`에 등록. 멱등성: 알려진 레코드는 uuid → file_handle로 중복 확인; 동일 이름의 다중 버전 파일은 uuid 짧은 접두사를 추가하므로 재실행 시 충돌 없음.
- `--fetch-blocks`(온라인): deep-research/computer/council/study 스레드에서 누락된 `raw_blocks.json` 및 다운로드 가능한 자산 재확보; 스레드는 계정 디렉터리별로 그룹화되며, 각 계정에 대해 지연 어댑터 구축(cookie 자동 전환), 스레드 간격 3초.
- `--online`: manifest에서 `downloaded_to`가 누락/만료된 버전에 대해 `/rest/assets/<uuid>/data`를 통해 새 서명 URL 획득(API 직렬, 간격 3초), 그런 다음 CDN에서 재다운로드(6개 스레드 동시, 지연 없음 — CDN은 API 아님). 404 `ASSET_NOT_FOUND`는 `asset_expired` 최종 상태 표시 설정; 계정 간 403은 아카이브 소유 계정으로 한 번 재시도.
- 매번 쓰기 시 manifest의 `count`를 버전 총 개수로 재계산.

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

계정의 모든 아카이브된 스레드에 대한 사용량 기록(`credits/thread-usage`)을 보완하여 `index/credit_usage_<account>.json`에 씁니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--limit N` | 처음 N개 스레드만 처리 | 전체 |

주요 동작:

- 각 아카이브된 스레드에 대해 한 번 GET(`thread_id`로 스레드의 `psc_uuid` 획득), 간격 3초; 멱등성 — 출력 파일에 이미 기록된 스레드는 건너뜀.
- 403(`thread_usage_forbidden`, 즉 계정 간 스레드)은 `error`로 기록되며 재시도하지 않음; 다른 실패는 다음 라운드로 연기. 25개 스레드 처리마다 중간 저장.
- 다중 계정: 각 계정에 대해 `--account`를 각각 한 번씩 실행 — cookie는 실행 간에 자동 전환.

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

`index/library_<account>.json`의 각 행에 플랫폼 권위의 `search_mode` 필드를 보완하여 `batch --mode`가 휴리스틱 없이 정확하게 필터링할 수 있도록 합니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--limit N` | 처음 N개 미처리 행만 처리 | 전체 |
| `--offline` | 로컬 추출만 수행 — 로컬에 raw가 없는 행은 다음 라운드로 연기, 네트워크 폴백 없음 | 끄기 |
| `--delay-min SEC` | 네트워크 폴백 시 스레드 간 무작위 간격 하한 | `10` |
| `--delay-max SEC` | 네트워크 폴백 시 스레드 간 무작위 간격 상한 | `20` |

주요 동작:

- 플랫폼 원래 값 저장(`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…); 스레드 내 여러 값인 경우 특이성 순서 computer > council > study > deep-research > search로 가장 높은 값을 취함.
- 로컬 우선: 아카이브된 스레드에서 `raw_entries.json` 추출, 네트워크 사용 없음 — 순수 로컬로 해결 가능한 경우 transport조차 구축하지 않음(세션 탐지도 없음).
- 로컬에 raw가 없는 행만 네트워크 폴백: `GET /rest/thread/<uuid>`, 10–20초 무작위 간격; `expired` 최종 상태의 행은 건너뛰고 그대로 기록; 온라인에서 새로 발견된 expired/deleted 스레드는 `batch_state.json`에 표시되어 다음 라운드에서 요청 방지.
- 멱등성 및 재개 가능: 이미 `search_mode`가 있는 행은 건너뛰고, 25개마다 중간 저장; 이후 `index` 새로고침 시 보강 결과 유지(`entryUUID` 기준으로 병합).

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

원격 라이브러리에서 사라진 스레드(사용자 삭제 또는 플랫폼 정리)를 식별하고 툼스톤 표시를 합니다. 아카이브 파일을 절대 삭제하거나 이동하지 않습니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--online` | 온라인 확인 후보 | 끄기(오프라인 dry-run: 후보만 나열) |
| `--limit N` | 처음 N개 후보만 처리 | 전체 |
| `--delay-min SEC` | 후보 간 무작위 간격 하한 | `10` |
| `--delay-max SEC` | 후보 간 무작위 간격 상한 | `20` |

주요 동작:

- 후보 판정은 오프라인 및 계정 간: `batch_state` 상태가 `ok`인 스레드가 **모든** `index/library_*.json`의 `entryUUID` 집합에서 모두 사라진 경우에만 후보가 됨. 하나의 인덱스라도 포함하면 활성으로 간주되므로, 공유 공간을 통해 계정 간 내보내기된 스레드는 오탐되지 않음. 사용 가능한 인덱스가 전혀 없으면 모두 안전하게 건너뛰고 먼저 `index`를 실행하라는 메시지 표시.
- 기본 오프라인 dry-run: 후보와 안전하게 건너뛴 이유만 나열 — 네트워크 사용 없음, 파일 변경 없음.
- `--online`: 후보 `thread.json`의 `export_via` 계정을 기준으로 각 후보를 `GET /rest/thread/<uuid>`로 하나씩 확인(cookie는 후보마다 자동 전환).
- `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 확인 → `batch_state` 최종 상태 `deleted` 표시(`expired`과 동일한 의미: 재시도하지 않음, `--force`도 재내보내기하지 않음; [incremental-sync.zh-CN.md](incremental-sync.md) 참조), 그리고 해당 스레드의 각 `thread.json`에 `remote_deleted` 타임스탬프를 제자리에 추가(멱등성 — 이미 키가 있으면 덮어쓰지 않음).
- 스레드가 여전히 존재함 → 오탐: 그대로 보고하고 `index` 재실행을 권장하며, 상태는 변경하지 않음. 전송 오류는 백오프하여 다음 라운드로 연기; 연속 3회 인증 실패 시 중단하여 활성 스레드의 오표시 방지.

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

첫 번째 줄은 후보만 나열(오프라인 dry-run); 두 번째 줄은 온라인 확인 후 확인된 스레드에 표시.

## status

아카이브 상태 장부와 증분 변경 계획을 출력합니다. 네트워크 사용 없음, 읽기 전용. "아카이브 현재 상태는 어떠하며, 다음 `batch`가 무엇을 할 것인지"에 답하며,全程 네트워크에 접촉하지 않음.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `--account X` | 하나의 계정만 보고 | `index/library_*.json`가 있는 모든 계정 |
| `--json` | 기계 판독 가능 전체 보고서(stdout 단일 행 JSON, -v 수준 무시) | 끄기(사람이 읽는 로그 행) |

주요 동작:

- 데이터 소스는 모두 로컬: `index/library_*.json`(각 계정 인덱스 행) 및 `index/batch_state.json`(내보내기 상태의 유일한 진실 공급원). 변경 분류는 `batch`/`schedule`와 동일한 `plan_incremental` 순수 함수를 재사용하며, `new`/`updated`/`done`/`expired`/`deleted` 의미는 `batch`의 계산과 완전히 일치.
- 기본 INFO 출력: 계정당 한 줄 요약(인덱스 항목 수 및 신선도, `ok/expired/deleted/error` 상태 개수, `new/updated` 변경 개수, 조기 중단 수), 마지막 줄에 전역 `batch_state` 상태 장부(예: `559 ok + 13 expired + 12 deleted`).
- 상세 수준은 기존 `-v` 개수 플래그를 직접 사용: `-v`는 new/updated/error 스레드 제목 추가(첫 번째 행, 60자로 자름); `-vv`는 done/expired/deleted 스레드 추가 및 `lastUpdated`/`exported_at` 첨부; `-vvv`는 전체 자르지 않음 및 인덱스 `mode`/`search_mode` 필드와 state-only 목록 첨부(`batch_state`에는 있지만 모든 계정 인덱스에는 없는 레코드 — 원격 삭제 의심, [sync-deleted](#sync-deleted)를 통해 대조 가능).
- 가드: `index/` 또는 library 파일 누락 → `pplx-export index`를 가리키는 오류; `batch_state.json` 누락 시 빈 상태로 처리(모두 new로 판정). 사용자 수준 config 불필요 — 계정 이름은 library 파일 이름에서 열거.
- `--json`: stdout을 통해 전체 보고서(accounts/changes/threads/state_only/totals 단일 행 JSON) 출력 — `pplx-ask`와 동일한 계약 스타일.

```bash
pplx-export status                 # 全部账户摘要
pplx-export status -vv             # 五态线程明细
pplx-export status --account alice --json
```

## relations

내보내기된 스레드에서 대화 관계 그래프를 재구성하여 아카이브 루트 아래 `relations/edges.jsonl`에 저장하고, 사람이 읽을 수 있는 요약 `relations/graph.md`도 함께 저장합니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| *(공통 옵션만; `--out`만 적용됨)* | | |

주요 동작:

- 순수 오프라인, 네트워크 사용 없음, 아카이브에 대해 읽기 전용: re-render의 오프라인 재구성 파이프라인(`raw_entries.json` / `raw_blocks.json`) 재사용, `sub_agents`, `query_source`, 인용 등 모든 신호를 에지 감지에 사용 가능.
- raw 데이터가 없는 스레드는 `thread.json` + `conversation.md` 셸로 퇴화 — `same_space` 및 bare uuid 참조 에지만 트리거 가능.

```bash
pplx-export relations
```

## debug-js

로컬 WebBridge 데몬(`127.0.0.1:10086`)을 통해 현재 브라우저 페이지 컨텍스트에서 JavaScript 코드 조각을 실행하고 결과를 JSON으로 출력합니다. 디버깅용 비상구입니다.

| 매개변수 | 의미 | 기본값 |
|---|---|---|
| `JS代码`(위치 매개변수) | 페이지 컨텍스트에서 실행할 JavaScript 코드 | 필수 |

주요 동작:

- WebBridge 데몬에 연결 가능해야 하며, 브라우저에서 대상 Perplexity 페이지가 열려 있어야 함; 코드 조각은 페이지 자체 세션에서 실행.
- 출력 JSON은 5000자로 잘림.

```bash
pplx-export debug-js 'document.title'
```
