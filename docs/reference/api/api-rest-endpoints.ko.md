---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-rest-endpoints.zh-CN.md"
translation_source_sha256: "38129b3e7bf3833341615d818dc6e81c57bb7f290df912c314acd50a0de08772"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-参考rest-端点" data-pplx-source-anchor="true"></a>
# API 참조: REST 엔드포인트

<a id="rest-端点按用途分组" data-pplx-source-anchor="true"></a>
## REST 엔드포인트 (용도별 그룹)

규칙: `?version=2.18&source=default`는 일반 쿼리 문자열(대부분의 엔드포인트에 필수).

<a id="线程内容导出主路径" data-pplx-source-anchor="true"></a>
### 스레드 콘텐츠 (내보내기 기본 경로)
| 엔드포인트 | 설명 |
|---|---|
| `GET /rest/thread/<uuid>` | **일반(plain) 응답**: `entries[]`(각 라운드, `text`는 모든 단계 텍스트 포함), `background_entries[]`(**서브 에이전트 전체 워크플로우**), `thread_metadata`. `?cursor=` 페이지네이션 지원(`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **스키마화된 응답**: `entries[].blocks[]`(`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`), 서브 에이전트 프롬프트(`workflow_payload.objective_chunks`), 자산 서명 URL, 파일 콘텐츠 포함. use cases는 `rest.py:SCHEMATIZED_USE_CASES` 참조(workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | 최근 스레드 목록(홈페이지 사이드바용; `unread` 필드 포함) |
| **`POST /rest/thread/mark_viewed`** | **읽음 확인(2026-07-21 발견)**: body `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`, unread 즉시 반전. 사이드바에서 스레드 클릭 시 프론트엔드가 이 엔드포인트 호출. 참고: analytics의 "thread viewed" 이벤트는 unread를 **반전시키지 않음**(여러 번의 실제 테스트로 확인) |
| `GET /rest/thread/<uuid>/members` | **스레드 수준 공유 멤버**(실제 테스트 완료): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | `{"will_request_org_join": bool, "org_display_name": str|null}` 반환——조직 가입 관련, **threadAccess 의미와 무관**(실제 테스트로 확인) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | 정적 분석 존재; 직접 GET 테스트 시 400(매개변수 형태 미확인) |

<a id="资产元数据2026-07-20-探明过期资产救星" data-pplx-source-anchor="true"></a>
### 자산 메타데이터 (2026-07-20 확인, **만료된 자산 구제책**)

- **`GET /rest/assets/<asset_uuid>/data`** → 자산 전체 메타데이터(실제 테스트 200):
  - `asset_data.<类型>.url` 및 `asset_data.download_info[].url`: **새로운 CloudFront 서명 URL**——
    보관 시 원본 서명 URL이 만료된 경우 asset_uuid로 다운로드 주소를 다시 가져올 수 있음(플랫폼이 자산을 제거하지 않은 경우);
  - 동시에 `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space` 제공
    (asset → 스레드 역추적 체인);
  - `signed_url: null`, `read_write_token`, `allow_remix` 등 필드.
- **적용 범위(실제 테스트 완료)**: 실제 asset uuid 사용 가능; **`toolu_` 접두사의 클라우드 워크스페이스 핸들(DOC_FILE/CODE_FILE
  URL 형태 없음)은 404 ASSET_NOT_FOUND 반환**; `file-repository/download`는 실제 URL 필요, `file:repo/...` 핸들 허용 안 함
  (400 failed to parse). toolu 유형 자산은 현재 API 다운로드 채널 없음.
- 관련: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access`(정적 분석 존재, 실제 테스트 안 함).
- 적용: 도구에서 `pplx-export assets-backfill` 구현(인라인 추출 + 이 엔드포인트 온라인 갱신, [§4](api-responses-errors.md) 적용 도구 참조).

- **ENTRY_EXPIRED**: 약 3개월 전 스레드/아티팩트가 플랫폼에서 제거됨, 요청 시 특정 오류 본문 반환——도구에서 최종 상태로 표시하고 재시도 안 함.
- **스레드 삭제(2026-07-23 WebBridge + chunk 조사 실제 테스트)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, body `{entry_uuid, read_write_token}`,
  성공 `200 {"status":"success"}`; 중복 삭제 멱등성 유지 200; 존재하지 않는 uuid 삭제 → 404 `THREAD_NOT_FOUND`;
  **`read_write_token` 획득(같은 날 실전 검증)**: `GET /rest/thread/<uuid>` 응답의
  `entries[].read_write_token` 첫 번째 비어 있지 않은 값 사용 가능(활성 스레드에 대해 10/10 삭제 성공 확인);
  **쓰기 작업은 반드시 www 도메인 사용**(베어 도메인은 DELETE에 301 반환). GraphQL mutation 없음, 일괄 삭제 엔드포인트 없음
  (UI 일괄 삭제는 프론트엔드에서 항목별 루프). 삭제는 스레드 수준 파괴, 복구 불가, 스레드가 자동으로 해당 공간에서 사라짐
  (먼저 `batch_remove_collection_threads`로 이동할 필요 없음).
  소프트 방식: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (body `{context_uuids:[...]}`, 정적 분석만, 실제 테스트 안 함).
- **ENTRY_DELETED**: 스레드 삭제 후 `GET /rest/thread/<uuid>`가 HTTP 400 `ENTRY_DELETED` 반환
  (ENTRY_EXPIRED와 마찬가지로 400이지만 code 다름)——도구에서 `EntryDeletedError`로 매핑
  (`EntryExpiredError` 하위 클래스), batch_state를 최종 상태 `deleted`로 표시.
- 각 라운드 entry에는 `context_uuid` 포함(= 플랫폼 `past_session_contexts` UUID, 이중 ID 네임스페이스 매핑의 핵심).

<a id="空间collections" data-pplx-source-anchor="true"></a>
### 공간 (collections)
| 엔드포인트 | 설명 |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **공간 메타데이터**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. permission 실제 테스트: 4=소유자, 2=편집 가능. 볼 권한 없을 때 `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` 반환(HTTP는 여전히 200) |
| `POST /rest/collections/create_collection` | **공간 생성**(2026-07-21 WebBridge 캡처 실제 테스트): body `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → 전체 collection 반환(uuid/slug/url/user_permission=4). BOT 공간이 이렇게 생성됨 |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **공간 스레드 목록(cookie 직접 연결, 브라우저 기반 space-index 대체 가능)**: 응답은 배열, 각 항목에 `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview` 등 포함. **페이지네이션: `&offset=N`(페이지당 20)**, `has_next_page`는 각 항목에 있음; `total_threads` 의미는 다소 큼(computer 하위 스레드 포함, 관측 99 vs 최상위 27) |
| `POST /rest/collections/batch_move_threads` | **스레드를 공간으로 이동**(실제 테스트 성공): body `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}`——**context_uuid 사용, entryUUID 아님** |
| `POST /rest/collections/batch_remove_collection_threads` | 공간에서 일괄 제거(body `{items:[{collection_uuid,...}]}`, 실제 테스트 안 함) |
| `GET /rest/collections/list_user_collections` | **현재 계정 공간 목록**(실제 테스트 16개): 각 항목에 `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page` 등 포함, list_recent보다 정보가 완전함 |
| `GET /rest/collections/list_recent` | 현재 계정 최근 공간 목록(`title/uuid/emoji/is_pinned/link`, 실제 테스트 5개 항목) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | 공간 접근 신청 정보(실제 테스트 안 함) |
| `GET /rest/collections/<uuid>/join-requests` | 가입 신청(심층 분석 안 함) |
| `GET /rest/spaces/<uuid>/tasks` | `{"tasks":[]}` 반환——관측 결과 비어 있음; 공간의 예약/computer 작업으로 추정, 스레드 목록 아님 |
| `GET /rest/spaces/<uuid>/recurring_tasks` | 주기적 작업(실제 테스트 안 함) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | 공간 고정/예약 스레드(페이지 로드 시 호출, 심층 분석 안 함) |

- **계정 간 포크(branch_of, 사용자 실제 테스트 인지 2026-07-23)**: 공간 공유 스레드는 다른 멤버 계정이
  **해당 계정만 볼 수 있고, 해당 계정이 계속하는** 포크 스레드로 "계속"할 수 있음——A 계정 스레드가 공간 공유 후,
  B가 계속하여 B 개인 포크를 생성할 수 있음. 보관 라이브러리에 아직 인스턴스 없음, relations 엣지는 아직 구현하지 않음; 포크 스레드의 API 신호 필드
  (부모 스레드 포인터/포크 표시)는 첫 사례 발생 시 확인 및 기록.

<a id="账户会话" data-pplx-source-anchor="true"></a>
### 계정/세션
| 엔드포인트 | 설명 |
|---|---|
| `GET /api/auth/session` | 현재 세션 `{user:{email,...}}`——계정 확인 및 자동 전환 탐지용 |
| `GET /api/auth/linked-accounts` | [§1.2](api-authentication.md) 참조(primary 활성화 시에만 전체) |
| `GET /rest/user/info`, `/rest/user/settings` | 사용자 프로필/설정(심층 분석 안 함) |

<a id="积分用量2026-07-20-探明" data-pplx-source-anchor="true"></a>
### 크레딧 사용량 (2026-07-20 확인)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → 단일 스레드 크레딧 사용량(실제 테스트 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **참고**: `thread_id`는 **context_uuid**(psc_uuid)가 필요, entryUUID 전달 시 403
  `thread_usage_forbidden`("Thread does not belong to the current user", 실제로는 ID 형태 오류).
- context_uuid 출처: `list_collection_threads`(space-index REST 버전에서 27/27 커버리지),
  스레드 항목 `context_uuid` 필드(보관 thread.json의 `psc_uuid`).
- 본인 계정 스레드만 조회 가능(타 계정 403)——다중 계정 수집 시 계정별 자동 전환 필요.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: 목록 버전, 두 계정 실제 테스트 모두 빈 값 반환
  (조직 청구 전용으로 추정, 대기 중).
- 기타 billing 엔드포인트(`/rest/billing/credits/balance` 등)는 [§7 부록](api-discovery-roadmap.md) 참조, 심층 분석 안 함.

<a id="官方导出页面导出按钮的后端2026-07-20-探明" data-pplx-source-anchor="true"></a>
### 공식 내보내기 (페이지 "내보내기" 버튼의 백엔드, 2026-07-20 확인)

- **`POST /rest/thread/export`**, body: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<名称>"}`
- 응답: `{"file_content_64": "<base64>", "filename": "..."}`
- 실제 테스트 format: **`md`**(로고 `<img>` 헤더가 있는 공식 markdown), **`pdf`**(%PDF 바이너리 ~880KB),
  **`docx`**(PK zip ~350KB)——모두 HTTP 200. 다른 format 값은 시도 안 함.
