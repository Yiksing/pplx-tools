---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/getting-started.zh-CN.md"
translation_source_sha256: "ea130999f3f8892de32f1a0e7eba131c868abbe632d517b80a4e234c542ca743"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# 快速上手

從全新檢出到第一份本地歸檔：安裝兩個命令、建立使用者級設定、選擇 cookie 通道，
並完成首次匯出。

<a id="环境要求" data-pplx-source-anchor="true"></a>
## 環境需求

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)**——用於安裝工具與執行測試
- **一個已登入 Perplexity 的桌面瀏覽器**——工具複用其工作階段 cookie；設定中不存放
  任何 token

cookie 解密使用 `browser_cookie3`。auto-detect 涵蓋 Edge、Chrome、Firefox、
Safari；Brave、Chromium、Opera、Vivaldi 可經 `--cookies-from` 指定。

<a id="安装" data-pplx-source-anchor="true"></a>
## 安裝

無需複製——直接從 git URL 安裝：

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI 镜像替代（如中国大陆网络环境）：
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

從本地複製安裝（倉庫根目錄）：

```bash
uv tool install .            # 或开发模式：uv tool install --editable .
```

安裝後得到兩個命令：`pplx-export`（歸檔）與 `pplx-ask`（互動式查詢）。驗證：

```bash
pplx-export --version
pplx-export --help           # 总览（含示例）；每个子命令另有专属 --help
pplx-ask --help
```

`uvx --from . pplx-export` 可免安裝單次執行。

<a id="创建用户级配置" data-pplx-source-anchor="true"></a>
## 建立使用者級設定

