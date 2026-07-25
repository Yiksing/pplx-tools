---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-discovery-roadmap.zh-CN.md"
translation_source_sha256: "d2ef3b082d6320ba6a0ba74a978305c5c362c8fa56c8ee0dbf357470df97cebd"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="端点发现方法与改进路线图" data-pplx-source-anchor="true"></a>
# 엔드포인트 발견 방법 및 개선 로드맵

*이 문서는 Perplexity Web API 참조의 일부입니다. 전체 개요는 [API 색인](index.md)을 참조하세요.*

<a id="已知未探索待确认项" data-pplx-source-anchor="true"></a>
## 알려진 미탐색/확인 필요 항목

- `list_collection_threads`의 정렬 필드와 `total_threads`의 정확한 의미
  (2026-07 실시간 계정 스냅샷: 보고 99개 vs 최상위 27개 항목).
- `threadAccess`/`access`/`user_permission` 값의 전체 스펙트럼 (2026-07 관측 샘플:
  threadAccess 5 일반, 1 🔒 포함; collection access 1; permission 4 소유자 /
  2 편집 가능; assets data에도 thread_access 포함).
- `list_ask_threads`, `list_scheduled_computer_tasks`의 올바른 매개변수 형태 (직접 GET 400).
- `collections/*/request-access-info`, `spaces/<uuid>/recurring_tasks`, `assets/<id>/members` 응답 구조.
- 대시보드 GraphQL 작업이 등록되지 않은 이유 (PERSISTED_QUERY_NOT_FOUND): 버전 불일치 또는 컨텍스트 임계값,
  필요 시 온라인 네트워크 캡처의 실시간 해시를 기준으로 다시 추출.
- `frontend_uuid` vs `uuid` vs `context_uuid` 세 가지의 computer 스레드 내 역할 구분.
- 계정 간 공간 공유 분기 스레드(branch_of)의 API 신호 필드 (부모 스레드 포인터/분기 표시) —
  메커니즘 확인됨 ([§3.3](api-rest-endpoints.md) 말미), 2026-07-23 기준 아카이브 사례 없음,
  첫 사례 발생 시 검증 기록 대기.

<a id="端点发现方法前端-bundle-静态分析零-api-成本2026-07-20-建立" data-pplx-source-anchor="true"></a>
## 엔드포인트 발견 방법: 프론트엔드 번들 정적 분석 (API 비용 제로, 2026-07-20 구축)

한 번에 **147개 `/rest/` 엔드포인트** 발견, 방법 재사용 가능 (프론트엔드 개편 후 재실행):

1. 페이지 로드 진입점 `_spa/assets/index.html-*.js`이 `bootstrap-*.js` 참조 (런타임에 모든 청크 매핑 포함);
2. bootstrap에서 682개 청크 파일명 추출 (패턴 `<name>-<hash8>.js`), 이름으로 API 관련 필터링
   (client/api/thread/collection/space/computer…);
3. 공용 CDN `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`에서 직접 다운로드
   (쿠키 불필요); 핵심 모듈: `platform-core-*`(API client), `spa-shell-*`, `spa-metadata-*`;
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'`에서 엔드포인트 목록 획득 (147개);
5. 청크는 동시에 호출 형태 노출 (예: export의 `format:'md'`와 `file_content_64`).
6. 추가로 sourcemap: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (심층 분석 안 함).

