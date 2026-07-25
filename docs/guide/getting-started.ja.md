---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/getting-started.zh-CN.md"
translation_source_sha256: "ea130999f3f8892de32f1a0e7eba131c868abbe632d517b80a4e234c542ca743"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="快速上手" data-pplx-source-anchor="true"></a>
# クイックスタート

新規チェックアウトから最初のローカルアーカイブまで：2つのコマンドをインストールし、ユーザーレベルの設定を作成し、Cookieチャンネルを選択し、初回エクスポートを完了します。

<a id="环境要求" data-pplx-source-anchor="true"></a>
## 環境要件

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)**——ツールのインストールとテストの実行に使用
- **Perplexity にログインしたデスクトップブラウザ**——ツールはそのセッションCookieを再利用します。設定にトークンは保存されません。

Cookieの復号には `browser_cookie3` を使用します。auto-detect は Edge、Chrome、Firefox、Safari をカバーします。Brave、Chromium、Opera、Vivaldi は `--cookies-from` で指定できます。

<a id="安装" data-pplx-source-anchor="true"></a>
## インストール

クローンは不要——git URL から直接インストール：

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI 镜像替代（如中国大陆网络环境）：
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

ローカルクローンからインストール（リポジトリルート）：

```bash
uv tool install .            # 或开发模式：uv tool install --editable .
```

インストール後、2つのコマンドが利用可能：`pplx-export`（アーカイブ）と `pplx-ask`（インタラクティブクエリ）。確認：

```bash
pplx-export --version
pplx-export --help           # 总览（含示例）；每个子命令另有专属 --help
pplx-ask --help
```

`uvx --from . pplx-export` はインストール不要で1回限り実行可能。

<a id="创建用户级配置" data-pplx-source-anchor="true"></a>
## ユーザーレベルの設定を作成

