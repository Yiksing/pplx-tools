---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/modes.zh-CN.md"
translation_source_sha256: "902b8570a856deeeb385f0d0babe3d22af5388a78c1cb546c595ece011aacade"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="会话模式" data-pplx-source-anchor="true"></a>
# 대화 모드

Perplexity 대화에는 다섯 가지 모드가 있습니다: `search` / `deep-research` / `computer` / `council` / `study`.
내보내기 시 스레드별로 모드를 판정하며, 이는 어떤 API 응답을 가져올지, 스레드 디렉터리에 무엇을 넣을지, 그리고 스레드가
어느 [보관 경로](archive-layout.md)로 들어갈지 결정합니다 (`<账户>/<模式>/…`). 판정 결과는
`thread.json` (`mode` 키)에 기록되며, `pplx-export batch --mode` 필터링에 사용됩니다. `pplx-ask`는
또한 다섯 가지 모드 중 네 가지 (`computer` 제외)로 새 스레드를 **생성**할 수 있습니다 — [pplx-ask](pplx-ask.md) 참조.

<a id="五种模式一览" data-pplx-source-anchor="true"></a>
## 다섯 가지 모드 개요

| 모드 | UI 이름 / 모델 | 라운드 내용 | 인용 | 산출물 | schematized blocks 가져오기 |
|---|---|---|---|---|---|
| `search` | "Best" (`pplx_pro`; labs의 `STUDIO`/`pplx_beta`도 여기에 포함) | 질문 + 답변, 텍스트 단계 | 라운드 수준 + 전체 스레드 `sources.*` | — | 아니오 (`raw_blocks.json` 없음) |
| `deep-research` | "Deep research" (`pplx_alpha`, 고정 선택 불가) | 연구 단계, `RESEARCH_ANSWER` 포함 | 있음 | `report.md` (전체 보고서) | 예 |
| `computer` | Computer (`pplx_asi_opus`, `pplx_asi_opus_thinking`) | 전체 `workflow_block`: 나레이션, 도구 호출, 하위 에이전트 프롬프트/단계, 단계별 인용 | 단계별 + 라운드 + 전체 스레드 | `assets/` 다중 버전 파일 + 하위 에이전트 실행 | 예 |
| `council` | 모델 위원회 (`pplx_agentic_research`; 기본 세 모델) | `COUNCIL_RESEARCH` 단계; 각 모델 중첩 `LLM_COUNCIL` 워크플로가 `<details>`으로 접힘 (검색 라운드, 모든 출처, 전체 단일 모델 답변) | 단일 모델 + 집계 | 여러 모델 답변 나란히 비교 | 예 |
| `study` | Study (`pplx_study`) | 블록을 통해 단계/인용 제공 (실제로는 자산도 포함) | 있음 | 존재 시 자산 | 예 |

<a id="模式如何判定" data-pplx-source-anchor="true"></a>
## 모드 판정 방법

판정 기준은 플랫폼 자체 필드 **`entry.search_mode`** (`SEARCH_MODE_MAP`,
`normalize.py:50-59`)이며, 모든 항목을 순회하여 수집합니다 (`normalize.py:106-115`).
공식 모델 구성 (`GET /rest/models/config/v2`)에 대해 검증 완료:
`default_models.search=pplx_pro` (UI "Best"), `default_models.research=pplx_alpha`
(UI "Deep research") 값은 대화 모드와 일대일로 대응됩니다:

| `search_mode` 값 | 모드 |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`, `STUDIO` | `search` |

충돌 규칙 (`detect_mode`, `normalize.py:66-128`):

- **스레드 내 모드 전환** (항목 불일치): 특이성에 따라 가장 높은 값을 취함 —
  **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`,
  `normalize.py:63`) — 그리고 `log.warning`.
- **하위 신호와 충돌** (단계 이름 / `display_model`): `search_mode`이 우선하며,
  `log.warning` (`normalize.py:120-123`).
- **`search_mode` 완전히 누락** → 원래 체인 사용: URL에 `/computer/tasks/` 또는
  `metadata.mode == '4'` 포함 또는 인덱스 mode ∈ `ASI`/`COMPUTER` → `computer`; 존재
  `COUNCIL_RESEARCH` 단계 → `council`; 존재 `RESEARCH_ANSWER` 단계 → `deep-research`;
  중복 신호 `display_model` (`DISPLAY_MODEL_MODE`, `normalize.py:32-37`) 충돌 시 우선;
  모두 미해당 → 기본값 `search`.
