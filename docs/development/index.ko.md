---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/index.zh-CN.md"
translation_source_sha256: "8708f914f56087b4180143beba883a20b4055715274a1f95823832bb5fd03b4b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="维护者指南" data-pplx-source-anchor="true"></a>
# 유지 관리자 가이드

아카이브 충실도나 테스트 격리를 약화시키지 않으면서 pplx-tools를 수정하는 데 필요한 계약과 워크플로입니다.

<a id="选择对应文档" data-pplx-source-anchor="true"></a>
## 관련 문서 선택

- [테스트 시스템 아키텍처](testing-architecture.md) — 테스트 계층, 신뢰 경계, 오프라인 스냅샷이 제공하는 보증.
- [테스트 실무](testing.md) — 현재 테스트 체크리스트와 기여자 워크플로.
- [Fixtures 및 스냅샷](fixtures.md) — 모의 데이터 소스, 디렉터리 규칙, 골든 생성 및 잔여물 검사.

<a id="本地质量闭环" data-pplx-source-anchor="true"></a>
## 로컬 품질 루프

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Fixture 입력은 결정론적 모의 데이터이며, 실제 계정, 실시간 API 응답, `web_archive/` 또는 개인 아카이브에서 가져오지 않습니다.
