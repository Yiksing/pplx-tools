---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/fixtures.zh-CN.md"
translation_source_sha256: "a34e1db385d79a8f56c92b6dfccfd6c90c76ec38feef5af63c4393418d02dc81"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试-fixtures" data-pplx-source-anchor="true"></a>
# 테스트 fixtures

`tests/fixtures/`는 [테스트 스위트](testing.md)에 결정론적이고 API 구조를 가진
**모의 데이터**를 제공합니다. 입력은 대표적인 스레드 및 워크플로 구조를 시뮬레이션하며, 렌더링 결과물은 golden
스냅샷 형태로 저장소에 커밋됩니다.

<a id="来源契约" data-pplx-source-anchor="true"></a>
## 출처 계약

<!-- audit:contract fixture-source=simulated -->

현재 커밋된 fixture 내용은 모두 모의 데이터입니다:

- 새 fixture를 추가하거나 업데이트할 때는 모의 데이터를 구성해야 합니다. `web_archive/`,
  사용자 계정 데이터, 실시간 API 응답 또는 개인 아카이브를 가져와서 채워서는 안 됩니다.
- 커밋된 파일의 이름, 신원, 식별자, prompt, answer, 워크플로 페이로드, 경로 및 URL은
  테스트용 플레이스홀더입니다.
- JSON은 파서, 렌더러, 상태 및 관계 동작을 다루기 위해 프로덕션 응답 및 아카이브 스키마를 모방합니다.
- 저장소는 플레이스홀더에서 개인 식별자로의 역매핑을 커밋하지 않습니다.

**전체 모드 fixture**와 **간소화 시나리오 fixture**는 적용 범위와 입력 형태를 설명하며,
데이터 출처를 설명하는 것이 아닙니다. 둘 다 모의 데이터입니다.

<a id="目录契约" data-pplx-source-anchor="true"></a>
## 디렉터리 계약

각 fixture 디렉터리에는 원래 응답 형태를 가진 모의 입력이 포함되며, 스냅샷 비교가 필요할 때는
`golden/` 트리도 포함됩니다:

| 경로 | 역할 |
|---|---|
| `raw_entries.json` | 프로덕션 응답 형태와 일치하는 모의 스레드 entries |
| `raw_blocks.json` | 모의 workflow blocks; 해당 모드에 block 응답이 없으면 누락 |
| `thread.json` | 모의 아카이브 스레드 메타데이터 |
| `golden/conversation.md` + `golden/turns/turn_*.md` | 모의 입력에서 생성되어 바이트 단위로 비교되는 결과물 |

현재 결정론적 규칙은 다음과 같습니다:

- 플레이스홀더 계정 `alice` / `bob`, 예시 신원, 플레이스홀더 BOT 공간 및 고정
  `read_write_token`;
- `5cbeef00` 태그가 있는 uuid5 파생 식별자로, 모의 레코드 간 의도된 상호 참조를 유지;
- `5crub0` 태그가 있는 고정 길이 모의 `toolu_` 식별자;
- 일반적인 prompt, 제목, 워크플로 텍스트 및 파일 경로;
- 쿼리 문자열이 제거된 서명된 URL.

이러한 규칙은 우발적으로 혼입된 환경 관련 잔여물을 쉽게 발견할 수 있게 합니다. 모의 식별자가 온라인 객체에서 비롯되었음을 의미하지는 않습니다.

<a id="清单" data-pplx-source-anchor="true"></a>
## 인벤토리

<!-- audit:inventory fixture-directories -->

<a id="完整模式-fixtures" data-pplx-source-anchor="true"></a>
### 전체 모드 fixtures

지원되는 각 모드에는 완전한 모의 세션이 있습니다:

| Fixture | 적용 범위 |
|---|---|
| `search_demo` | search, 단일 라운드; R 코드 펜스 및 인라인 코드 |
| `deep_research_demo` | deep research; 종단 간 수학 구분자 변환 |
| `computer_demo` | computer, 7라운드 워크플로 렌더링 |
| `council_demo` | council 모델 위원회 렌더링 및 대규모 중첩 페이로드 |
| `study_demo` | study 모드 렌더링 |

<a id="精简场景-fixtures" data-pplx-source-anchor="true"></a>
### 간소화 시나리오 fixtures

이들은 특정 회귀에 필요한 entries와 관계만 유지하는 고정 모의 페이로드입니다. "간소화"는 실제 스레드에서 추출했음을 의미하지 않습니다.

| Fixture | 적용 범위 |
|---|---|
| `scenario_computer_answer_fallback` | 일반 FINAL 경로를 사용할 수 없을 때 패턴화된 workflow block에서 답변 복구 |
| `scenario_subagent_fallback` | background 일치 항목이 없을 때 하위 에이전트 제목 및 자체 항목 렌더링 |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` Q&A 렌더링 |
| `scenario_subagent_stub` | 앵커 없는 subagent-result 스텁의 10초 연관 윈도우 |
| `scenario_workflow_item_nested` | 중첩된 `WORKFLOW_ITEM_WORKFLOW` 접힘 블록 렌더링 |
| `scenario_limit_interrupted` | 크레딧 중단, 기여 폭포, 부록 배치 및 중복 렌더링 금지 |
| `scenario_canceled` | `WORKFLOW_CANCELED` 주석 |

<!-- /audit:inventory fixture-directories -->

<a id="维护-fixtures" data-pplx-source-anchor="true"></a>
## Fixtures 유지 관리

`tests/scrub_fixtures.py`는 모의 데이터를 정규화하고, 프로덕션 오프라인 렌더러를 통해 golden을
재생성하며, 잔여물 게이트를 실행합니다:

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **재생성**——각 fixture는 임시 디렉터리에서
  `pplx_export.commands.rerender_cmd.rerender`를 통해 렌더링되며, 라운드 수가 일치하지 않으면 중단됩니다.
- **결정론적 정규화**——플레이스홀더 텍스트, UUID, `toolu_` 값, 토큰 및 서명된 URL이
  멱등적으로 정규화됩니다.
- **안전한 입력은 데이터 출처가 아님**——선택적 로컬 `tests/scrub_pairs.local.json`
  및 사용자 수준 계정 구성은 대체 및 잔여물 검사만 확장합니다. fixture 시나리오를 구성하는
  입력으로 사용해서는 안 됩니다.
- **검사 모드**——`--check`는 파일을 쓰지 않습니다. 구성된 잔여물, 로컬 절대 경로 또는 서명된 URL
  자격 증명이 발견되면 실패합니다.

모의 입력 JSON 또는 렌더러 출력을 수정한 후 유지 관리 도구를 실행하고, fixture 변경 사항을 커밋하기 전에
`--check`를 실행하세요.

<a id="golden-快照的权威边界" data-pplx-source-anchor="true"></a>
## Golden 스냅샷의 권위 경계

커밋된 모의 JSON은 입력 진실 공급원입니다. Golden Markdown은 파생물입니다: 현재 프로덕션 재렌더링
경로를 통해 모의 JSON에서 재생성된 후 바이트 수준 회귀 비교를 위해 커밋됩니다. 독립적인 진실 공급원으로
수동 유지 관리해서는 안 됩니다.

<a id="另见" data-pplx-source-anchor="true"></a>
## 참고

- [테스트](testing.md)——스위트가 fixtures를 사용하는 방법
- [테스트 시스템 아키텍처](testing-architecture.md)——회귀 계층 및 보증
- `tests/fixtures/README.zh-CN.md`——저장소 내 fixture 인벤토리
