---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/index.zh-CN.md"
translation_source_sha256: "11e03bf1d56e3cd6e14277369f8369ceba6af4385ecb25765fe3c05980c9c5c6"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="系统架构阅读地图" data-pplx-source-anchor="true"></a>
# 시스템 아키텍처 읽기 지도

pplx-tools(`pplx-export` / `pplx-ask`)의 메커니즘 계층 참조: 의존 관계, 실행 파이프라인,
상태 머신, 데이터 계약 및 신뢰성 경계. 작업 지향 설명은 [사용 가이드](../guide/index.md)부터 시작하세요.

!!! note "범위 및 사실 출처"

    이 영역은 프로젝트를 유지보수하는 에이전트와 엔지니어를 대상으로 `pplx_export/`의 시스템 아키텍처를 설명합니다.
    줄 번호 참조는 `file.py:NN`을 사용하며, 모두 `pplx_export/`를 기준으로 합니다. 페이지 내용은
    2026-07-23에 저장소와 대조하여 확인했습니다(`__version__ = "0.1.0"`,
    `pplx_export/__init__.py:31`). 현재 코드와 테스트가 여전히 최종 사실 출처입니다.

<a id="从系统地图开始" data-pplx-source-anchor="true"></a>
## 시스템 맵부터 시작하기

- [아키텍처 개요](overview.md)——계층 구조, 모듈 책임 및 실제 import 의존 그래프.

<a id="沿运行流程阅读" data-pplx-source-anchor="true"></a>
## 실행 흐름 따라 읽기

- [내보내기 파이프라인](export-pipeline.md)——크롤링, 원시 응답 보존, 패턴 인식 및 Markdown
  렌더링.
- [하위 에이전트 및 중단](subagents-interruptions.md)——백그라운드 산출물 귀속 및 중단/재개 의미.
- [pplx-ask 및 다중 계정](ask-and-accounts.md)——스트리밍 질문 및 다중 계정 쿠키 전환.

<a id="理解数据与可靠性" data-pplx-source-anchor="true"></a>
## 데이터 및 신뢰성 이해하기

- [데이터 모델 및 디렉터리 계약](data-model.md)——모델, 쓰기 경계 및 디스크 아카이브 계약.
- [속도 제한 및 오류 처리](rate-limiting-errors.md)——스로틀링, 백오프, 최종 상태 및 오류 분류.
- [오프라인 운영 메커니즘](offline-operations.md)——네트워크 없는 재렌더링, 관계 그래프 재구성 및 로컬 유지보수 파이프라인.

<a id="相关参考" data-pplx-source-anchor="true"></a>
## 관련 참조

- [Web API 참조](../reference/api/index.md)——관찰된 REST/GraphQL 계약, 응답 의미 및
  발견 기록.
- [유지보수자 가이드](../development/index.md)——테스트 아키텍처, 기여자 워크플로 및 모의 fixture 계약.
