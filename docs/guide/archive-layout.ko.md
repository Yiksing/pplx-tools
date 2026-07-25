---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/archive-layout.zh-CN.md"
translation_source_sha256: "87d25ea40af1217fcbcddafae7c173aebca9a6669c09a8f77ccb2e8eee557782"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="归档目录结构" data-pplx-source-anchor="true"></a>
# 아카이브 디렉터리 구조

`pplx-export`에서 다운로드한 모든 내용은 단일 출력 트리에 저장됩니다. 기본값은 `./web_archive/`이며
(`--out`로 재정의 가능). 이 페이지는 해당 트리에 대한 안내입니다: 각 디렉터리와 파일의 역할, `thread.json`이
가지고 있는 키, 그리고 세션이 여러 날에 걸쳐 이어질 때 도구가 하나의 스레드에 하나의 디렉터리만 유지하도록 보장하는 방법. 모든 내용은 도구에 의해 생성됩니다.
메커니즘에 대한 자세한 내용은 [데이터 모델 및 디렉터리 계약](../architecture/data-model.md)과 [내보내기 파이프라인](../architecture/export-pipeline.md)을 참조하세요.

<a id="输出目录树" data-pplx-source-anchor="true"></a>
## 출력 디렉터리 트리

```
web_archive/
├── alice/                                # 每账户一个文件夹（作者显示名）
│   ├── search/                           # 模式：search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # 每线程一个目录
│   │       ├── thread.json               # 元数据 + 可选登记键
│   │       ├── conversation.md           # 简版：逐轮 Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # 完整版：完整工作过程细节
│   │       │   └── ...
│   │       ├── sources.json              # 全线程引文（按 url 去重）
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research 报告（有才存在）
│   │       ├── raw_entries.json          # plain API 响应，原样落盘（恒存在）
│   │       ├── raw_blocks.json           # schematized API 响应（search 无此文件）
│   │       └── assets/
│   │           ├── assets_manifest.json  # 多版本清单
│   │           └── files/                # 已下载的资产文件体
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # 状态文件与索引（见下）
├── relations/                            # edges.jsonl + graph.md（由 `pplx-export relations` 重建）
├── crosscheck/                           # 交叉核验报告（人工/评审产物）
└── bob/ ...
```

<a id="线程目录" data-pplx-source-anchor="true"></a>
## 스레드 디렉터리

각 스레드는 정확히 하나의 디렉터리에 해당하며, `thread_dir_for`(`fs_writer.py:58-72`)로 계산됩니다:

```
<账户显示名>/<模式>/<YYYY-MM-DD>_<标题slug>_<uuid8>/
```

| 구성 요소 | 출처 | 설명 |
|---|---|---|
| `<账户显示名>` | 스레드 작성자, `author_folder` → `_safe_folder` 정제(`fs_writer.py:40-51`) | 경로 구분자 및 Windows 비허용 문자(`:*?"<>\|`)를 `_`로 대체; `.`/`..` 거부(공유 공간 경로 탐색 방지); 나머지 문자(공백 포함)는 그대로 유지 |
| `<模式>` | `detect_mode` | 다섯 가지 모드 중 하나, [세션 모드](modes.md) 참조 |
| `<YYYY-MM-DD>` | `thread.json`의 `lastUpdated` 날짜 접두사 | 플랫폼 측 마지막 업데이트 날짜, **내보내기 날짜 아님** — 이어지는 스레드가 업데이트되면 변경됨(아래 마이그레이션 참조) |
| `<标题slug>` | `slugify(title)`(`normalize.py:261-263`) | 최대 40자, 비단어 문자 → `-`, 빈 제목 → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | 스레드 UUID의 앞 8자 — 디렉터리의 식별 앵커 |

<a id="线程目录内的文件" data-pplx-source-anchor="true"></a>
## 스레드 디렉터리 내 파일

<a id="threadjson元数据与登记信息" data-pplx-source-anchor="true"></a>
### thread.json — 메타데이터 및 등록 정보

