---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/configuration.zh-CN.md"
translation_source_sha256: "0e237ed1c2465d1d1496878708fadd64d1f0459788f85ba8063dffbca1c5329d"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="配置" data-pplx-source-anchor="true"></a>
# 設定

pplx-export は、アカウントレジストリ（表示名、ログインメール、ユーザーID）とBOTスペースを、リポジトリ外のユーザーレベルTOMLファイルに保存します。このページでは、そのファイルの場所、すべてのフィールド、ファイルがない場合の動作、およびレジストリがマルチアカウントCookie処理をどのように駆動するかを説明します。

<a id="为什么配置外置在仓库之外" data-pplx-source-anchor="true"></a>
## なぜ設定をリポジトリの外に置くのか

アカウントレジストリとBOTスペースは個人のプライベートデータであり、**決して**リポジトリにコミットしてはなりません（`pplx_export/config.py:7-12`）。リポジトリにはプレースホルダテンプレート `config.example.toml` のみが付属します。実際の値はあなたのプライベートコピーに書き込まれます。ツールに必要なその他の内容（サイトドメイン、API URL、デフォルトのアーカイブルート）はコード定数（`pplx_export/config.py:50-58`）であり、ユーザー設定には属しません。

TOMLはIDデータのみを保持します。Cookieソースとデータパスの選択は、呼び出しごとのCLIフラグであり、設定フィールドではありません。[CLIフラグであって設定フィールドではない](#cli-标志而非配置字段)を参照してください。

<a id="位置与加载优先级" data-pplx-source-anchor="true"></a>
## 場所と読み込み優先順位

`configure()`（`pplx_export/config.py:113`）は、以下の優先順位で設定パスを解決します（`pplx_export/config.py:95-110`）：

| 優先順位 | ソース | 明示的に指定されたか |
|---|---|---|
| 1 | `--config PATH` CLIフラグ | はい |
| 2 | 環境変数 `PPLX_EXPORT_CONFIG` | はい |
| 3 | `~/.config/pplx-export/config.toml`（デフォルトパス） | いいえ |

「明示的」は、ファイルがない場合のエラー動作に影響します。[設定がない場合：縮退モード](#配置缺失降级模式)を参照してください。両方のCLIエントリポイントは、引数解析後にstrictモードで再読み込みします（`pplx_export/cli.py:223`、`pplx_export/ask_cli.py:278`）。インポート時の読み込み（`pplx_export/config.py:174-179`）はフォールトトレラントであるため、パッケージをインポートするだけではファイルがなくても失敗しません。

<a id="创建你的配置" data-pplx-source-anchor="true"></a>
## 設定を作成する

!!! tip "自動代替手段"
    `pplx-export init` はこのファイルを自動生成できます。ブラウザのCookieからログイン済みアカウントを検出し、0600パーミッションでTOMLを書き込みます。[pplx-export → init](pplx-export.md#init)を参照してください。

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

次に、そのコピーを編集します。テンプレートはすべてプレースホルダです。構造をそのままコピーし、各値を置き換えてください：

```toml
# --account 未给出时使用的默认账户（对应下方 [accounts.<名>] 的键）
default_account = "alice"

# 账户注册表：键 = 账户用户名（thread URL / library 中的 username）
[accounts.alice]
# 完整显示名：用于归档目录命名（web_archive/<显示名>/…）
display_name = "Alice Example"
# 登录 email：校验 cookie 归属
email = "alice@example.com"
# 账户 uid（thread viewed 遥测需要）
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT 空间：pplx-ask 发问完成后线程的集中收纳处
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

プレースホルダのスタイル：`alice`/`bob` は架空のアカウントユーザー名、メールは `example.com`、UUIDは全ゼロの `00000000-0000-4000-8000-…` 形式です。実際のファイルでは、テーブルキーは**実際のアカウントユーザー名**でなければなりません。これはスレッドURLやライブラリに表示されるものです。

!!! warning "プライベートに保つ"
    実際の設定には個人データ（メール、ユーザーID）が含まれます。パーミッションは `0o600` を推奨します。gitリポジトリにコミットしないでください（`config.example.toml:4-6`）。

<a id="字段参考" data-pplx-source-anchor="true"></a>
## フィールドリファレンス

<a id="顶层" data-pplx-source-anchor="true"></a>
### トップレベル

| フィールド | 型 | 意味 |
|---|---|---|
| `default_account` | string | ある `[accounts.<name>]` テーブルのキー。`--account` が指定されていない場合に使用されます（`pplx_export/commands/common.py:84-85`）。空/欠落 = 縮退モード。 |
| `archive_root` | string | オプション。アーカイブ出力ルート。`--out` のフォールバックとして、日常的なコマンドでは `--out` を省略できます。優先順位：`--out` > `archive_root` > `./web_archive`（`pplx_export/config.py`、`ARCHIVE_ROOT` で読み込み；`cli.py` / `ask_cli.py` で解析）。`~` は展開されます。 |

### `[accounts.<name>]`

アカウントごとに1つのテーブル。`<name>` はアカウントのユーザー名です。レジストリは、ユーザー名をキーとする3つのdictに読み込まれます：`ACCOUNT_DISPLAY_NAMES`、`ACCOUNT_EMAIL`、`ACCOUNT_UID`（`pplx_export/config.py:65-75`）。

| フィールド | 型 | 必須 | 意味 |
|---|---|---|---|
| `display_name` | string | いいえ | 完全な表示名。アーカイブディレクトリの命名に使用されます（`web_archive/<显示名>/…`）。デフォルトはユーザー名自体にフォールバックします。[アーカイブレイアウト](archive-layout.md)を参照してください。 |
| `email` | string | 推奨 | ログインメール。transportはこれを使用してCookieの所有権を検証し、「アカウントBのエクスポートがアカウントAのセッションを使用する」ことを防ぎます（`pplx_export/config.py:69-72`）。一致しない場合、ブラウザ内のアカウントセッショントークンを自動的に列挙して切り替えます。[マルチアカウントCookieモデル](#多账户-cookie-模型)を参照してください。 |
| `user_id` | string | `pplx-ask` テレメトリに必要 | アカウントuid。スレッド表示テレメトリに必要です（`pplx_export/config.py:73-75`）。`GET /api/auth/linked-accounts` で確認できます。このエンドポイントは、ログイン済みの各アカウントの `user_id` / `email` / `display_name` を返します。[API認証](../reference/api/api-authentication.md)を参照してください。 |

### `[bot_space]`

BOTスペースは、`pplx-ask` が質問を完了した後のスレッドを集中管理する場所です（`pplx_export/config.py:76-79`）。スペース自体は `pplx-ask space-create` で実際に作成し（[pplx-ask](pplx-ask.md)を参照）、ここに登録します。

| フィールド | 型 | 意味 |
|---|---|---|
| `uuid` | string | スペースUUID。`pplx-ask` は完了したスレッドをここに移動します（`pplx_export/ask_cli.py:156-158`）。空の場合は移動ステップをスキップします。 |
| `slug` | string | スペースのURLスラッグ。`BOT_SPACE_SLUG` に読み込まれます（`pplx_export/config.py:79`）。ランタイムCLIはこれを読み取りません。フィクスチャメンテナンスツールが消費し、それに基づいてID置換ペアを構築します（`tests/scrub_fixtures.py:446-447`）。 |

<a id="cli-标志而非配置字段" data-pplx-source-anchor="true"></a>
### CLIフラグであって設定フィールドではない

TOMLにはパスやCookieの設定は一切ありません。これらは呼び出しごとに選択します：

| 関心事 | 設定場所 |
|---|---|
| 設定ファイルパス | `--config PATH`、または `PPLX_EXPORT_CONFIG` |
| Cookieソース | `--cookies-from BROWSER` / `--cookies FILE` |
| データパス | `--transport cookie\|webbridge`（`pplx-export` のみ；デフォルト `cookie`） |
| 起動時アカウント検証をスキップ | `--skip-auth-check`（両方のエントリポイント）——[マルチアカウントCookieモデル](#多账户-cookie-模型)を参照 |

完全なフラグリファレンスは [pplx-export](pplx-export.md) を参照してください。

<a id="配置缺失降级模式" data-pplx-source-anchor="true"></a>
## 設定がない場合：縮退モード

何も読み込まれなかった場合、モジュールレベルのレジストリは空のままで、`LOADED_CONFIG_PATH` は `None` になります（`pplx_export/config.py:83-85`）。シナリオごとの動作（`resolve_cli_account`、`pplx_export/commands/common.py:51-90`）：

| シナリオ | 動作 |
|---|---|
| デフォルトパスに設定なし、`--account` なし | 縮退モード：warningを記録し、プレースホルダアカウント（`username='default'`）でコマンドを実行。メール所有権検証はスキップ。日常的なオフラインコマンドは影響を受けません（`pplx_export/commands/common.py:86-90`）。 |
| 設定なし、明示的な `--account` | `SystemExit`、検索順序を示し、`config.example.toml` を指します（`pplx_export/commands/common.py:67-74`）。 |
| 設定は読み込まれているが、`--account` が登録されていない | `SystemExit`、読み込まれたファイルパスを示し、`[accounts.<name>]` の追加を要求します（`pplx_export/commands/common.py:77-82`）。 |
| 明示的なパス（`--config` / 環境変数）が存在しない | strictモードで `ConfigError` をスローします（`pplx_export/config.py:140-146`）。 |
| ファイルは存在するが解析に失敗 | 常に `ConfigError` をスロー——設定の破損は静かに縮退すべきではありません（`pplx_export/config.py:147-150`）。 |
| `--account` なし、設定は読み込まれている | `default_account` を使用します（`pplx_export/commands/common.py:84-85`）。 |

「オフラインコマンド」の範囲、および縮退実行とアーカイブの相互作用については、[オフライン操作](../architecture/offline-operations.md)を参照してください。

<a id="多账户-cookie-模型" data-pplx-source-anchor="true"></a>
## マルチアカウントCookieモデル

複数のアカウントが同じブラウザにログインしている場合、Cookieストアは**アカウントごとに**1つのセッションCookieを保存します。設定内の `email` フィールドは、ツールにどれが必要かを伝えます：

- ログイン済みの各アカウントには、1つの `__Secure-pplx.session.<uid>` Cookieがあります（`ACCOUNT_SESSION_PREFIX`、`pplx_export/core/cookies/loaders.py:171`）。`<uid>` サフィックスはアカウントの `user_id` です。
- **現在アクティブな**アカウントは、トークンが現在 `__Secure-next-auth.session-token` に書き込まれているアカウントです（`ACTIVE_SESSION_COOKIE`、`pplx_export/core/cookies/loaders.py:172`）。アカウントの切り替え = ターゲットアカウントのアカウント別Cookie値をそのCookieに書き込むこと。ブラウザUIは不要です（`pplx_export/core/cookies/loaders.py:180-187`）。
- 起動時にtransportは `GET https://www.perplexity.ai/api/auth/session` をプローブし、返されたメールを `accounts.<name>.email` と比較します（`pplx_export/commands/common.py:126-130`）。
- 一致しない場合、`_try_switch_account`（`pplx_export/commands/common.py:190-215`）は `list_account_tokens`（`pplx_export/core/cookies/loaders.py:175-206`、優先的に `www.` サブドメインのエントリ）を介してブラウザ内のすべてのアカウントトークンを列挙し、それぞれを `__Secure-next-auth.session-token` に書き込んで試し、最初に一致したものでtransportを再構築します。
- すべて一致しない場合、コマンドは終了し、2つのメールをリストアップして、ブラウザでターゲットアカウントにログインするよう求めます（`pplx_export/commands/common.py:142-145`）。[トラブルシューティング](troubleshooting.md)を参照してください。
- `email` が登録されていないアカウントは、検証なしで通過し、ブラウザで正しいアカウントにログインしていることを自分で確認するようwarningを出します（`pplx_export/commands/common.py:146-149`）。

完全な切り替えフローとセッションエンドポイントのセマンティクスについては、[質問とアカウント](../architecture/ask-and-accounts.md)および[API認証](../reference/api/api-authentication.md)を参照してください。

**検証をスキップ（`--skip-auth-check`）。** 上記の起動時セッションプローブは、数秒（ネットワークが悪い場合は数分）をかけて、「アカウントBをAとして使用する」という所有権保護を提供します。ブラウザがターゲットアカウントにログインしていると確信している場合、`--skip-auth-check`（`pplx-export` と `pplx-ask` で共有）はこのプローブを完全にスキップし、直接作業を開始します（`pplx_export/commands/common.py`、`make_transport`）：

- 起動時に `GET /api/auth/session` を送信しません。ネットワークの変動により、最初の実際のリクエストの前に長時間の無音待機が発生しなくなります（現在はハートビートがあります）。
- ツールは現在ログインしているアカウントを信頼します。上記の起動時メール所有権検証とマルチアカウント自動切り替えは実行されません。
- **遅延セーフティネット**：`batch` では、一般的なエクスポートエラーが累積（3回失敗）した後、1回限りのアカウント検証を実行し、結果を通知します——Cookieの有効期限切れ、アカウントとターゲットの不一致、またはアカウント正常（エラーがネットワーク/レート制限によるものであり、認証によるものではないことを示す）（`pplx_export/commands/common.py`、`report_account_status`；`pplx_export/commands/batch_cmd.py`）。
- **トレードオフ**：遅延検証はCookieの有効期限切れをキャッチできますが、**アカウントは有効だが間違っている**場合でエクスポートがエラーなく成功する状況はキャッチできません。`--skip-auth-check` を使用する場合は、ログインしているアカウントがターゲットであることを自分で確認する必要があります。

ログインが正しいことがわかっている場合の高速で無人実行に適しています。起動時の所有権保護や自動アカウント切り替えに依存する場合は、これを使用しないでください。

<a id="cookie-缓存" data-pplx-source-anchor="true"></a>
## Cookieキャッシュ

検証が成功すると、解析されたCookieがキャッシュされ、以降の実行ではブラウザにアクセスしません：

| プロパティ | 値 |
|---|---|
| パス | `<归档根>/index/.cookies.json`——`--out`（`pplx_export/commands/common.py:111`）に従う |
| 新鮮期間 | 12時間（`CACHE_MAX_AGE_S = 12 * 3600`、`pplx_export/core/cookies/cache.py:22`）。期限切れまたは破損したキャッシュはキャッシュなしとして扱われる |
| 内容 | `fetched_at`、`source`、`account_email`、`cookies`（`pplx_export/core/cookies/cache.py:62-66`） |
| 書き込み | アトミック書き込み：一時ファイルを `0o600` で作成し、`os.replace`（`pplx_export/core/cookies/cache.py:49-67`） |
| Git | `.gitignore` でカバー済み（`**/index/.cookies.json`） |

Cookie解析順序（`cookies.resolve`、`pplx_export/core/cookies/loaders.py:270-302`）：明示的な `--cookies-from` → 明示的な `--cookies` ファイル → 新鮮なキャッシュ → 自動検出ブラウザ（edge → chrome → firefox → safari）。アカウント検証が成功するたびにキャッシュが更新されます（`pplx_export/commands/common.py:150`）。

<a id="保护你的文件" data-pplx-source-anchor="true"></a>
## ファイルを保護する

- `config.toml` に対して `chmod 600` を実行します——個人データ（メール、ユーザーID）が含まれています。
- Cookieキャッシュはツールによって `0o600` で書き込まれます。セッションCookieはログイン資格情報と同等です。
- `--cookies` 用のCookieファイルを手動で作成する場合も、`chmod 600` を実行します。

<a id="认证失败时" data-pplx-source-anchor="true"></a>
## 認証に失敗した場合

Cookieの有効期限切れ、自動切り替えで見つからないアカウント、ブラウザのキーチェーン権限エラー、その他の認証失敗については、[トラブルシューティング](troubleshooting.md)を参照してください。
