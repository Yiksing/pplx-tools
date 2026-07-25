---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/getting-started.zh-CN.md"
translation_source_sha256: "ea130999f3f8892de32f1a0e7eba131c868abbe632d517b80a4e234c542ca743"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="快速上手" data-pplx-source-anchor="true"></a>
# 빠른 시작

새로운 체크아웃에서 첫 번째 로컬 아카이브까지: 두 개의 명령어 설치, 사용자 수준 구성 생성, 쿠키 채널 선택,
그리고 첫 번째 내보내기 완료.

<a id="环境要求" data-pplx-source-anchor="true"></a>
## 환경 요구 사항

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)**——도구 설치 및 테스트 실행에 사용
- **Perplexity에 로그인된 데스크톱 브라우저**——도구가 세션 쿠키를 재사용하며, 구성에
  토큰을 저장하지 않음

쿠키 복호화는 `browser_cookie3`을 사용합니다. auto-detect는 Edge, Chrome, Firefox,
Safari를 지원하며, Brave, Chromium, Opera, Vivaldi는 `--cookies-from`로 지정할 수 있습니다.

<a id="安装" data-pplx-source-anchor="true"></a>
## 설치

클론할 필요 없음——git URL에서 직접 설치:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI 镜像替代（如中国大陆网络环境）：
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

로컬 클론에서 설치(저장소 루트 디렉터리):

```bash
uv tool install .            # 或开发模式：uv tool install --editable .
```

설치 후 두 개의 명령어를 사용할 수 있습니다: `pplx-export`(아카이브)와 `pplx-ask`(대화형 쿼리). 확인:

```bash
pplx-export --version
pplx-export --help           # 总览（含示例）；每个子命令另有专属 --help
pplx-ask --help
```

`uvx --from . pplx-export`은 설치 없이 단일 실행이 가능합니다.

<a id="创建用户级配置" data-pplx-source-anchor="true"></a>
## 사용자 수준 구성 생성