`write_thread`(`fs_writer.py:224-253`)에 의해 작성됨. 항상 존재하는 키:

| 키 | 내용 |
|---|---|
| `web_uuid` | 웹 entryUUID — 스레드 URL의 UUID, 스레드의 식별자 |
| `psc_uuid` | 플랫폼 `context_uuid`(널 가능; 첫 번째 비어 있지 않은 턴 값 사용) — 공간 인덱스에 사용되는 이중 ID |
| `url` | 스레드 정규 URL |
| `title` | 스레드 제목 |
| `mode` | 판별된 모드(`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | 작성자 계정 표시 이름 |
| `export_via` | 내보내기를 수행한 계정의 사용자 이름 — 해당 계정을 통해 내보낸 공유 공간 스레드에 특히 중요 |
| `space` | `{"uuid", "title", "slug"}` 또는 `null` |
| `lastUpdated` | 플랫폼 마지막 업데이트 타임스탬프(증분 동기화를 위한 기계 비교 계약) |
| `threadAccess` | 플랫폼 접근 플래그 |
| `n_turns` | 턴 수 |
| `n_sources` | 전체 스레드 인용 수 |
| `metadata` | API 응답의 `thread_metadata`, 원본 그대로 유지 |
| `report_info` | `{"title", "file_name", "url"}` 또는 `null` |
| `exported_at` | 내보내기 시간(UTC ISO 8601) |

선택적 키 — 해당 내용이 없으면 나타나지 않음:

| 키 | 작성 시점 | 내용 |
|---|---|---|
| `interruptions` | 완료되지 않은 워크플로우 존재(`fs_writer.py:242-244`) | `{location, kind, headline, status}` 목록; [세션 모드 — 중단 표시](modes.md) 참조 |
| `answer_variants` | 답변 재작성 변형 감지(`fs_writer.py:247-252`) | 좁힌 기준의 `side_by_side_metadata` 위치 필드; [세션 모드 — 답변 재작성 변형](modes.md) 참조 |
| `remote_deleted` | `pplx-export sync-deleted --online`가 원격 삭제 확인 | 묘비 타임스탬프, 제자리 작성, 멱등성(기존 값 덮어쓰지 않음; `sync_deleted_cmd.py:215-244`) — 로컬 아카이브 자체는 유지 |

<a id="conversationmd简版" data-pplx-source-anchor="true"></a>
### conversation.md — 간략 버전

`render_conversation`(`render.py:641`): 헤더(모드 / 작성자 / 턴 / 인용 수), 그 후 각 턴마다 `### Query` + `### Answer` 쌍, 답변 전체 표시; 존재하는 경우 끝에 스레드 수준 백그라운드 작업 부록 첨부.
가장 먼저 열어볼 파일; 각 턴의 작업 과정은 `turns/`에 있음.

<a id="turnsturn_nnnnmd完整版" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — 전체 버전

`render_turn`(`render.py:596`): 각 턴마다 하나의 파일(`turn_0001.md` …), 전체 작업
과정 포함 — 단계, 도구 호출, 하위 에이전트 실행, 표, 해당 턴의 인용. 스레드 턴 수가 줄어들면 번호가 높은 이전
`turn_*.md`만 삭제, 변경되지 않은 파일의 mtime 유지(`fs_writer.py:287-301`).

### sources.json / sources.md

전체 스레드 인용, URL 기준 중복 제거(`fs_writer.py:270-278`). `sources.json`은
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`; `sources.md`는
동일 목록의 번호가 매겨진 Markdown 링크 버전.

### report.md

deep-research의 보고서 산출물, 스레드가 보고서를 가지고 있을 때만 작성(`fs_writer.py:308-316`):
보고서 제목, 원본 산출물 파일 이름, 그 후 전체 보고서 Markdown.

<a id="raw_entriesjson-raw_blocksjson原始保真" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — 원본 충실도

API 응답을 **파싱 전**에 원본 그대로 디스크에 저장(`fs_writer.py:257-266`):

- `raw_entries.json` — plain 응답: `{"thread_metadata", "entries", "background_entries"}`,
  항상 존재.
- `raw_blocks.json` — schematized 응답, 구조 동일. `search` 스레드는 이 파일 없음(blocks 미수집);
  나머지 네 가지 모드는 모두 수집하며, 모든 모드 판별 신호가 없을 때도 fallback으로 수집.

이 두 파일은 전체 아카이브의 충실도 앵커: 파싱, 렌더링, 등록 정보를 모두 오프라인에서 재구성 가능, 네트워크 불필요.
[오프라인 작업](../architecture/offline-operations.md) 참조.

<a id="assets产物与清单" data-pplx-source-anchor="true"></a>
### assets/ — 산출물 및 매니페스트

다운로드 가능한 산출물(computer 모드 파일 및 API에 나열된 기타 자산)은 CloudFront 서명 URL을 통해 `assets/files/`로 다운로드;
확장자는 다운로드 시 URL 경로, 내용 매직 넘버 또는 자산 유형에 따라 결정.
`assets/assets_manifest.json`(`fs_writer.py:320-330`)은 각 버전을 기록:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count`는 항상 **총 버전 수**(Σ `len(versions)`), 파일 그룹 수가 아님 — 파일 그룹 수는 `len(files)` 사용.

<a id="index-层" data-pplx-source-anchor="true"></a>
## index/ 계층

`web_archive/index/`는 도구가 관리하는 상태와 인덱스를 저장 — 수동 수정 금지:

| 파일 | 작성자 | 의미 |
|---|---|---|
| `library_<account>.json` | `pplx-export index`(`index_cmd.py:17-43`) | 계정 전체 스레드 인덱스(GraphQL); batch / 스케줄링 / 공간 인덱스의 입력 |
| `batch_state.json` | `BatchState`(`state.py`) | 재개 가능 체크포인트: uuid → 상태(ok/error/expired/deleted) + lastUpdated; 원자적 쓰기; 손상된 파일은 자동으로 `.corrupt-<ts>`로 백업 |
| `.cookies.json` | 쿠키 캐시(`common.py:111`, `common.py:150`) | 12시간 신선도 쿠키 캐시, 출처 및 계정 이메일 포함; 먼저 `0o600`로 임시 파일 작성 후 원자적 교체(세션 자격 증명은 소유자만 읽기 가능) |
| `space_<slug>.json` | `pplx-export space-index`(`spaces_cmd.py:106-167`) | 단일 공간 스레드 목록, `context_uuid` 이중 ID 매핑 포함 |
| `space_meta.json` | `pplx-export spaces --fetch-meta`(`spaces_cmd.py:299-330`) | 공간 owner/member 캐시, 재구성 시 재사용 |
| `credit_usage_<account>.json` | `pplx-export usage-backfill`(`usage_backfill_cmd.py:17`) | 스레드별 할당량 사용량(멱등성, 재개 가능, 25개마다 디스크에 기록) |
| `cron_snippet.txt` | `pplx-export schedule`(`scheduler.py:48-78`) | cron 호출 조각(절대 경로) |
| `answer_variants_log.jsonl` | `variant_log.append_registry`(`variant_log.py:76`) | 답변 재작성 변형 중앙 등록소, (스레드, entry) 기준 중복 제거, 멱등성 |
| `logs/` | `--log-file`(`common.py:218-229`) | 전체 DEBUG 로그 |

<a id="spaces-层" data-pplx-source-anchor="true"></a>
## spaces/ 계층

`pplx-export spaces`는 `index/library_*.json`를 집계하여 공간 인덱스 재구성(`spaces_cmd.py:259-389`):
각 공간마다 하나의 `<slug>.md`(참여 계정 집계, owner/member 헤더, 스레드 테이블, 내보내기 위치 역링크),
추가로 `spaces.json` 레지스트리.

!!! note "출력 위치"
    `spaces/`는 현재 작업 디렉터리를 기준으로 출력(`spaces_cmd.py:332`) — **따르지 않음** `--out`.
    수동 수정 금지: 다음 재구성 시 덮어쓰기.

<a id="跨天续接按-uuid-身份的目录迁移" data-pplx-source-anchor="true"></a>
## 여러 날에 걸친 이어짐: UUID 식별자 기반 디렉터리 마이그레이션

디렉터리 이름에 `lastUpdated` 날짜가 포함되어 있으므로, 다음 날 스레드를 이어갈 때 단순 계산은 **새** 디렉터리를 생성합니다.
writer는 UUID 식별자를 기준으로 중복을 방지합니다(`thread_dir_for`, `fs_writer.py:58-72`):

1. **찾기**: `find_thread_dirs`(`fs_writer.py:74-105`) 전체 저장소에서 `_<uuid8>`로 끝나는
   디렉터리 검색 — 계정 및 모드 전반. 후보 디렉터리는 해당 `thread.json`가 존재하고, 파싱 가능하며, `web_uuid`가
   완전히 일치할 때만 수락; 누락, 손상 또는 불일치 디렉터리는 그대로 둠(누락 이전이 잘못된 병합보다 나음).
2. **병합**: `_merge_into`(`fs_writer.py:107-178`)는 이전 디렉터리를 새 디렉터리로 병합 — 파일 합집합
   (이전 디렉터리 고유 파일 유지); 동일 이름 동일 내용은 건너뜀; 동일 이름 충돌은 **항상 대상 측 유지**(의미상 업데이트된 쪽),
   각 항목 로그 기록. 각 복사 파일은 sha256 검증 후 이전 디렉터리 삭제; 실패 시 이전 디렉터리
   그대로 유지, 재시도는 멱등성.
3. **이력 중복 정리**: `consolidate_uuid`(`fs_writer.py:180-209`) 전체 저장소에서 동일 UUID의
   중복 날짜 디렉터리 병합, `lastUpdated`이 가장 큰 것 유지 — 이전 버전에서 남은 중복 디렉터리에 대한 fallback 수단.

동일한 UUID 엄격성은 공간 인덱스 역링크도 보호: `thread.json` 누락/손상/불일치 후보 디렉터리는
링크되지 않음.

<a id="可手改与工具托管" data-pplx-source-anchor="true"></a>
## 수동 수정 가능 및 도구 관리

- **도구 관리(수동 수정 금지)**: 스레드 디렉터리 내 모든 것, 그리고 `index/`, `spaces/`, `relations/`.
  내용에 문제가 있으면 도구를 수정하고 다시 생성 — 렌더링 수정은 `pplx-export re-render`, 데이터 수정은 해당
  backfill 명령([유지 관리 명령](maintenance-commands.md) 참조) — 각 산출물이 raw에서
  재현 가능하도록 함.
- **수동 수정 가능**: 문서 및 `web_archive/crosscheck/` 검토 보고서. 한 가지 사용자 수준 예외: 수동으로 복구된
  대체 답변은 스레드 디렉터리 내 `rewritten_answer_variant.md`로 기록 가능 —
  [세션 모드 — 답변 재작성 변형](modes.md) 참조.

<a id="另见" data-pplx-source-anchor="true"></a>
## 함께 보기

- [세션 모드](modes.md) — 다섯 가지 모드 및 각 산출물
- [증분 동기화](incremental-sync.md) — `lastUpdated`가 재내보내기를 구동하는 방법
- [유지 관리 명령](maintenance-commands.md) — re-render, backfill, sync-deleted
- [데이터 모델 및 디렉터리 계약](../architecture/data-model.md) — 기본 dataclass
- [내보내기 파이프라인](../architecture/export-pipeline.md) — 이 파일들이 작성되는 방법
- [오프라인 작업](../architecture/offline-operations.md) — `raw_*.json`에서 모든 것을 재구성
