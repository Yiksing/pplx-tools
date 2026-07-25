---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/api-authentication.zh-CN.md"
translation_source_sha256: "406c7c3482391bd37729d04f0ef0d57990bf5540a96837da279ae0429277d588"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="认证模型" data-pplx-source-anchor="true"></a>
# 인증 모델

> 이 페이지는 API 참조 영역의 첫 페이지입니다——pplx_export 프로젝트의 Perplexity 비공개 Web API에 대한 실측 기록입니다.
> 독자: 이 프로젝트의 유지 관리자와 사용자. 모든 엔드포인트는 WebBridge 네트워크 캡처 + 쿠키 직접 연결을 통해 실측 검증되었습니다(2026-07).
> **API 인지 사항을 수정/추가할 때는 이 페이지들을 반드시 함께 업데이트해야 합니다**(사용자 명시적 요구).
> 마지막 업데이트: 2026-07-23
>
> 참조 영역은 다음과 같이 나뉩니다: **1. 인증 모델**(이 페이지) · [2. GraphQL(영구 쿼리 APQ)](api-graphql.md) · [3. REST 엔드포인트(용도별 그룹화)](api-rest-endpoints.md) · [4–5. 응답 구조와 오류 의미](api-responses-errors.md) · [6–8. 확인 대기 항목, 엔드포인트 발견 및 로드맵](api-discovery-roadmap.md)——주변 시스템 설계는 [시스템 아키텍처 읽기 지도](../../architecture/index.md)를 참조하세요.

---

<a id="认证模型_1" data-pplx-source-anchor="true"></a>
## 인증 모델

<a id="cookie-会话" data-pplx-source-anchor="true"></a>
### 쿠키 세션
- 모든 API 요청은 브라우저 세션 쿠키만 필요합니다(CSRF 토큰 불필요; GET/POST 모두 직접 연결 실측 성공).
- 주요 쿠키: `__Secure-next-auth.session-token`(**현재 활성 계정**의 세션 토큰).
- Cloudflare 전단: `cf_clearance`/`__cf_bm`는 브라우저 TLS 지문과 바인딩됩니다——**curl 원시 요청은 403**;
  도구는 Python urllib + 브라우저에서 가져온 쿠키를 사용하여 정상 통과 가능(UA를 데스크톱 Chrome으로 위장).

<a id="多账户2026-07-20-探明" data-pplx-source-anchor="true"></a>
### 다중 계정(2026-07-20 확인)
- 동일 브라우저에서 여러 계정으로 로그인 시, 각 계정마다 하나의 `__Secure-pplx.session.<user_id>` 쿠키를 보유합니다
  (도메인 www.perplexity.ai; 값은 응답에 따라 롤링 갱신).
- `__Secure-next-auth.session-token`의 값 = 활성 계정의 per-account 쿠키 값.
- **웹에서 계정 전환** = `https://www.perplexity.ai/?pplx_account=<user_id>` 탐색, 서버가 활성 토큰을 변경.
- **도구 측 자동 전환**(pplx_export 구현됨): 브라우저에서 `__Secure-pplx.session.*`을 열거,
  `__Secure-next-auth.session-token`을 하나씩 교체하고 `/api/auth/session`을 탐지하여 대상 이메일과 일치할 때까지 진행.
- `GET /api/auth/linked-accounts`는 `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`을 반환하지만,
  **primary 계정이 활성화된 경우에만 모든 계정을 반환**(primary가 아닌 계정이 활성화된 경우 현재 계정만 반환)——따라서 도구는 이에 의존하지 않음.
- 등록된 계정 예시(실제 계정 테이블은 사용자 수준 `config.toml`로 외부화, 여기서는 자리 표시자):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa`(Max);
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb`(Pro, primary).