계정 레지스트리(표시 이름 / email / user_id)와 BOT 공간은 개인 정보이므로 **저장소에 포함하지 않으며**, 외부
TOML 파일로 관리합니다. 템플릿은 저장소 루트 디렉터리의 `config.example.toml`에서 확인할 수 있습니다.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # 含个人隐私，建议仅属主可读写
# 编辑填入真实账户值
```

1. 구성 디렉터리를 생성합니다.
2. 템플릿을 기본 경로에 복사합니다.
3. `chmod 600`——파일에 개인 정보가 포함되어 있으므로 소유자만 읽고 쓸 수 있도록 유지합니다.
4. `[accounts.<name>]`를 작성합니다——키는 계정 사용자 이름(thread URL / library의
   username)입니다. `display_name`, `email`, `user_id`을 설정하고 `default_account`을 선택합니다.
5. `[bot_space]`를 작성합니다——`pplx-ask` 질문 완료 후 스레드의 중앙 저장소입니다(`pplx-ask space-create`로
   실제 생성 가능).

**자동 대안:** `pplx-export init`가 이 파일을 추론할 수 있습니다——브라우저에서 각 계정의
세션 쿠키를 열거하고, `/api/auth/session`를 통해 email/표시 이름을 얻은 후,
`default_account`를 현재 활성 계정으로 설정하고, 제목으로 BOT 공간을 매칭하며, 0600 권한으로
TOML을 원자적으로 작성합니다(이미 존재하는 파일은 `--force`인 경우에만 덮어씁니다).

```bash
pplx-export init                     # 发现账户，写入默认配置路径
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --bot-title TITLE   # 匹配/创建其他标题的空间（默认 BOT）
pplx-export init --config /path/to/config.toml   # 写入自定义路径
```

플래그 설명: `--force`는 기존 구성을 덮어씁니다. `--create-bot-space [标题]`는 제목 매칭이 없을 때
API를 통해 공간을 생성합니다(계정에 대한 쓰기 작업 한 번; 명시적 제목이 있으면 매칭과 생성 모두 해당 제목 사용).
`--bot-title TITLE`는 매칭과 생성 모두에 사용됩니다. 참고: 다른 모든 명령어와 달리, `init`의 `--config`는 **쓰기** 경로이며
로드 경로가 아닙니다. 전체 설명은 [pplx-export → init](pplx-export.md#init)을 참조하세요.

전체 필드 설명은 [구성](configuration.md)을 참조하세요.

**로드 우선순위**(높은 순에서 낮은 순):

| # | 출처 |
|---|------|
| 1 | `--config PATH` |
| 2 | 환경 변수 `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml`(기본값) |

!!! note "구성이 없을 때"
    `--account`가 지정되지 않은 명령어는 저하된 모드로 실행됩니다——email 소유권 확인을 건너뛰고 warning을 출력합니다
    (오프라인 명령어는 영향을 받지 않음). 명시적인 `--account`는 오류를 발생시키고 `config.example.toml`을 가리킵니다.
    `--account`가 제공되지 않으면 구성의 `default_account`을 사용합니다.

<a id="选择-cookie-通道" data-pplx-source-anchor="true"></a>
## 쿠키 채널 선택

자격 증명은 로컬 브라우저에 로그인된 Perplexity 세션 쿠키에서 가져오며, `browser_cookie3`를 통해 읽습니다——
여러 계정 토큰 열거 및 자동 전환을 포함합니다. 총 4개의 채널이 있습니다:

| 채널 | 사용법 | 설명 |
|------|------|------|
| auto-detect(기본값) | 인수 없음 | 먼저 12시간 동안 신선한 캐시를 사용한 후, edge→chrome→firefox→safari 순서로 브라우저 라이브러리 탐지 |
| 브라우저 지정 | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| 쿠키 파일 | `--cookies /path/to/cookies.txt` | Netscape 쿠키 파일 또는 내보낸 JSON |
| WebBridge | `--transport webbridge` | 페이지 컨텍스트 fetch——대체 채널, 명시적 지정 필요 |

Linux에서 snap 및 flatpak으로 설치된 브라우저도 auto-detect 가능——프로필 경로가
내장 레지스트리에 포함되어 있습니다. 전체 Linux 매트릭스(keyring, 데스크톱 환경, 배포판 패키지)는
[문제 해결 → Linux 쿠키 복호화](troubleshooting.md#linux-cookie-解密)를 참조하세요.

```bash
pplx-export export <thread_url>                                 # 默认：auto-detect 浏览器库
pplx-export export <thread_url> --cookies-from edge             # 指定从某个浏览器导入
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # 用 cookie 文件
pplx-export export <thread_url> --transport webbridge           # WebBridge 页面上下文（显式回退）
```

쿠키를 가져온 후 `/api/auth/session`를 호출하여 현재 계정 이메일을 출력하므로, 계정이 올바른지 확인할 수 있습니다
——`--account`와 쿠키 계정이 일치하지 않으면 주의하세요. 전송/자격 증명 설계에 대한 자세한 내용은
[질문 및 계정](../architecture/ask-and-accounts.md)을 참조하세요.

<a id="首次运行" data-pplx-source-anchor="true"></a>
## 첫 실행

```bash
pplx-export index --account alice     # 拉取 library 索引
pplx-export export <thread_url>       # 导出单线程
pplx-export batch --account alice     # 批量（默认增量早停；--full 全量兜底）
pplx-export re-render --dry-run       # 离线重渲，零网络
```

1. **`index`** 계정의 library 인덱스를 가져옵니다——`batch` 등 계정 수준 명령어의 진입점입니다.
2. **`export`** 단일 스레드를 종단간 아카이브합니다: 원시 응답(`raw_*.json`)과 Markdown을
   함께 보존하며, 이후 오프라인에서 다시 렌더링할 수 있습니다.
3. **`batch`** 전체 라이브러리를 스캔합니다: 남은 스레드가 모두 아카이브되면 조기 중단(증분 조기 중단), 중단 지점에서 재개,
   `--full` 전체 대비책. 자세한 내용은 [증분 동기화](incremental-sync.md)를 참조하세요.
4. **`re-render --dry-run`** 오프라인 파이프라인을 검증합니다: 로컬 raw 파일만으로
   `conversation.md` + `turns/`을 재구성하며, 네트워크 없음. `--dry-run`를 제거해야 실제로 디스크에 씁니다. 자세한 내용은
   [오프라인 작업](../architecture/offline-operations.md)을 참조하세요.

실행에 성공하면, `pplx-ask ask "<prompt>"`로 스트리밍 질문을 하고 생성된 스레드를 자동으로 아카이브할 수 있습니다——
[pplx-ask](pplx-ask.md)를 참조하세요.

<a id="归档落盘位置" data-pplx-source-anchor="true"></a>
## 아카이브 저장 위치

아카이브는 기본적으로 `./web_archive/`에 저장됩니다(`--out`로 재정의 가능): 각 스레드당 하나의 디렉터리.

| 경로 | 내용 |
|------|------|
| `conversation.md`, `turns/` | 렌더링된 대화 |
| `thread.json` | 스레드 메타데이터 + interruptions 기록 |
| `sources.md` / `sources.json` | 인용 |
| `report.md` | Deep Research / Pro / study 보고서 |
| `assets/` | 다운로드된 자산(Computer 모드) |
| `raw_*.json` | 보존된 원시 API 응답——성공적인 아카이브를 위해 다시 가져올 필요 없이 오프라인에서 다시 렌더링 가능 |

전체 디렉터리 규칙은 [아카이브 레이아웃](archive-layout.md)을 참조하세요.

<a id="下一步" data-pplx-source-anchor="true"></a>
## 다음 단계

- 문제가 있나요? → [문제 해결](troubleshooting.md)
- 명령어별 참조 → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [유지 관리 명령어](maintenance-commands.md)
- 다섯 가지 대화 모드 → [모드](modes.md)