- **신호가 전혀 없어도 search로 확정하지 않음**: 파이프라인은 여전히 schematized blocks를 가져오며
  (`adapter.py:83-89`), 플랫폼 필드 변경으로 `raw_blocks.json`이 조용히 손실되지 않습니다.

!!! note "`pplx_alpha`이 판정 기준이 아닌 이유"
    `pplx_alpha`은 RESEARCH 전용 모델입니다 — 이 분류기가 판정하려는 **대상**이지 판정 증거가 아니므로,
    매핑 테이블에서 의도적으로 제외되었습니다 (`normalize.py:15-31` 주석).

모든 분기를 포함한 전체 의사 결정 트리: [내보내기 파이프라인 — 모드 판정](../architecture/export-pipeline.md).

<a id="子代理负载的落点" data-pplx-source-anchor="true"></a>
## 하위 에이전트 페이로드 배치

computer/council 실행은 백그라운드 하위 에이전트 워크플로를 생성합니다. 각 백그라운드 `workflow_payload`은
**정확히 한 곳에 배치되며, 두 번 렌더링되지 않습니다**; 사용자 수준의 세 가지 가능한 배치:

1. **앵커 — 시작 라운드에 포함**: 하위 에이전트를 시작한 라운드가 동일한 payload id를 가지므로, 해당 실행이 이
   라운드의 작업 과정에 인라인 렌더링됩니다 (`turns/turn_NNNN.md`), 프롬프트, 단계, 답변 및 출처 포함.
2. **stub 라운드 — "하위 에이전트 작업" 섹션**: 10초 완료 창 내의 `subagent_result` stub 라운드가
   해당 페이로드를 흡수합니다; 답변은 다시 채워지지 않습니다.
3. **스레드 부록 — `conversation.md` 끝**: 나머지 모든 페이로드 (중단된 실행은 완료 알림이 없으며, 처음 두 단계는
   반드시 누락됨)는 "## 백그라운드 작업 (라운드에 속하지 않음)" 아래에 그대로 보관됩니다 — 시간 추정 없이,
   모든 상태를 수용합니다.

일치 규칙, 데이터 구조 및 단일 소비 보장:
[하위 에이전트 및 중단](../architecture/subagents-interruptions.md).

<a id="中断非-completed-工作流" data-pplx-source-anchor="true"></a>
## 중단: COMPLETED가 아닌 워크플로

완료되지 않은 워크플로는 렌더링 위치에 인라인으로 표시됩니다 — 작업 과정 제목, 하위 에이전트 제목 및 중첩된 `<details>`
요약. 세 가지 표시 (`parsers.classify_wf_status`, `parsers.py:263-284`):

| 표시 | 조건 | 의미 |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | 할당량 소진, 워크플로 중간에 중단 |
| `⏸ 中断待续` | `WORKFLOW_AWAITING_NEXT_STEPS` 및 `locked_reason` 없음 | 중단됨, 플랫폼에서 계속 가능 |
| `⛔ 已取消` | `WORKFLOW_CANCELED` | 사용자 또는 플랫폼에 의해 취소됨 |

- `COMPLETED`는 절대 표시되지 않음 (정상 스레드는 차이 없음); 알 수 없는 미래 상태 값은 조용히 유지.
- 각 표시된 경우는 동시에 `thread.json.interruptions`에 등록되며, 형식은
  `{location, kind, headline, status}` — 위치는 `turn_0007`,
  `turn_0011/subagent`, `turn_0024/subagent_stub`, `background_unassigned` 형식
  (`parsers.py:535-583`; 정상 스레드에는 이 키가 나타나지 않음).
- **재개는 특별 사례가 필요 없음**: 플랫폼에서 중단된 스레드를 계속하면, 해당 `lastUpdated`이 변경되고, 다음 증분
  내보내기에서 다시 가져오며, 워크플로가 완료되면 표시가 자연스럽게 사라집니다. [증분 동기화](incremental-sync.md) 참조.

실제 상태 값 및 분포: [API 응답 및 오류](../reference/api/api-responses-errors.md);
상태 머신: [하위 에이전트 및 중단](../architecture/subagents-interruptions.md).

<a id="答案重写变体answer_variants" data-pplx-source-anchor="true"></a>
## 답변 재작성 변형 (answer_variants)

플랫폼이 답변을 재작성 (A/B 실험)할 때, 대체된 변형은 API 측에서 보이지 않습니다 — 선택된 답변만 반환되며,
선택되지 않은 형제 버전은 `entries[].side_by_side_metadata`에만 흔적을 남기며, 이후 플랫폼에 의해 제거될 수 있습니다
(죽은 링크 확인됨: 403 `VIEW_THREAD_NOT_ALLOWED`). 도구는 "재작성이 발생했음"을 관찰 가능하게 만듭니다:

