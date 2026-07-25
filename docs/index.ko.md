---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/index.zh-CN.md"
translation_source_sha256: "49d67dcdb3d8715b15c05689069b96ae47f030e3c8c86ece51558818b535fc14"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="perplexity-命令行工具集" data-pplx-source-anchor="true"></a>
# Perplexity 명령줄 도구 모음

<p class="homepage-scope-note" role="note">
  <strong>기존 구독에 적용되며, 종량제 API에는 적용되지 않습니다</strong>
</p>

Perplexity 대화 기록 보관 및 대화형 조회 도구 (`pplx-export` / `pplx-ask` 이중 명령).

브라우저 쿠키를 통해 Perplexity REST/GraphQL API에 직접 연결하여 대화(단계, 인용, 심층 연구 보고서, computer 자산, 하위 에이전트 워크플로 포함)를 로컬 Markdown + JSON으로 완전히 보관합니다. 성공적인 내보내기는 원본 응답과 렌더링된 결과물을 모두 보존하므로, 다시 가져오지 않고도 오프라인에서 다시 렌더링할 수 있습니다.

<a id="简介" data-pplx-source-anchor="true"></a>
## 소개

과거 대화를 보관하는 것 외에도, 이 프로젝트의 목적은 데이터에 더 가깝고 더 강력한 컴퓨팅 성능을 가진 로컬 에이전트가 어느 정도의 Perplexity Computer 능력을 갖추도록 하는 데 더 있습니다. 작업 루프에서 Perplexity 심층 연구 모드가 생성한 보고서에 직접 액세스함으로써, 로컬 에이전트는 고품질 정보를 활용하여 코드의 핵심 매개변수를 더 정밀하게 조정하는 동시에 기존 Perplexity Max 구독을 더욱 완전히 활용할 수 있습니다.

> 7월 20일 기준으로 Perplexity는 유닉스 계열 환경에서 공식 CLI를 제공하지 않았습니다.
> 7월 23일에 공식적으로 Computer 모드에서 사용되는 pplx 도구의 공개 릴리스 버전이 제공되었음을 확인했습니다. 그러나 해당 도구는 여전히 종량제입니다.

하지만 이는 Computer 모드를 완전히 대체하지는 않습니다. 복제할 수 없는 두 가지 기능이 있습니다:

- 심층 연구 스킬은 모델을 자유롭게 지정할 수 있습니다.
- 모델 위원회 스킬은 여러 다른 모델을 지정하여 각각 심층 연구를 수행하고 보고서를 출력한 후 직접 비교할 수 있습니다.

저장소의 [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context) 디렉토리에는 일부 시스템 프롬프트와 실행 규칙이 보관되어 있어, 심층 연구 모드 선택 및 하위 에이전트 모델 선택을 포함하여 Computer의 일부 워크플로를 로컬에서 근사하는 데 도움이 될 수 있습니다.

<a id="功能概览" data-pplx-source-anchor="true"></a>
## 기능 개요

<a id="pplx-export-归档你的-library" data-pplx-source-anchor="true"></a>
### `pplx-export` — 라이브러리 보관

- 라이브러리 인덱스 및 공간 인덱스
- 단일 스레드/일괄 내보내기 (증분 조기 중단 + 중단점 재개)
- 자산 복구 및 사용량 추가 기록
- 대화 관계 그래프
- 오프라인 재렌더링 (`re-render`, 네트워크 없음)
- 주기적 증분 cron 조각

<a id="pplx-ask-在命令行发问" data-pplx-source-anchor="true"></a>
### `pplx-ask` — 명령줄에서 질문하기

- SSE 스트리밍 질문 (search / deep-research / council / study 네 가지 모드)
- 완료 후 자동으로 BOT 공간으로 이동, 읽음 확인
- 생성된 스레드는 자동으로 보관 — 다른 에이전트가 실시간 정보를 검색하기 위해 호출할 수 있음

다섯 가지 모드의 산출물 경계(인용/보고서/자산/하위 에이전트)는 [모드](guide/modes.md)를 참조하십시오. 렌더링 충실도 원칙은 [내보내기 파이프라인](architecture/export-pipeline.md)을 참조하십시오.

!!! note "문서 출처"

    MkDocs 사이트의 대부분 페이지는 현재 코드와 테스트를 기반으로 생성되거나 재생성됩니다. 일부 페이지는 이전에 에이전트와 논의하여 형성된 설계 배경, 관찰 기록 및 결정 사항도 보존합니다. 문서 표현이 구현과 일치하지 않는 경우, 현재 코드와 테스트를 기준으로 합니다.

<a id="接下来去哪" data-pplx-source-anchor="true"></a>
## 다음 단계

- **도구 사용** — 작업별로 [사용 가이드](guide/index.md)를 읽으십시오.
- **구현 이해** — [시스템 아키텍처 읽기 지도](architecture/index.md)로 시작하십시오.
- **관찰된 웹 인터페이스 처리** — [Web API 참조](reference/api/index.md)를 확인하십시오.
- **프로젝트 안전하게 수정** — [유지 관리자 가이드](development/index.md)를 따르십시오.