- **콘텐츠 경계(실제 테스트 확인)**: 반환되는 것은 **전체 스레드** markdown(query + answer 요약 + `[^1_N]` 각주 인용),
  **RESEARCH_REPORT 보고서 본문은 포함하지 않음**——심층 연구 보고서 본문은 서명 URL을 통해서만 획득 가능(§3.7),
  즉 현재 report.md의 서명 URL 링크가 **공식 보고서 소스**(페이지 아티팩트 패널 다운로드와 동일 소스)이므로 이 엔드포인트를 사용할 필요 없음.
- 가치: 공식 스레드 버전 markdown은 conversation 수준 교차 검증 소스로 사용 가능(공식 렌더링 인용 각주/형식).

<a id="资产报告下载" data-pplx-source-anchor="true"></a>
### 자산/보고서 다운로드
- 스키마화된 응답의 **CloudFront 서명 URL**(`d2z0o16i8xm8ak.cloudfront.net`): urllib 직접 다운로드,
  cookie/인증 불필요; 다중 버전 파일은 `created_at` 기준 정렬 번호.
- 연구 보고서 대체 소스: RESEARCH_ANSWER 단계의 S3 URL(`ppl-ai-file-upload.s3.amazonaws.com`, **만료됨**);
  추가 대체 페이지 렌더링 추출(KaTeX `<annotation>`).
