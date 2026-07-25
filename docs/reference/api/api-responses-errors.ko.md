---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-responses-errors.zh-CN.md"
translation_source_sha256: "cc96e525443d1f8445d81a3997cc8f26178730ef0541a33d0774f40c3fe70b89"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-响应结构与错误语义" data-pplx-source-anchor="true"></a>
# API 응답 구조와 오류 의미

*이 문서는 Perplexity Web API 참조의 일부입니다. 전체 개요는 [API 색인](index.md)을 참조하세요.*

<a id="响应结构要点解析纪律" data-pplx-source-anchor="true"></a>
## 응답 구조 핵심 (파싱 규칙)

- **성공 아카이브는 원본 데이터를 보존**: `raw_entries.json`(plain)과
  `raw_blocks.json`(schematized, 실제 수집 시)는 렌더링 결과물과 함께 저장되며,
  파싱/렌더링은 오프라인에서 재실행 가능(`pplx-export re-render`), 재수집하지 않음.
- **필드 추출 집중**: `sites/perplexity/parsers.py`(스키마 변경 시 한 곳만 수정).
- 모드 식별(`normalize.detect_mode`, 의사결정 트리는 [export-pipeline.md](../../architecture/export-pipeline.md) 참조): 최우선 신호는
  각 entry의 **`search_mode`** 필드(매핑은 [§3.9](api-rest-endpoints.md) 말미 참조); 모두 없을 경우 폴백——computer = URL
  `/computer/tasks/` 또는 metadata.mode=="4" 또는 인덱스 mode∈{ASI,COMPUTER}; council = COUNCIL_RESEARCH
  단계 존재; deep-research = RESEARCH_ANSWER 단계 존재(내용 기준, 한국어 레이블 불필요);
  나머지는 search.
- computer의 UI는 모두 접혀 있음——**항상 API의 entries/blocks를 기준으로 하며**, UI 텍스트를 내용 경계로 사용하지 않음.
- 하위 에이전트 이중 채널(2026-07-19 확인): 프롬프트는 schematized `workflow_payload.objective_chunks`;
  단계/결론은 plain `background_entries`; `workflow_payload.id`(`toolu_X`)을 통해 연결.
- `WORKFLOW_ITEM_SOURCES` 항목은 `sources_payload.sources`(링크 목록) 외에도 `text_payload`
  (하위 에이전트의 페이지 추출 본문/비교표, 전체 데이터베이스 측정 450건 중 408건이 background 중첩 페이로드 내에 있음)를
  자주 포함; 동일한 내용이 plain 백그라운드 entry의 `text` 내장 단계 JSON과 schematized 중첩 페이로드에 동시에 나타남——
  하위 에이전트를 plain 경로로 렌더링하면 본문이 이미 보존됨(2026-07-22 전체 데이터베이스 확인 408/408 누락 없음).
- **`related_queries` / `related_query_items`(2026-07-23 확정)**: 각 entry가 포함하는
  **다음 질문 프롬프트 추천**——플랫폼이 완료된 답변에 대한 후속 질문 제안; `related_queries`는 추천 텍스트 배열,
  `related_query_items`는 구조화된 항목(uuid/upsell_type 등 포함). 증거 결론: item의 uuid는
  **스레드 uuid가 아님**(전체 데이터베이스 스레드 uuid와 교차 0/988), 추천 텍스트는 다른 스레드 query와 전혀 중복되지 않음——
  **현재로서는 스레드 간 관계로 해석할 수 없음**; "사전 할당된 스레드 uuid(클릭 시 구체화)"라는 검증되지 않은 가설이 존재.
  데이터는 아카이브 `raw_entries.json`(일부 아카이브 데이터베이스의 과반 스레드에서 발견)에 자연스럽게 보존되며, 추가 수집 작업 불필요;
  relations 그래프는 이를 위해 엣지를 생성하지 않음.

<a id="错误与风控语义" data-pplx-source-anchor="true"></a>
## 오류 및 위험 관리 의미