<a id="附录147-个端点按类分组与归档相关性标注" data-pplx-source-anchor="true"></a>
### 부록: 147개 엔드포인트를 클래스별 그룹화 (아카이브 관련성 표시)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`, `/rest/thread/export`★, `/rest/thread/{uuid}/members`,
  `/rest/thread/list_recent`, `/rest/thread/list_ask_threads`, `/rest/thread/list_pinned_ask_threads`,
  `/rest/thread/list_scheduled_computer_tasks`, `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★: [§3.3](api-rest-endpoints.md) 전체 표 참조 (batch_move/batch_remove, list_user_collections, request-access-info,
  recurring_tasks, pins/threads, scheduled_threads 포함)
- **assets**★: `/rest/assets/{asset_id}/data`, `/rest/assets/{asset_id}/members`,
  `/rest/assets/{asset_id}/published-access`, `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`, `/rest/analytics/computer/usage/members`
  (모두 403 NOT_ORG_MEMBER — 조직 계정 전용)
- **models/skills**: `/rest/models/config(/v2)`, `/rest/skills`, `/rest/skills/selectable`,
  `/rest/skills/grants`, `/rest/skills/submissions(/source)`
- **files/uploads**: `/rest/file-repository/*` (list/download/get-file-upload-urls/delete-files…),
  `/rest/files/list(/list-infinite/list-errors)`, `/rest/uploads/(batch_)create_upload_url(s)`,
  `/rest/connectors/attachments/upload`
- **tasks/computer**: `/rest/tasks/`, `/rest/tasks/{task_id}`, `/rest/tasks/shortcuts/mentions`,
  `/rest/tasks/shortcuts/paste/{copy_token}`, `/rest/computer/asset`, `/rest/computer/menu`,
  `/rest/computer/onboarding_cards`
- **user/auth**: `/rest/user/settings`, `/rest/user/get_user_ai_profile`, `/rest/user/promotions`,
  `/rest/user/site-instructions`, `/rest/auth/get_special_profile`, `/rest/visitor/*`
- **billing/stripe**: `/rest/billing/*` (credits/paypal/subscription…), `/rest/stripe/*`
- **enterprise/org**: `/rest/enterprise/*`, `/rest/organizations/{id}/credit-limits*`,
  `/rest/pplx-api/v2/enterprise-api-org`
- **sse**: `/rest/sse/attachment_processing/subscribe`, `/rest/sse/index_files`,
  `/rest/sse/perplexity_terminate`, `/rest/sse/related-queries/{entry_uuid}`
- **verticals** (아카이브와 무관): `/rest/finance/*`, `/rest/sports/*`, `/rest/travel/hotels/{slug}`,
  `/rest/health-assistant/*`, `/rest/article/{uuid_or_slug}`
- **misc**: `/rest/pins`, `/rest/rate-limit/(all|status)`, `/rest/notifications/web-push/*`,
  `/rest/attribution/*`, `/rest/homepage-widgets/upsell`, `/rest/ntp/upsell/`, `/rest/sidebar/upsell/`,
  `/rest/incentives/comet-activation`, `/rest/connector-service/usage`

(★ = 아카이브와 직접 관련)

<a id="端点-工具能力状态与路线图" data-pplx-source-anchor="true"></a>
## 엔드포인트 → 도구 기능 상태 및 로드맵

아래 표의 구현 상태는 **2026-07-24** 기준 현재 코드 및 테스트 스위트와 동기화되었습니다. API 증거는 기존
실시간 관측 또는 정적 분석의 날짜와 범위를 따릅니다. 이번 문서 동기화는 비공개 엔드포인트를 다시 탐지하지 않았습니다. 계정/아카이브 수는
모두 스냅샷이며, 플랫폼 전체의 일정한 보장이 아닙니다.

상태 의미:

- **구현 완료** — 현재 CLI 또는 프로덕션 경로가 표에 설명된 기능에 엔드포인트를 사용합니다.
- **부분 구현** — 엔드포인트가 이미 사용 중이지만, 로드맵의 다운스트림 기능이 아직 완료되지 않았습니다.
- **실측 완료, 미통합** — 온라인 API 동작이 관측되었지만, 도구에 소비 경로가 없습니다.
- **계획 중** — 증거는 있지만, 구현이 아직 시작되지 않았습니다.
- **차단됨** — 명확한 상위 또는 프로토콜 차단이 존재합니다.
- **종료됨** — 증거가 원래 용도를 부정했거나, 해당 용도가 범위 밖으로 결정되었습니다.

<a id="能力状态矩阵" data-pplx-source-anchor="true"></a>
### 기능 상태 매트릭스

| 엔드포인트 / 작업 | 검증 근거 | 현재 통합 | 상태 | 남은 격차 |
|---|---|---|---|---|
| `collections/get_collection` | 실시간 관측 + 현재 코드 | `spaces --fetch-meta` 공간 소유자/멤버 인덱스 구축 | **구현 완료** | — |
| `collections/list_collection_threads` | 실시간 관측 + 현재 코드 | `space-index` 기본 REST, context_uuid 이중 ID 매핑 포함; WebBridge는 대체 | **구현 완료** | 정렬과 `total_threads` 정확한 의미 확인 필요 |
| `assets/<uuid>/data` | 2026-07-20 온라인 실측 + 현재 코드 | `assets-backfill --online` 실제 asset UUID에 대한 서명 URL 갱신 | **구현 완료** | 이 엔드포인트는 `toolu_` 클라우드 작업 공간 핸들을 포함하지 않음 |
| `LibraryThreadsRelayQuery` 및 페이지네이션 쿼리 | APQ 캡처 + 현재 코드 | `index`/`batch` 전체 인덱스 및 증분 조기 중단 제공 | **구현 완료** | 대시보드 패턴별 쿼리는 별도로 차단됨 |
| `collections/list_user_collections` | 2026-07 온라인 관측 + 현재 코드 | `init` 제목 정확 일치 및 BOT 공간 발견 | **부분 구현** | 계정 수준 권위 공간 레지스트리 구축, 새 공간 발견 및 `spaces` 재구축용 |
| `credits/thread-usage` | 2026-07-20 온라인 실측 + 현재 코드 | `usage-backfill` `index/credit_usage_<account>.json`에 쓰기 | **부분 구현** | 이중 진실 공급원을 만들지 않고 `thread.json` 및/또는 library 인덱스 행을 풍부화할지 결정 |
| `models/config/v2` | 2026-07-21 온라인 실측 + 현재 코드 | `pplx-ask models` 모델/기본값 나열; 정규화 상수는 이를 기준으로 교차 검증 | **부분 구현** | 가치가 있다면 안정적인 모델 표시 메타데이터를 아카이브/인덱스에 기록 |
| `POST /rest/thread/export` | 2026-07-20 md/pdf/docx 실측 완료 | CLI 통합 없음 | **실측 완료, 미통합** | 다중 형식 아카이브 및 공식 Markdown 대조 |
| `rate-limit/status` | 페이지 로드 관측; 응답 의미 미탐색 | 없음 | **계획 중** | 적응형 속도 제한에 사용 전 의미 검증 |
| `file-repository/list-files` | 프론트엔드 정적 분석만 | 없음 | **계획 중** | `toolu_` 핸들 열거/복구 가능 여부 검증; 2026-07 아카이브 스냅샷은 다운로드 채널 없는 270개 핸들 기록 |
| `pins`, `tasks/{id}` | 프론트엔드 정적 분석 / 페이지 로드 관측 | 없음 | **계획 중** | 고정 상태 및 computer 작업 시간 풍부화 |
| `thread/<uuid>/members` | 2026-07 온라인 실측 | 없음 | **계획 중** | relations 그래프에 스레드 수준 공유 관계 제공 |
| 대시보드 GraphQL `threadGroup` + 패턴 필터 | 직접 호출 시 `PERSISTED_QUERY_NOT_FOUND` 반환 | 없음 | **차단됨** | 실시간 persisted-query 해시 복구 또는 필요한 컨텍스트 확인 |
| `related_queries` / `sse/related-queries` | 2026-07-23 전체 데이터베이스 포렌식 확정 | 관계 엣지 생성 안 함 명확히 | **종료됨** | 해석 가능한 스레드 ID를 설정할 수 있는 새로운 증거가 있을 때만 재개 |

<a id="活跃路线" data-pplx-source-anchor="true"></a>
### 활성 경로

<a id="p0官方导出集成" data-pplx-source-anchor="true"></a>
#### P0 — 공식 내보내기 통합

- **다중 형식 아카이브**: 선택적으로 `POST /rest/thread/export`가 반환하는 PDF/DOCX 산출물 보존.
- **렌더러 대조**: 공식 전체 스레드 Markdown을 `conversation.md`과 비교하여 독립적인 회귀 신호로 사용.

<a id="p1空间发现" data-pplx-source-anchor="true"></a>
#### P1 — 공간 발견

- `list_user_collections`을 BOT 제목 조회에서 계정 수준 권위 공간 레지스트리로 승격,
  새 공간 발견 및 `spaces` 재구축에 사용.

<a id="p2元数据风控与资产救援" data-pplx-source-anchor="true"></a>
#### P2 — 메타데이터, 위험 관리 및 자산 복구

- 크레딧 사용량의 진실 공급원 경계 명확화: 전용 `credit_usage_<account>.json`만 유지할지, 아니면
  `thread.json` / library 인덱스 행도 함께 풍부화할지.
- 엔드포인트 의미가 안정화될 때만 모델 표시 메타데이터, 고정 상태, computer 작업 시간 및 스레드 공유 관계 추가.
- 적응형 속도 제한 설계 전 `rate-limit/status` 검증.
- `file-repository/list-files`가 `toolu_` 복구 경로로 사용 가능한지 먼저 검증한 후,
  아카이브 쓰기 작업 추가.

<a id="p3受阻的发现能力" data-pplx-source-anchor="true"></a>
#### P3 — 차단된 발견 기능

- 패턴별 증분 인덱싱의 가치가 유지 관리 비용을 상쇄할 때만 대시보드 GraphQL의
  persisted-query 해시 재캡처.

<a id="已关闭决定-不采用" data-pplx-source-anchor="true"></a>
### 종료된 결정 / 채택되지 않음

- **공식 export 엔드포인트를 사용한 보고서 본문 획득**: 반증됨. 해당 엔드포인트는 전체 스레드 Markdown을 반환하며,
  보고서 본문을 포함하지 않음; 서명 URL 체인이 여전히 `report.md`의 공식 출처
  ([§3.6](api-rest-endpoints.md)).
- **`related_queries`로 관계 엣지 구축**: 2026-07-23 반증됨. item UUID는 스레드 UUID가 아니며,
  추천 텍스트도 아카이브 쿼리로 해석 불가; 관계 엣지 구축 안 함 ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: 테스트 계정에서 조직 전용 관측
  (`403 NOT_ORG_MEMBER`).
- `thread/request-access-info`: 실측 결과 조직 가입 관련이며, `threadAccess` 신호가 아님.
- billing/Stripe/enterprise 및 finance/sports 등 수직 분야는 아카이브 도구 범위 밖.

---

*이 문서는 [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md)(도구 아키텍처), [overview.md](../../architecture/overview.md)(시스템 설계)와 상호 보완적입니다.*