- **약 3개월 후 제거**: 아티팩트/보고서 소스 링크 만료 시 복구 불가——내보내기는 반드시 적시에 수행.

<a id="其他观测到的端点页面加载未深入" data-pplx-source-anchor="true"></a>
### 기타 관측된 엔드포인트 (페이지 로드, 심층 분석 안 함)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates`(SSE), `/api/version`.

<a id="消息提交与遥测2026-07-20-webbridge-cdp-探明" data-pplx-source-anchor="true"></a>
### 메시지 제출 및 원격 측정 (2026-07-20 WebBridge + CDP 확인)

<a id="提交端点post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### 제출 엔드포인트: `POST /rest/sse/perplexity_ask`
- 전체 요청 본문 샘플(합성 예시)은 `docs/perplexity-api-samples/` 참조:
  - `ask_envelope_deep_research.json`——deep-research 계속 라운드(2026-07-20; 39개 params + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + `last_backend_uuid` 계속 체인
  - `ask_envelope_search.json`——표준 검색, 홈페이지에서 새 대화 시작(2026-07-21; 35개 params + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json`——모델 위원회, 홈페이지에서 새 대화 시작(2026-07-21; 36개 params + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- 주요 필드(deep-research 계속 라운드 실제 테스트):
  - `mode: "copilot"`(심층 연구); `model_preference: "pplx_alpha"`
  - **대화 계속 체인**: `last_backend_uuid`(이전 라운드 backend uuid) + `query_source: "followup"`
  - `frontend_uuid`(이번 라운드 새 uuid), `read_write_token`, `target_collection_uuid`(소속 공간),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`**(첫 입력부터 제출까지의 밀리초——행동 원격 측정이 제출과 함께 보고됨)
  - `use_schematized_api: true`, `supported_block_use_cases`(전체 블록 목록, §3.1 스키마화된 항목과 대응),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- 응답은 SSE 스트림(프론트엔드에서 fetch-event-source `getReader()`로 소비——앱 모듈 초기화 시 fetch 참조 고정,
  **페이지 이후 fetch/XHR hook 무효**; 또한 **스트리밍 응답 본문은 브라우저에 보존되지 않음**(`Network.getResponseBody` 반환
  No data found)——패킷 캡처는 CDP `Network.getRequestPostData`에만 의존 가능(요청 본문 사용 가능).
- 스트림 콘텐츠 최종 상태는 `/rest/thread/<uuid>`의 entries/blocks와 동일(동일 데이터, 증분 전달)——
  내보내기 도구는 스트림을 읽을 필요 없이 최종 상태를 직접 가져오면 됨.

<a id="遥测post-resteventanalytics批量高频" data-pplx-source-anchor="true"></a>
#### 원격 측정: `POST /rest/event/analytics`(배치, 고빈도)
실제 테스트 이벤트(event_data 요점 포함):
| event_name | 주요 필드 | 설명 |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | 페이지 보기 이벤트——**unread 반전 안 함**(실제 테스트로 확인; 실제 읽음 확인은 `POST /rest/thread/mark_viewed`, §3.1 참조) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs`(**해당 라운드 읽기 체류 밀리초**), `userId`, `isPro`, `deviceInfo`(동시성 수/화면/색심도) | 읽기 시간 원격 측정(unread 반전 안 함, 실제 테스트로 확인) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | 제출 동작 |
| `query first llm token` | `startLLMTokenElapsed`(첫 토큰 지연), 전체 `queryStr` | 성능 원격 측정 |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, 전체 `queryStr` | 성공 확인 |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | 위원회 모델 선택기 상호작용 |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | 오른쪽 패널 보기 |
- 이벤트 공통 필드: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info`(hardwareConcurrency/화면/색심도/architecture), `isBrowserExtension`, `web_platform`.
- **참고**: 실제 테스트에서 특정 이벤트가携带하는 `userId`는 **다른 계정**의 uid(uid는 계정 A에 속하지만 세션은 이미 계정 B)——
  원격 측정 SDK의 profile id에 캐시 지연이 있으므로 원격 측정 userId로 현재 계정을 판단할 수 없음.
- 또한 datadog RUM(`browser-intake-datadoghq.com/api/v2/rum`) 고빈도 보고(스크롤/마우스/성능, 콘텐츠 미해석).

<a id="模式与模型选择2026-07-21-付费账户实测" data-pplx-source-anchor="true"></a>
#### 모드 및 모델 선택 (2026-07-21 유료 계정 실제 테스트)
- **`GET /rest/models/config/v2` = 권위 모델 전체 목록**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`、`agentic_research_compare_models`(위원회 기본 세 모델).
  `pplx-ask models`가 이 엔드포인트를 호출.
  - 공식 대응(실제 테스트): **search = `pplx_pro`(UI 이름 "최적"), research = `pplx_alpha`
    (UI 이름 "Deep research")**.
  - search 모드 UI 선택 가능 모델 목록(Deep research 없음): 최적(pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **`mode` 필드는 항상 `"copilot"`, 모드 판별 필드 아님**(검색/심층 연구/모델 위원회 모두 동일).
- 판별은 **`model_preference`**에서:
  - 검색: `pplx_pro`(또는 사용자가 선택한 모델 id, 예: `experimental`=Sonar 2, `gpt56_sol`…)
  - 심층 연구: `pplx_alpha`(**UI에 모델 선택기 없음**, 고정)
  - **모델 위원회**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 模型>]`**
    (실제 테스트 기본 `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    UI는 **슬롯별 단일 선택**, 후속 질문 시 모델 수 2로 변경).
  - 단계별 학습: `pplx_study`; Computer: `pplx_asi*` 시리즈.
- 작성 영역 모델 선택기(모델 ⌄)와 위원회 "N개 모델 ⌄" 선택기는 각각 위 필드에 대응;
  원격 측정 이벤트 `ask input model selector opened`는 `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels`携带(이전 심층 연구 스레드는 `searchMode: "research"`).
- 새 대화: `query_source: "home"`, `last_backend_uuid` 없음, `frontend_context_uuid` 있음;
  대화 계속: `query_source: "followup"` + `last_backend_uuid` 계속 체인.

<a id="entrysearch_mode会话模式的权威记录字段2026-07-22-定案" data-pplx-source-anchor="true"></a>
#### entry.search_mode: 세션 모드의 권위 기록 필드 (2026-07-22 확정)
`/rest/thread/<uuid>`의 **각 entry**에는 `search_mode`가 포함되어 있으며, 이는 플랫폼이 해당 라운드 세션 모드에 대한 권위 기록임
(모드 판별 최우선 순위 신호, `normalize.SEARCH_MODE_MAP`):

| search_mode | 의미(UI/모델) | 보관 모드 |
|---|---|---|
| `SEARCH` | 일반 검색(default_models.search=pplx_pro "최적" 및 UI 선택 가능 모델) | search |
| `STUDIO` | labs 세션(pplx_beta), UI는 search 쪽에 속함 | search |
| `RESEARCH` | Deep research(default_models.research=pplx_alpha, UI 고정 선택기 없음) | deep-research |
| `AGENTIC_RESEARCH` | 모델 위원회(pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | 단계별 학습(pplx_study) | study |
| `ASI` | Computer(pplx_asi*) | computer |

- 보관 전체 값 실제 테스트: 여섯 가지 값 모두 실제 보관 라이브러리에 인스턴스 존재, SEARCH와 RESEARCH가 대다수,
  STUDIO가 그 다음, ASI / STUDY / AGENTIC_RESEARCH는 소수.
- **pplx_alpha ⟺ RESEARCH 상호 증명**: 보관된 수백 개의 플랫폼 SEARCH 진입점+pplx_alpha 스레드 100%
  `search_mode=RESEARCH`; 수백 개의 순수 pplx_pro 스레드는 모두 `search_mode=SEARCH`——
  "pplx_alpha는 일반 search에서 자주 사용되는 모델"이라는 이전 통계는 실제로 분류기 오판 샘플로, 성립하지 않음.
- 스레드 내에서 여러 값이 나타날 수 있음(모드 전환, 실제 테스트 SEARCH+RESEARCH 혼합): 판별은 특이성 기준
  computer>council>study>deep-research>search 순으로 가장 높은 값을 취함.

<a id="模型委员会输出结构与展开行为" data-pplx-source-anchor="true"></a>
#### 모델 위원회 출력 구조 및 확장 동작
- 단일 라운드 산출물 = N개 모델 각각의 "Council: <모델명>" 블록(각각 검색어/출처/답변 포함) + 종합 부분:
  **Where Models Agree**(합의 매트릭스, 항목별 세 모델 ✓ 대조 + Evidence),
  **Where Models Disagree**(의견 차이 표, 각 모델 입장 + 차이 원인),
  **Unique Discoveries**(각 모델의 고유 발견), 마지막으로 관련 질문 추천——**모두 동일한 SSE 스트림에서 전송됨**.
- 확장 동작(**생성 중** 확장 포함): 확장 행은 ">" chevron이 있는 행(단계 행/"출처" 행/Council 행),
  클릭 시 확장, **순수 클라이언트 측 렌더링, 콘텐츠 요청 없음**——이 세션의 1208개 요청 중 921개는 favicon/글꼴 등 정적 리소스,
  확장 동작 자체는 favicon 로드와 /api/version만 트리거. 스트리밍 중 확장은 스트림의 계속 전송을 방해하지 않음.
- 첫 토큰 지연 실제 테스트 ~204s(세 모델 병렬 생성, 단일 모델보다 현저히 김); 출처 수 실제 테스트 236.
- 작성 영역(Lexical) 자동화 요점: 텍스트는 CDP `Input.insertText`로 주입해야 함(execCommand/fill 후
  Lexical 내부 상태가 동기화되지 않아 Enter 무효); 제출은 CDP Enter 또는 aria-label="제출" 버튼 클릭 사용 가능
  (위원회 모드에는 명시적 제출 화살표 있음).

<a id="续历史对话的行为特征2026-07-20-实测" data-pplx-source-anchor="true"></a>
#### 대화 기록 계속의 동작 특성 (2026-07-20 실제 테스트)
1. 스레드 페이지 로드 → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. 후속 질문 제출 → `rate-limit/status` → `sse/perplexity_ask`(`last_backend_uuid` 계속 체인 포함) → 고빈도 analytics.
3. 생성 중 → SSE 스트림 증분 렌더링; 완료 후 다시 analytics 배치(`thread entry exited` 읽기 시간 포함).
4. deep-research 계속 라운드도 보고서 구조 생성(이번 라운드 5단계 완료).