- **등록**: 좁은 판정 기준이 적중하면 `thread.json.answer_variants`에 기록 (`fs_writer.py:247-252`;
  적중 없으면 키가 나타나지 않음), 중앙 등록소 `index/answer_variants_log.jsonl`에 추가,
  (스레드, 항목)별로 중복 제거, 멱등성 (`variant_log.py:76`).
- **경고**: 각 온라인 적중 시 grep 가능한 단일 행 WARNING `ANSWER_VARIANT_DETECTED` 출력,
  전체 위치 필드 포함 (스레드 uuid/uuid8, entry_uuid, sibling_uuid, selection_status,
  experiment_role); `re-render` 오프라인 재등록, 내용이 새롭거나 변경된 경우에만 경고,
  전체 데이터베이스 재실행 시 화면 넘치지 않음; 배치 요약에 ⚠ 적중 수 추가.
- **수동 보완 보관**: 형제 변형은 실제로 죽은 링크이며, 대체 답변은 일반적으로 **API를 통해 복구할 수 없음**. 적중 후 가능한 한 빨리
  수동으로 대체 답변 확인 (플랫폼 인터페이스, 자신의 기록, 스크린샷); 획득하면 스레드 디렉터리 내
  `rewritten_answer_variant.md`로 기록; 획득하지 못하면, `thread.json.answer_variants`에 jsonl
  등록소가 최종 추적 가능한 기록입니다.

감지 체인 및 오프라인 재등록: [오프라인 작업](../architecture/offline-operations.md); 필드 의미 및
죽은 링크 증거: [API 응답 및 오류](../reference/api/api-responses-errors.md).

<a id="渲染保真原则" data-pplx-source-anchor="true"></a>
## 렌더링 충실도 원칙

어떤 모드든 렌더링은 동일한 충실도 계약을 따릅니다:

- **답변 완전히 표시, 절대 잘리지 않음** — 이전 `[:4000]` 잘림은 문장을 끊었으며, 제거됨
  (`render.py:645-647`).
- **표 절대 잘리지 않음** — `WORKFLOW_ITEM_TABLE` 모든 행과 열 렌더링, 표 머리글과 셀 내 `|`
  및 줄바꿈은 이스케이프 처리, Markdown 구조 손상 없음 (`render.py:211-243`).
- **인용 완전** — 세 가지 수집 채널 (`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`), URL별 중복 제거하여 `sources.*`에 통합; 참조된 것은 손실되지 않음.
- **API raw JSON이 내용 경계** — 렌더링된 모든 것은 `raw_entries.json` /
  `raw_blocks.json`에서 비롯됨; API가 반환하지 않는 것 (예: 대체된 답변 변형)은 렌더링할 수 없으며, 대신 등록 키를 통해
  표시되며, 절대 추측하지 않음.
- **UI 접힘, 보관 시 전체 펼침** — 웹 UI에서 접힘 및 클릭 뒤에 숨겨진 세부 사항 (computer 워크플로 나레이션 및
  도구 입력/출력, council 단일 모델 실행, 하위 에이전트 단계) 모두 완전히 렌더링; `<details>`
  접힘 블록을 사용하여 문서 개요를 읽기 쉽게 유지하면서 정보 손실 없음 (`render.py:46`, `render.py:404-413`).
- **구조 견고성** — 코드 펜스는 내용에 따라 길이 결정 (`_fence_for`, `render.py:28-43`), 자체 펜스가 있는
  도구 출력으로 인해 쌍이 뒤집히지 않음; LaTeX 구분자는 `$$` / `$`로 정규화, 코드 세그먼트는 보호됨
  (`normalize_math_delims`).

보존된 원시 응답이 이 모든 것을 오프라인에서 재생성 가능하게 하는 방법:
[내보내기 파이프라인](../architecture/export-pipeline.md) 및 [오프라인 작업](../architecture/offline-operations.md).

<a id="另见" data-pplx-source-anchor="true"></a>
## 함께 보기

- [보관 디렉터리 구조](archive-layout.md) — 각 모드 파일의 위치
- [pplx-ask](pplx-ask.md) — 각 모드로 새 스레드 생성
- [증분 동기화](incremental-sync.md) — 재개된 스레드 다시 가져오기
- [내보내기 파이프라인](../architecture/export-pipeline.md) — 전체 모드 판정 의사 결정 트리
- [하위 에이전트 및 중단](../architecture/subagents-interruptions.md) — 배치 폭포 및 상태 머신
- [API 응답 및 오류](../reference/api/api-responses-errors.md) — 필드 실제 값
