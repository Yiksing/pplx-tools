---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/index.zh-CN.md"
translation_source_sha256: "6e3c3f3adb7e4fa7d731b9d510aacd07fb9c71885c4618222a12f066997cd316"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-参考" data-pplx-source-anchor="true"></a>
# Web API 참조

`pplx-export` 및 `pplx-ask`에서 사용하는 Perplexity REST 및 GraphQL 동작 관찰 기록입니다.

!!! warning "관찰된 인터페이스, 안정성 약속 아님"

    이 섹션은 프로젝트의 웹 애플리케이션, 보관된 응답, 프론트엔드 번들 및 현재 구현에서 관찰된 동작을 기반으로 정리되었습니다.
    Perplexity 공식 API 계약이 아닙니다. 네트워크 코드를 수정하기 전에 날짜가 포함된 관찰 결과를 다시 확인하십시오.

<a id="推荐阅读顺序" data-pplx-source-anchor="true"></a>
## 권장 읽기 순서

1. [인증 모델](api-authentication.md) — 세션 쿠키, 토큰, 연결된 계정 및 신원.
2. [GraphQL](api-graphql.md) — 지속적 쿼리, APQ 식별자 및 사용 중인 작업.
3. [REST 엔드포인트](api-rest-endpoints.md) — 용도별로 그룹화된 관찰된 엔드포인트.
4. [응답 및 오류 의미론](api-responses-errors.md) — 응답 형태, 구문 분석 규율, 최종 상태 및 리스크 관리 동작.
5. [발견 방법 및 로드맵](api-discovery-roadmap.md) — 엔드포인트 발견 방법 및 아직 확인되지 않은 문제.

<a id="相关实现文档" data-pplx-source-anchor="true"></a>
## 관련 구현 문서

- [pplx-ask 및 다중 계정](../../architecture/ask-and-accounts.md)
- [속도 제한 및 오류 처리](../../architecture/rate-limiting-errors.md)
- [문제 해결](../../guide/troubleshooting.md)