アカウントレジストリ（表示名 / email / user_id）と BOT スペースは個人のプライバシーに関わるため、**リポジトリにコミットせず**、TOML ファイルとして外部に保存します。テンプレートはリポジトリルートの `config.example.toml` にあります。

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # 含个人隐私，建议仅属主可读写
# 编辑填入真实账户值
```

1. 設定ディレクトリを作成します。
2. テンプレートをデフォルトパスにコピーします。
3. `chmod 600`——ファイルには個人のプライバシー情報が含まれるため、所有者のみ読み書き可能にします。
4. `[accounts.<name>]` を記入します——キーはアカウントのユーザー名（スレッドURL / ライブラリ内の username）です。`display_name`、`email`、`user_id` を設定し、`default_account` を選択します。
5. `[bot_space]` を記入します——`pplx-ask` の質問完了後のスレッドを集中管理する場所です（`pplx-ask space-create` で実際に作成可能）。

**自動代替案：**`pplx-export init` はこのファイルを推論できます——ブラウザ内の各アカウントのセッションCookieを列挙し、`/api/auth/session` をプローブして email / 表示名を取得し、`default_account` を現在アクティブなアカウントに設定し、タイトルで BOT スペースをマッチングし、0600 パーミッションでアトミックに TOML を書き込みます（既存のファイルは `--force` の場合のみ上書き）。

```bash
pplx-export init                     # 发现账户，写入默认配置路径
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --bot-title TITLE   # 匹配/创建其他标题的空间（默认 BOT）
pplx-export init --config /path/to/config.toml   # 写入自定义路径
```

フラグの説明：`--force` は既存の設定を上書きします。`--create-bot-space [标题]` はタイトルがマッチしない場合に API 経由でスペースを作成します（アカウントへの1回の書き込み操作。明示的なタイトルが指定された場合、マッチングと作成の両方にそのタイトルを使用）。`--bot-title TITLE` はマッチングと作成の両方に使用されます。注意：他のすべてのコマンドとは異なり、`init` の `--config` は**書き込み**パスであり、読み込みパスではありません。完全な説明は [pplx-export → init](pplx-export.md#init) を参照してください。

完全なフィールドの説明は[設定](configuration.md)を参照してください。

**読み込み優先順位**（高い順から低い順）：

| # | ソース |
|---|------|
| 1 | `--config PATH` |
| 2 | 環境変数 `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml`（デフォルト） |

!!! note "設定がない場合"
    `--account` が指定されていないコマンドは縮退モードで実行されます——email 帰属チェックはスキップされ、警告が表示されます（オフラインコマンドは影響を受けません）。明示的な `--account` はエラーとなり、`config.example.toml` を参照するよう促します。
    `--account` が指定されていない場合は、設定内の `default_account` が使用されます。

<a id="选择-cookie-通道" data-pplx-source-anchor="true"></a>
## Cookieチャンネルを選択

認証情報は、ローカルブラウザにログインしている Perplexity のセッションCookieから取得され、`browser_cookie3` 経由で読み取られます——マルチアカウントトークンの列挙と自動切り替えを含みます。合計4つのチャンネルがあります：

| チャンネル | 使用方法 | 説明 |
|------|------|------|
| auto-detect（デフォルト） | 引数不要 | 最初に12時間の新鮮なキャッシュを使用し、次に edge→chrome→firefox→safari の順でブラウザライブラリをプローブ |
| ブラウザ指定 | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| Cookieファイル | `--cookies /path/to/cookies.txt` | Netscape cookie ファイルまたはエクスポートされた JSON |
| WebBridge | `--transport webbridge` | ページコンテキスト fetch——フォールバックチャンネル。明示的に指定する必要あり |

Linux では、snap および flatpak でインストールされたブラウザも auto-detect 可能です——それらのプロファイルパスは組み込みレジストリに含まれています。完全な Linux マトリックス（キーリング、デスクトップ環境、ディストリビューションパッケージ）については、[トラブルシューティング → Linux Cookie 復号](troubleshooting.md#linux-cookie-解密) を参照してください。

```bash
pplx-export export <thread_url>                                 # 默认：auto-detect 浏览器库
pplx-export export <thread_url> --cookies-from edge             # 指定从某个浏览器导入
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # 用 cookie 文件
pplx-export export <thread_url> --transport webbridge           # WebBridge 页面上下文（显式回退）
```

Cookie を取得した後、`/api/auth/session` を呼び出して現在のアカウントのメールアドレスを表示し、アカウントが正しいことを確認します——`--account` と Cookie アカウントが一致しない場合は注意してください。transport/認証情報の設計の詳細については、[質問とアカウント](../architecture/ask-and-accounts.md) を参照してください。

<a id="首次运行" data-pplx-source-anchor="true"></a>
## 初回実行

```bash
pplx-export index --account alice     # 拉取 library 索引
pplx-export export <thread_url>       # 导出单线程
pplx-export batch --account alice     # 批量（默认增量早停；--full 全量兜底）
pplx-export re-render --dry-run       # 离线重渲，零网络
```

1. **`index`** アカウントのライブラリインデックスを取得——`batch` などのアカウントレベルコマンドのエントリポイント。
2. **`export`** 単一スレッドのエンドツーエンドアーカイブ：元のレスポンス（`raw_*.json`）と Markdown を一緒に保持し、後でオフラインで再レンダリング可能。
3. **`batch`** 全ライブラリスキャン：残りのスレッドがすべてアーカイブ済みの場合は早期停止（インクリメンタル早期停止）、中断再開可能、`--full` でフルスキャン。詳細は[インクリメンタル同期](incremental-sync.md)を参照。
4. **`re-render --dry-run`** オフラインリンクの検証：ローカルの raw ファイルのみから `conversation.md` + `turns/` を再構築、ネットワークゼロ。`--dry-run` を外すと実際にディスクに書き込みます。[オフライン操作](../architecture/offline-operations.md)を参照。

動作確認後、`pplx-ask ask "<prompt>"` でストリーミング質問を行い、生成されたスレッドを自動アーカイブできます——[pplx-ask](pplx-ask.md) を参照。

<a id="归档落盘位置" data-pplx-source-anchor="true"></a>
## アーカイブの保存場所

アーカイブはデフォルトで `./web_archive/` に書き込まれます（`--out` で上書き可能）。スレッドごとに1つのディレクトリが作成されます。

| パス | 内容 |
|------|------|
| `conversation.md`、`turns/` | レンダリングされた会話 |
| `thread.json` | スレッドメタデータ + interruptions 記録 |
| `sources.md` / `sources.json` | 引用 |
| `report.md` | 深層研究 / 委員会 / study レポート |
| `assets/` | ダウンロードされたアセット（Computer モード） |
| `raw_*.json` | 保持された元のAPIレスポンス——成功したアーカイブは再取得不要でオフライン再レンダリング可能 |

完全なディレクトリ規則については[アーカイブレイアウト](archive-layout.md)を参照してください。

<a id="下一步" data-pplx-source-anchor="true"></a>
## 次のステップ

- 問題が発生した場合？→ [トラブルシューティング](troubleshooting.md)
- コマンドごとのリファレンス → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [メンテナンスコマンド](maintenance-commands.md)
- 5つの会話モード → [モード](modes.md)