帳戶註冊表（顯示名稱 / email / user_id）與 BOT 空間屬個人隱私，**不入庫**，外置為
TOML 檔案。範本見倉庫根目錄 `config.example.toml`。

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # 含个人隐私，建议仅属主可读写
# 编辑填入真实账户值
```

1. 建立設定目錄。
2. 把範本複製到預設路徑。
3. `chmod 600`——檔案含個人隱私，保持僅擁有者可讀寫。
4. 填寫 `[accounts.<name>]`——鍵為帳戶使用者名稱（即 thread URL / library 中的
   username）；設定 `display_name`、`email`、`user_id`，並選定 `default_account`。
5. 填寫 `[bot_space]`——`pplx-ask` 發問完成後執行緒的集中收納處（可經
   `pplx-ask space-create` 實際建立）。

**自動替代方案：**`pplx-export init` 可為你推導該檔案——列舉瀏覽器中各帳戶
的工作階段 cookie，逐個探測 `/api/auth/session` 取得 email / 顯示名稱，把
`default_account` 設為目前活躍帳戶，按標題比對 BOT 空間，並以 0600 權限
原子寫入 TOML（已存在的檔案僅 `--force` 才覆蓋）。

```bash
pplx-export init                     # 发现账户，写入默认配置路径
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --bot-title TITLE   # 匹配/创建其他标题的空间（默认 BOT）
pplx-export init --config /path/to/config.toml   # 写入自定义路径
```

旗標說明：`--force` 覆蓋已存在的設定；`--create-bot-space [标题]` 在無標題比對時
經 API 建立空間（對帳戶的一次寫入操作；附明確標題時比對與建立均使用該標題）；
`--bot-title TITLE` 同時用於比對與建立。注意：與其他所有命令不同，`init` 的 `--config` 是**寫入**路徑而非
載入路徑。完整說明見 [pplx-export → init](pplx-export.md#init)。

完整欄位說明見[設定](configuration.md)。

**載入優先順序**（從高到低）：

| # | 來源 |
|---|------|
| 1 | `--config PATH` |
| 2 | 環境變數 `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml`（預設） |

!!! note "設定缺失時"
    未指定 `--account` 的命令以降級模式執行——email 歸屬檢查跳過並 warning
    （離線命令不受影響）；明確 `--account` 會報錯並指向 `config.example.toml`。
    `--account` 未給時取設定中的 `default_account`。

<a id="选择-cookie-通道" data-pplx-source-anchor="true"></a>
## 選擇 cookie 通道

憑證來自本機瀏覽器已登入的 Perplexity 工作階段 cookie，經 `browser_cookie3` 讀取——
含多帳戶令牌列舉與自動切換。共四條通道：

| 通道 | 用法 | 說明 |
|------|------|------|
| auto-detect（預設） | 無需參數 | 先用 12h 新鮮快取，再依 edge→chrome→firefox→safari 順序探測瀏覽器庫 |
| 指定瀏覽器 | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| cookie 檔案 | `--cookies /path/to/cookies.txt` | Netscape cookie 檔案或匯出的 JSON |
| WebBridge | `--transport webbridge` | 頁面上下文 fetch——回退通道，需明確指定 |

Linux 下 snap 與 flatpak 安裝的瀏覽器同樣可 auto-detect——其 profile 路徑已納入
內建登錄檔。完整的 Linux 矩陣（keyring、桌面環境、發行版套件）見
[故障排除 → Linux cookie 解密](troubleshooting.md#linux-cookie-解密)。

```bash
pplx-export export <thread_url>                                 # 默认：auto-detect 浏览器库
pplx-export export <thread_url> --cookies-from edge             # 指定从某个浏览器导入
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # 用 cookie 文件
pplx-export export <thread_url> --transport webbridge           # WebBridge 页面上下文（显式回退）
```

取得 cookie 後會呼叫 `/api/auth/session` 列印目前帳戶電子郵件，便於確認帳戶是否正確
——`--account` 與 cookie 帳戶不一致時請留意。transport/憑證設計詳見
[發問與帳戶](../architecture/ask-and-accounts.md)。

<a id="首次运行" data-pplx-source-anchor="true"></a>
## 首次執行

```bash
pplx-export index --account alice     # 拉取 library 索引
pplx-export export <thread_url>       # 导出单线程
pplx-export batch --account alice     # 批量（默认增量早停；--full 全量兜底）
pplx-export re-render --dry-run       # 离线重渲，零网络
```

1. **`index`** 拉取帳戶的 library 索引——`batch` 等帳戶級命令的入口。
2. **`export`** 端到端歸檔單個執行緒：將原始回應（`raw_*.json`）與 Markdown
   一併保留，之後可離線重新渲染。
3. **`batch`** 全庫掃描：剩餘執行緒全部已歸檔即提前停止（增量早停），斷點續跑，
   `--full` 全量兜底。詳見[增量同步](incremental-sync.md)。
4. **`re-render --dry-run`** 驗證離線鏈路：僅憑本地 raw 檔案重建
   `conversation.md` + `turns/`，零網路。去掉 `--dry-run` 才真正寫入磁碟。見
   [離線操作](../architecture/offline-operations.md)。

跑通之後，`pplx-ask ask "<prompt>"` 可串流發問並自動歸檔產生的執行緒——見
[pplx-ask](pplx-ask.md)。

<a id="归档落盘位置" data-pplx-source-anchor="true"></a>
## 歸檔儲存位置

歸檔預設寫入 `./web_archive/`（`--out` 可覆蓋）：每個執行緒一個目錄。

| 路徑 | 內容 |
|------|------|
| `conversation.md`、`turns/` | 渲染後的對話 |
| `thread.json` | 執行緒中繼資料 + interruptions 登記 |
| `sources.md` / `sources.json` | 引用文獻 |
| `report.md` | 深研 / 委員會 / study 報告 |
| `assets/` | 下載的資產（computer 模式） |
| `raw_*.json` | 保留的原始 API 回應——成功歸檔無需重新抓取即可離線重新渲染 |

完整目錄慣例見[歸檔佈局](archive-layout.md)。

## 下一步

- 遇到問題？→ [故障排除](troubleshooting.md)
- 逐命令參考 → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [維護命令](maintenance-commands.md)
- 五種對話模式 → [模式](modes.md)
