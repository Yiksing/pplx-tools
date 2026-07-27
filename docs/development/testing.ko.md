---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/testing.zh-CN.md"
translation_source_sha256: "6135b1f3741f588961c302bffc7d049b47ff6c6df0c8797a8888b56edc1cf7a5"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试" data-pplx-source-anchor="true"></a>
# 테스트

테스트 스위트는 `tests/`에 위치하며(`pplx_export` 패키지 외부), 완전히 오프라인으로 실행됩니다. API 형태의
입력은 `tests/fixtures/`에 리포지토리와 함께 커밋된 결정론적 모의 데이터입니다. 테스트는 온라인 서비스에 의존하지 않으며,
실제 사용자 수준 구성에도 의존하지 않습니다.

이 페이지는 현재 테스트 모듈 목록과 기여 프로세스를 유지 관리합니다. 회귀 설계는
[테스트 시스템 아키텍처](testing-architecture.md)를, 입력 데이터 계약은
[테스트 fixtures](fixtures.md)를 참조하세요.

<a id="运行测试" data-pplx-source-anchor="true"></a>
## 테스트 실행

```bash
uv run pytest tests
```

pytest는 선언된 개발 종속성입니다. 테스트 스위트는 다음을 보장합니다.

- **제로 네트워크** — 모의 입력이 저장소에 있습니다. 네트워크 경로는 fake, `tmp_path` 및
  `monkeypatch`로 처리됩니다.
- **실제 사용자 구성 읽지 않음** — `tests/conftest.py`는 프로덕션 모듈을 가져오기 전에
  프로세스 수준 임시 구성을 만들고 `PPLX_EXPORT_CONFIG`를 재정의합니다. 그런 다음 각 테스트는 독립적인
  `alice` / `bob` 자리 표시자 구성을 받고, 완료 후 프로세스 수준 자리 표시자 구성이 복원됩니다. 하위 프로세스 회귀는 또한
  호출자 구성이 없거나 손상된 경우에도 테스트 수집이 실패하지 않는지 확인합니다.
- **빠른 피드백** — 이 프로젝트는 2026-07-25 기준 32개의 `test_*.py` 모듈에서
  435개의 테스트를 관찰했습니다. 로컬 검증의 전체 실행은 약 13–25초입니다. 수량은 날짜가 지정된 리포지토리 스냅샷이며,
  개발에 따라 증가합니다.

일반적인 선택:

| 명령 | 효과 |
|---|---|
| `uv run pytest tests` | 전체 스위트 |
| `uv run pytest tests/test_units.py` | 단일 모듈 |
| `uv run pytest tests -k snapshot` | `snapshot`와 일치하는 노드 ID의 테스트 |
| `uv run pytest tests -x -q` | 첫 번째 실패에서 중지, 자동 출력 |
| `uv run pytest --collect-only -q` | 수집된 테스트 수 새로 고침 |

<a id="当前模块清单" data-pplx-source-anchor="true"></a>
## 현재 모듈 목록

목록은 **2026-07-27** 기준 리포지토리와 동기화되었습니다.

<!-- audit:inventory test-modules -->

| 기능군 | 모듈 | 용도 |
|---|---|---|
| 렌더링 스냅샷 | `test_render_snapshots.py` | 모든 모의 전체 모드 및 간소화 시나리오 fixtures를 다시 렌더링하고 커밋된 아티팩트와 바이트 단위로 비교 |
| 코어 및 공유 유틸리티 | `test_units.py` | 상태, 스로틀링, 계획, 정규화, 자산 명명, 모드 판별, 안전 경로 및 교차 영역 회귀 |
| 문서 계약, skill 및 현지화 | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | 리포지토리 로컬 skill 계약, 읽기 전용 문서 감사기 및 기계 번역 파이프라인을 위한 격리된 미니 리포지토리 테스트 |
| 구성, 인증 및 초기화 | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | 외부 구성 격리, 쿠키 기반 구성, 자격 증명 선택 및 초기화 |
| 렌더링 및 워크플로 의미론 | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | 워크플로 귀속, 중단 상태, 답변 변형, 감사 로그 및 관계 가장자리 |
| 오프라인 아카이브 및 인덱스 유지 관리 | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | 보강, 재실행/멱등성 동작, 교차 계정 삭제 결정, 최종 상태, 오프라인 상태 장부/변경 보고서의 계층적 출력 |
| 검토 회귀 | 아래 표에 나열된 16개의 `test_fix_*.py` 모듈 | 검토 결과에서 비롯된 수정 사항; 모듈 이름은 검토 계통을 유지 |