| 현상 | 의미/처리 |
|---|---|
| 403(cf 챌린지 페이지 포함) | Cloudflare 차단(TLS 지문/빈도 제어)——백오프; urllib+브라우저 쿠키는 일반적으로 트리거되지 않음 |
| 401 / API 계층 403(cf 챌린지 페이지 없음) | 세션 쿠키 만료/무효——도구가 즉시 예외 발생, 백오프 없음; 배치에서 연속 3회 인증 실패 시 fail-fast(쿠키 업데이트 필요) |
| 429 | 빈도 제어——지수 백오프(도구에 이미 구현됨) |
| 5xx(500/502/503/504) | 서버 일시적 오류(504는 Cloudflare 시간 초과에서 흔함)——백오프 재시도(도구에 이미 구현됨) |
| ENTRY_EXPIRED | 플랫폼이 제거함(약 3개월)——최종 상태, 재시도하지 않음 |
| ENTRY_DELETED | 사용자/원격에서 삭제됨(HTTP 400이지만 code 다름)——최종 상태 `deleted`, 재시도하지 않음 |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED`(HTTP 200) | 현재 계정에 해당 스페이스 조회 권한 없음——볼 수 있는 계정으로 전환하여 재시도 |
| `error_code: VIEW_THREAD_NOT_ALLOWED`(HTTP 403) | 현재 계정에 해당 스레드 조회 권한 없음(2026-07-23 실제 측정: sibling 변형 uuid 탐지; 객체는 존재하지만 접근 불가, "존재하지 않음"이 아님) |
| `status:"failed"` 빈 데이터 | 위와 동일(get_collection의 실패 형태) |

**속도 제한 규칙(계정 차단 방지, 사용자 명시적 요청)**: 배치 스레드 간 10–20초 랜덤, 동시성 없음, 429/403 백오프, 5xx 백오프 재시도;
페이지네이션 ≥3초; schematized 보충 수집 ≥4초; 스페이스 메타데이터 수집 ≥3초. 단일 스레드 내보내기 = 1–2 요청 ≈ 페이지 한 번 열기.

<a id="中断语义实测取值2026-07-22分类真源-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### 중단 의미 실제 측정값(2026-07-22, 분류 진실 출처 `parsers.classify_wf_status`)

`locked_reason` 필드: `thread_metadata` / `entries[]` / `background_entries[]`에 나타남
(plain과 schematized 양쪽 모두). 실제 측정된 유일한 값:

| locked_reason | 의미 | 실제 분포 |
|---|---|---|
| `spending_limit_exceeded` | 할당량 중단(할당량 소진, 워크플로가 중단 지점에서 멈춤) | 전체 아카이브에서 정확히 1개 스레드(raw_entries와 raw_blocks 양쪽에 표시됨) |

workflow 상태 필드(`workflow_block.status`와 중첩 `workflow_payload.status`는 동일한 열거형) 실제 측정값:

| status | 의미 | 렌더링 표시(COMPLETED는 표시하지 않음) |
|---|---|---|
| `WORKFLOW_COMPLETED` | 정상 완료 | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | 다음 단계 대기 중; `locked_reason=spending_limit_exceeded`와 함께 나타나면 **할당량 중단**(내용은 중단 지점까지), locked_reason 없으면 중단 후 대기 중 | `⏸ 限额中断（内容截至中断点）` / `⏸ 中断待续` |
| `WORKFLOW_CANCELED` | 취소됨(사용자/플랫폼 중단) | `⛔ 已取消` |

- `WORKFLOW_CANCELED` 실제 측정 19건(16개 메인 + 3개 중첩), 7개 computer 스레드에 분포
  (a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff).
- 참고: 메인 entry 앵커 페이로드의 status는 지연될 수 있음(실제 측정에서 앵커는 COMPLETED이지만 백그라운드는 실제로 CANCELED)——
  하위 에이전트의 실제 상태는 백그라운드 측 `workflow_block.status`를 기준으로 함.
- 중단된 백그라운드 작업은 subagent_result 완료 알림을 생성하지 않음; 소비되지 않은 백그라운드 페이로드는 스레드 부록에서 처리
  ([subagents-interruptions.md](../../architecture/subagents-interruptions.md)의 "소속 폭포" 참조).
- computer 모드 빈 답변(2026-07 이중 확인, 복구 불가능): computer 모드에서 일부 턴의 답변이 비어 있음,
  서버에 원래 답변이 없기 때문——API 재수집 데이터는 아카이브와 완전히 일치하며, UI에서
  "N 단계 완료" 접힌 막대를 펼치면 데이터 요청이 전혀 발생하지 않음(순수 클라이언트 측 렌더링, UI와 API 동일 출처), API로 복구 불가능.
  이러한 빈 답변 턴 중 일부만 `locked_reason=spending_limit_exceeded`와 관련되어 있으며, 나머지는 서버에 원인 표시가 전혀 없음.

<a id="side_by_side_metadata答案重写变体信号2026-07-23-定案" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata`: 답변 재작성 변형 신호(2026-07-23 확정)

필드 경로: `entries[].side_by_side_metadata`(plain `/rest/thread/<uuid>` 응답).
플랫폼이 동일한 query에 대해 여러 버전의 답변을 생성(A/B 실험 또는 재작성)할 때, 현재 유효한 entry에 남는
유일한 흔적——**대체된 변형 본체(텍스트/단계/인용)는 스레드 API 응답에 포함되지 않음**(실제 예
b2d2632b: 응답에 1개의 entry, 1개의 FINAL만 있으며, 변형 2는 완전히 보이지 않음).

