---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-graphql.zh-CN.md"
translation_source_sha256: "8abe002576d89da5b7dbcdbba673ce6423cf94c8944606f70e60addcf6268ac0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-参考graphql" data-pplx-source-anchor="true"></a>
# API 참조: GraphQL

<a id="graphql持久化查询-apq" data-pplx-source-anchor="true"></a>
## GraphQL (Persisted Query APQ)

- **엔드포인트**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **형식**: persisted query — 본문에 operationName + variables + sha256 해시 포함 (query 텍스트 불필요).
- **구현**: `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery列表首页" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (목록 첫 페이지)
- sha256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- 변수: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- 응답 경로: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- node 필드 (어댑터 사용): `name(title)`, `entryId(entryUUID)`, `slug(href)`, `mode`, `displayModel.modelID`,
  `updatedAt(lastUpdated)`, `status`, `space{spaceUuid,title,slug}`
- **아카이브 측 계약 (2026-07-22 V5-01)**: `web_archive/**/thread.json`의 `lastUpdated`는 이 필드와 항상 동일함
  (ISO 전체 정밀도로 원본 그대로 저장); 배치/단일 내보내기 멱등성 비교(`is_unchanged`)는 이를 기준으로 하며,
  더 이상 렌더링 계층 표시 형식(`YYYY-MM-DD HH:MM UTC`)을 사용하지 않음.
- **아카이브 측 보강 (2026-07-23)**: 인덱스 저장 행(`index/library_*.json`)의 `search_mode` 키는
  아카이브 측 보강 필드 — 이 쿼리의 node에는 search_mode가 포함되지 않으며, `pplx-export search-mode-backfill`가
  스레드 수준 데이터(`GET /rest/thread/<uuid>`의 `entries[].search_mode`)에서 이를 보완함 (로컬 raw 우선,
  네트워크 폴백); `index` 새로고침은 entryUUID 기준 병합으로 유지됨. `batch --mode` 필터는 이 필드의 권위 있는 매핑을 우선 사용.

<a id="libraryrecentthreadspaginationquery翻页" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery (페이지 매김)
- sha256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- 변수: 첫 페이지 변수 + `{cursor, count}` (**변수명은 cursor/count이며, after/first가 아님**)
- 응답 구조는 위와 동일. `hasNextPage`가 참이지만 `endCursor`가 비어 있으면 중지해야 함 (그렇지 않으면 동일 페이지가 반복됨).

<a id="computer-仪表盘操作组2026-07-20-从-route-chunk-提取服务器未注册" data-pplx-source-anchor="true"></a>
### Computer 대시보드 작업 그룹 (2026-07-20 route chunk에서 추출, **서버에 미등록**)

`ComputerDashboardPage-*.js` chunk에 Relay 전체 쿼리 텍스트 + persisted id 포함 (추출 방법은 [§7](api-discovery-roadmap.md) 참조).
구조 요점: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— 즉 threadGroup + mode로 필터링된 스레드 목록; node에는 `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread` 포함.

| operation | persisted id (처음 16자리) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (WebSocket 구독) |

**실측**: 이 id로 `/rest/perplexity_ask/graphql` 호출 시 `PERSISTED_QUERY_NOT_FOUND` 반환
(현재 배포에 미등록 — 버전 불일치 또는 대시보드 컨텍스트 필요; 전체 쿼리 텍스트와 id는 `/tmp` 탐색 기록에 저장됨,
필요 시 text 직접 전송 또는 온라인 bundle에서 재추출 가능).

<a id="注意事项" data-pplx-source-anchor="true"></a>
### 주의 사항
- 웹 공간 페이지/홈 페이지에서는 graphql 호출이 보이지 않음 (모두 /rest 사용); graphql은 /library 목록과 Computer 대시보드에 사용됨이 확인됨.
- sha256 해시는 프론트엔드 버전에 따라 변경될 수 있음; 실패 시 `PERSISTED_QUERY_NOT_FOUND`로 나타남 — 이 경우 브라우저
  네트워크 캡처에서 재추출 (WebBridge `network` 도구로 `perplexity_ask/graphql` 필터링)하거나 온라인 bundle에서 재추출 ([§7](api-discovery-roadmap.md) 참조).

<a id="已提取的仪表盘-connection-keysrelay-缓存键调试用" data-pplx-source-anchor="true"></a>
### 추출된 대시보드 connection keys (Relay 캐시 키, 디버깅용)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
