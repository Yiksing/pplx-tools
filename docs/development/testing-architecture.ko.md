---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/testing-architecture.zh-CN.md"
translation_source_sha256: "7e7e01902d3e8e45e0929e728479bc7adbd556f2b2706972fecec4a9b9f5b77f"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试架构" data-pplx-source-anchor="true"></a>
# 테스트 아키텍처

`pplx_export` 테스트 시스템은 완전히 오프라인이며, 커밋된 모의 데이터를 사용하고 스냅샷으로 렌더러 동작을 고정합니다. 이 페이지는 아키텍처와 보장 사항을 설명합니다. 현재 모듈 목록은 [테스트](../development/testing.md)에서, fixture 세부 사항은 [테스트 fixtures](../development/fixtures.md)에서 관리합니다.

하위 섹션은 [아키텍처 개요](../architecture/overview.md)의 번호를 따릅니다.

---

<a id="测试体系" data-pplx-source-anchor="true"></a>
## 테스트 시스템

`uv run pytest tests`를 사용하여 스위트를 실행합니다. 테스트 수는 현재 실행 결과에 따라 보고되며, 아키텍처 상수로 간주되지 않습니다.

<a id="层次" data-pplx-source-anchor="true"></a>
### 계층

| 계층 | 대표 모듈 | 계약 |
|---|---|---|
| 순수 단위 동작 | `test_units.py`, 자격 증명/cookie/구성 테스트 | 모의 입력으로 함수, 클래스, 검증 및 정규화를 격리 |
| 컴포넌트 의미론 | 중단, 스텁 워크플로우, 답변 변형 및 relations 테스트 | 제로 네트워크 조건에서 파서, 렌더러, 상태 및 인덱스 코드의 협업을 다룸 |
| 오프라인 명령 및 상태 동작 | 백필, 삭제 동기화, 초기화 및 리뷰 회귀 | 임시 디렉토리와 fake transport에서 명령 경로 실행 |
| 렌더링 스냅샷 | `test_render_snapshots.py` | API 형태의 모의 JSON을 프로덕션 재렌더링 경로에 주입하고, 모든 Markdown을 커밋된 golden과 바이트 단위로 비교 |

N, V3, V4, V5 등의 리뷰 번호는 계층 간 추적 가능한 메타데이터이며, 독립적인 실행 아키텍처를 정의하지 않고 테스트 모듈과 일대일 대응하지 않아도 됩니다.

<a id="快照数据流" data-pplx-source-anchor="true"></a>
### 스냅샷 데이터 흐름

1. 모의 fixture가 `raw_entries.json`, 선택적 `raw_blocks.json` 및 `thread.json`를 제공합니다.
2. `tests/conftest.py::render_fixture`가 이 파일들을 `tmp_path`로 복사합니다.
3. Fixture가 `commands.rerender_cmd.rerender`, 즉 프로덕션 오프라인 재구성 경로를 호출합니다.
4. 새로 생성된 `conversation.md`가 `turns/turn_*.md` 및 커밋된 `golden/` 아티팩트와 바이트 단위로 비교됩니다.

Golden은 생성된 예상 결과이며, 독립적인 데이터 소스가 아닙니다. 출력 바이트를 변경하는 모든 렌더러 수정은 스냅샷 스위트를 실패하게 하며, 수정이 검토되고 의도적으로 golden을 재생성할 때까지 유지됩니다.

<a id="隔离与信任边界" data-pplx-source-anchor="true"></a>
### 격리 및 신뢰 경계

- **Fixture 출처**——커밋된 모든 fixture 입력은 모의 데이터이며, 온라인 계정, 실시간 API 응답, `web_archive/` 또는 개인 아카이브에서 복사되지 않습니다.
- **네트워크 경계**——테스트는 fake 및 오프라인 경로를 사용합니다. 커밋된 fixtures는 자격 증명이나 네트워크가 필요하지 않습니다.
- **구성 경계**——autouse fixture가 플레이스홀더 계정 구성을 설치하므로, 개발자의 실제 `~/.config`가 테스트 결과를 결정하지 않습니다.
- **파일 시스템 경계**——명령 및 마이그레이션 동작은 `tmp_path` 아래에서 실행되며, 사용자 아카이브를 테스트 대상으로 삼지 않습니다.
- **잔여 경계**——`tests/scrub_fixtures.py --check`는 파일을 수정하지 않고 구성된 환경 관련 문자열, 로컬 절대 경로 및 서명된 URL 자격 증명을 거부합니다.

단위 어설션, 컴포넌트 의미론, 명령 상태 테스트 및 바이트 수준 스냅샷은 로직과 종단 간 재렌더링 계약을 함께 보호합니다.