<a id="评审回归-lineage" data-pplx-source-anchor="true"></a>
### 검토 회귀 계통

검토 번호는 회귀 테스트가 존재하는 이유를 설명하지만, 테스트 스위트의 기본 아키텍처는 아닙니다. 매핑은 다대다를 명시적으로 허용합니다.
하나의 모듈이 여러 발견을 다룰 수 있고, 하나의 발견이 기존 주제 모듈에 테스트 케이스를 추가할 수도 있습니다.

| 계통 | 전용 모듈 |
|---|---|
| N차 검토 | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| V3차 검토 | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| V4차 검토 | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| V5차 검토 | `test_fix_v5_review.py` 및 기존 주제 모듈의 대상 수정 |
| V6차 검토 | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

각 모듈의 docstring은 여전히 해당 발견의 이전 동작, 수정 동작 및 회귀 경계에 대한 권위 있는 설명입니다.

<a id="快照测试如何复用生产重渲路径" data-pplx-source-anchor="true"></a>
## 스냅샷 테스트가 프로덕션 재렌더링 경로를 재사용하는 방법

스냅샷 테스트는 별도의 렌더러를 구현하지 않습니다.

1. `tests/conftest.py`의 `render_fixture`는 fixture의 모의
   `raw_entries.json`, 선택적 `raw_blocks.json` 및 `thread.json`를 임시 디렉터리에 복사합니다.
2. `pplx_export.commands.rerender_cmd.rerender`를 호출합니다. 이는
   `pplx-export re-render`에서 사용하는 동일한 함수입니다.
3. `rendered` fixture 팩토리는 새 출력과 fixture에 커밋된 `golden/` 디렉터리를 반환합니다.
4. 테스트는 `conversation.md`와 모든 `turns/turn_*.md`를 바이트 단위로 비교합니다.

바이트 동등성 외에도 내용 불변성이 있습니다. 답변이 빈 자리 표시자 `(无)`로 퇴화되어서는 안 되며, `{'type': ...`와 같은
dict-repr 잔여물이 렌더링된 텍스트로 누출되어서는 안 됩니다.

<a id="新增测试" data-pplx-source-anchor="true"></a>
## 새 테스트 추가

- **기존 논리** — 해당 주제 모듈에 테스트를 추가합니다. `tmp_path`, fake 및
  `monkeypatch`를 사용합니다. 네트워크나 실제 `~/.config`에 액세스하지 마십시오.
- **버그 회귀** — 우선 해당 주제 모듈에 추가합니다. 검토 계통을 유지하는 것이 추적성을 명확히 개선하는 경우에만
  새 `test_fix_<lineage>_<slug>.py`를 만듭니다. 하나의 발견이 하나의 모듈에 해당한다고 가정하지 마십시오.
- **렌더링 회귀** — 모의 fixture를 새로 만들거나 간소화하고, 유지 관리 도구를 사용하여 golden을 다시 생성한
  다음, `test_render_snapshots.py`에 등록하거나 시나리오별 어설션을 추가합니다.

인접 코드 스타일을 따릅니다. 유형 주석, `from __future__ import annotations` 및 이중 언어 모듈
docstring.

<a id="另见" data-pplx-source-anchor="true"></a>
## 참고

- [테스트 fixtures](fixtures.md) — 모의 입력, golden 아티팩트 및 유지 관리 계약
- [테스트 시스템 아키텍처](testing-architecture.md) — 테스트 계층 및 회귀 보장
- [오프라인 작업](../architecture/offline-operations.md) — 스냅샷 테스트가 재사용하는 프로덕션 재렌더링 경로