관찰된 키와 값(b2d2632b raw 증거, 전체 데이터베이스 2442개 entry 스캔):

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| 키 | 의미(관찰/가설) |
|---|---|
| `sibling_uuid` | 동일 query의 **형제 답변 변형**(다른 버전의 entry/context 식별자)을 가리킴. 전체 데이터베이스 7개 스레드에서 발견; **온라인 증거 수집(2026-07-23)에서 데드 링크로 확인**: 두 계정 `GET /rest/thread/<sibling_uuid>` 모두 403 `VIEW_THREAD_NOT_ALLOWED`(404/ENTRY_EXPIRED 아님——서버가 존재하지만 조회 권한이 없는 객체로 인식), 브라우저(소유자 계정)에서 `/search/<sibling_uuid>` 열면 SPA가 홈페이지로 리디렉션——대체된 변형은 sibling_uuid로 복구 불가능 |
| `selection_status` | `SELECTED` = 이 entry의 답변이 선택되어 표시된 버전임; 대조군 인스턴스는 모두 `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | 실험 역할. 대조군은 `[control]` 접두사 포함(전체 데이터베이스 6건: `[control]default-model-class:gpt41` 등); 실제 예는 접두사 없음(`override-default-model-class:qwen3_instruct-01f7f`, 즉 모델 커버리지 실험의 실험군) |
| `experiment_override` | 실험 커버리지 매개변수(예: `override-default-model-class: qwen3_instruct`); 실험군 인스턴스에서만 관찰됨 |
| `execution_log` | 관찰값은 빈 객체, 의미 불명 |

**좁힌 판단 기준**("실제 재작성 및 이중 버전 보존"과 "일반 A/B 대조" 구분):
`sibling_uuid`가 비어 있지 않음 그리고 (`selection_status`가 비어 있지 않고 `SELECTION_STATUS_UNSPECIFIED`가 아님,
또는 `experiment_role`에 `[control]` 접두사가 없음) → 전체 데이터베이스 2442개 entry 중 **b2d2632b 하나만 적중**
(확인된 유일한 실제 예; 본 데이터베이스에서 precision/recall 모두 1, 표본 크기 1로 일반화 보장 불가).

도구 동작: `parsers.collect_answer_variants`가 적중 항목을 추출하고, `adapter.get_thread`가
log.warning 경고 + `thread.json.answer_variants`에 기록(적중 없으면 해당 키 나타나지 않음);
`re-render --thread-json`는 제자리에서 추가/삭제(멱등성). 시간 증거: 실제 예 entry `created→updated`
차이 53.66초(17:13에 생성 후 재작성/선택), 재작성이 스레드 수준 `lastUpdated`을 촉발(증분 재유도가
재수집을 트리거할 수 있지만, 재수집된 응답에는 여전히 현재 유효한 답변만 포함되며 이전 변형은 복구 불가능).

**감지 로그 및 처리 절차(2026-07-23, `sites/perplexity/variant_log.py`)**:

- **로그 표시**: 적중 시 WARNING 수준 단일 행, 통일된 grep 가능 표시 `ANSWER_VARIANT_DETECTED`,
  모든 위치 지정 필드와 처리 지침 포함, 형식:
  `ANSWER_VARIANT_DETECTED thread=<全量uuid> uuid8=<8位> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | 处置：…`
  온라인 경로(`adapter.get_thread`)는 실제 수집 시 적중할 때마다 출력; 오프라인 `re-render`는
  **등록된 내용이 새로 추가/변경된 경우에만** 출력(멱등성 재실행 시 화면 넘치지 않음); `batch` 말미 요약에
  적중 횟수 알림을 한 행 더 출력(기존 요약 형식 유지).
- **중앙 등록소**: `<out>/index/answer_variants_log.jsonl`(**저장소 파일**,
  gitignore의 `logs/` 아래에 있지 않음)——한 줄에 하나의 JSON(detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role), (web_uuid, entry_uuid) 기준으로 중복 제거, 반복 내보내기/재렌더링 시 무한 추가되지 않으며,
  detected_at은 첫 발견 시간 유지.
- **적중 후 권장 조치**: sibling은 실제로 대부분 데드 링크로 확인됨(위 표 참조), 대체 답변은 일반적으로 **API를 통해 복구 불가능**——
  가능한 한 빨리 대체 답변을 여전히 얻을 수 있는지 수동 확인(플랫폼 세션 측/사용자 기억/스크린샷), 얻을 수 있으면
  스레드 디렉토리 아래 `rewritten_answer_variant.md`와 동일한 형식의 수동 파일로 추가 기록; 얻을 수 없으면 `thread.json.answer_variants` +
  jsonl 등록을 최종 추적 가능 흔적으로 남김.
