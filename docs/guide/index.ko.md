---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/index.zh-CN.md"
translation_source_sha256: "36473d77356f8d36bd928e79c8c3584fc1e4e8a7c0e269b00dbb63bef56b458c"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="使用指南" data-pplx-source-anchor="true"></a>
# 사용 가이드

작업 중심의 `pplx-export` 및 `pplx-ask` 설치, 구성 및 실행 문서입니다.

<a id="开始使用" data-pplx-source-anchor="true"></a>
## 시작하기

- [빠른 시작](getting-started.md)——설치 명령, 초기 구성 및 첫 내보내기 실행.
- [구성](configuration.md)——계정, 쿠키 소스, 출력 루트 디렉터리 및 BOT 공간.

<a id="命令参考" data-pplx-source-anchor="true"></a>
## 명령어 참조

- [pplx-export](pplx-export.md)——인덱싱, 단일 스레드 내보내기 및 일괄 보관.
- [pplx-ask](pplx-ask.md)——search, deep-research, council 및 study 스트리밍 질문.
- [유지 관리 명령어](maintenance-commands.md)——재렌더링, 보충 기록, 관계도 및 동기화 작업.

<a id="归档与同步" data-pplx-source-anchor="true"></a>
## 보관 및 동기화

- [보관 구조](archive-layout.md)——파일, 인덱스, 상태 및 보존된 원본 응답.
- [세션 모드](modes.md)——지원되는 각 모드의 산출물 경계.
- [증분 동기화](incremental-sync.md)——조기 중단, 체크포인트 및 중단 지점에서 재개 의미.

<a id="运行与排错" data-pplx-source-anchor="true"></a>
## 실행 및 문제 해결

- [속도 제한 규율](rate-limiting.md)——안전한 요청 속도 및 스케줄링.
- [문제 해결](troubleshooting.md)——일반적인 오류 및 복구 경로.

구현 메커니즘을 이해해야 하는 경우 [시스템 아키텍처 읽기 지도](../architecture/index.md)를 계속 읽으십시오.
