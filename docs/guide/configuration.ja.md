---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/configuration.zh-CN.md"
translation_source_sha256: "7b819e8d951b62560d6b4b90885f0ebf8e82ed0313bc56d655126c24cf75045f"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="配置" data-pplx-source-anchor="true"></a>
# 設定

pplx-export は、ID データ（アカウントレジストリ：表示名、ログインメール、ユーザー ID）と BOT スペースを、リポジトリ外のユーザーレベル TOML ファイルに保存します。このページでは、そのファイルの場所、すべてのフィールド、ファイルがない場合の動作、およびレジストリがマルチアカウント Cookie 処理をどのように駆動するかについて説明します。

<a id="为什么配置外置在仓库之外" data-pplx-source-anchor="true"></a>
## なぜ設定をリポジトリの外に置くのか

アカウントレジストリと BOT スペースは個人のプライバシーデータであり、リポジトリに**決してコミットしません**（`pplx_export/config.py:7-12`）。リポジトリにはプレースホルダテンプレート `config.example.toml` のみが付属しています。実際の値はあなたのプライベートコピーに書き込まれます。ツールに必要なその他のもの（サイトドメイン、API URL、デフォルトのアーカイブルート）はコード定数（`pplx_export/config.py:50-58`）であり、ユーザー設定には属しません。

TOML は ID データのみを保持します。Cookie ソースとデータパスの選択は、呼び出しごとの CLI フラグであり、設定フィールドではありません。[CLI フラグであり設定フィールドではない](#cli-标志而非配置字段) を参照してください。

<a id="位置与加载优先级" data-pplx-source-anchor="true"></a>
## 場所と読み込み優先順位

`configure()`（`pplx_export/config.py:113`）は、次の優先順位で設定パスを解決します（`pplx_export/config.py:95-110`）：

| 優先順位 | ソース | 明示的指定とみなすか |
|---|---|---|
| 1 | `--config PATH` CLI フラグ | はい |
| 2 | 環境変数 `PPLX_EXPORT_CONFIG` | はい |
| 3 | `~/.config/pplx-export/config.toml`（デフォルトパス） | いいえ |

「明示的」はファイルがない場合のエラー動作に影響します。[設定がない場合：縮退モード](#配置缺失降级模式) を参照してください。両方の CLI エントリポイントは、引数解析後に strict モードで再読み込みします（`pplx_export/cli.py:223`、`pplx_export/ask_cli.py:278`）。インポート時の読み込み（`pplx_export/config.py:174-179`）はフォールトトレラントであるため、パッケージをインポートするだけではファイルがなくても失敗しません。

<a id="创建你的配置" data-pplx-source-anchor="true"></a>
## 設定ファイルを作成する

!!! tip "自動的な代替手段"
    `pplx-export init` はこのファイルを自動生成できます。ブラウザの Cookie からログイン済みアカウントを検出し、0600 パーミッションで TOML を書き込みます。[pplx-export → init](pplx-export.md#init) を参照してください。

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

プレースホルダのスタイル：`alice`/`bob` は架空のアカウントユーザー名、メールは `example.com`、UUID は全ゼロの `00000000-0000-4000-8000-…` 形式です。実際のファイルでは、テーブルキーは**実際のアカウントユーザー名**でなければなりません。これはスレッド URL やライブラリに表示されるものです。

!!! warning "プライベートに保つ"
    実際の設定には個人データ（メール、ユーザー ID）が含まれます。パーミッション `0o600` を推奨します。git リポジトリにコミットしないでください（`config.example.toml:4-6`）。

<a id="字段参考" data-pplx-source-anchor="true"></a>
## フィールドリファレンス

<a id="顶层" data-pplx-source-anchor="true"></a>
### トップレベル

| フィールド | 型 | 意味 |
|---|---|---|
| `default_account` | string | `[accounts.<name>]` テーブルのキー。`--account` が指定されていない場合に使用されます（`pplx_export/commands/common.py:84-85`）。空/欠落 = 縮退モード。 |
| `archive_root` | string | オプション。アーカイブ出力ルート。`--out` のフォールバックとして、日常的なコマンドで `--out` を省略できます。優先順位：`--out` > `archive_root` > `./web_archive`（`pplx_export/config.py`、`ARCHIVE_ROOT` で読み込み；`cli.py` / `ask_cli.py` で解析）。`~` は展開されます。 |
| `[models]`（テーブル） | table | **機械管理、手書き不可。** リフレッシュ可能なモデルディレクトリ。`pplx-ask models --refresh` によって書き込まれ、`pplx-export init` によってシードされます。`pplx_export/sites/perplexity/platform.py` の固定フォールバックを上書きします。キー：`last_refreshed`（UTC）、`source_version`、`auto_refresh`（bool）、`mode_defaults`、`council_defaults`、`search_models`、および完全な `[models.catalog]`（`id → {label, provider, mode}`）。リクエストはこれを読み取ります（`platform.py` をフォールバックとして）。7 日 TTL でリフレッシュ通知を表示するか、`auto_refresh = true` 時に自動リフレッシュします。書き戻しは `tomlkit`（実行時依存関係）を経由してラウンドトリップし、他のテーブルとコメントを保持し、`0600` を維持します。 |

### `[accounts.<name>]`

アカウントごとに 1 つのテーブル。`<name>` はアカウントのユーザー名です。レジストリは、ユーザー名をキーとする 3 つの dict に読み込まれます：`ACCOUNT_DISPLAY_NAMES`、`ACCOUNT_EMAIL`、`ACCOUNT_UID`（`pplx_export/config.py:65-75`）。

| フィールド | 型 | 必須 | 意味 |
|---|---|---|---|
| `display_name` | string | いいえ | 完全な表示名。アーカイブディレクトリの命名に使用されます（`web_archive/<显示名>/…`）。デフォルトはユーザー名自体にフォールバックします。[アーカイブレイアウト](archive-layout.md) を参照してください。 |
| `email` | string | 推奨 | ログインメール。transport はこれを使用して Cookie の所有権を検証し、「アカウント B のエクスポートがアカウント A のセッションで行われる」ことを防ぎます（`pplx_export/config.py:69-72`）。一致しない場合、ブラウザ内のアカウントセッショントークンを自動的に列挙して切り替えます。[マルチアカウント Cookie モデル](#多账户-cookie-模型) を参照してください。 |
| `user_id` | string | `pplx-ask` テレメトリに必要 | アカウント uid。スレッド表示テレメトリに必要です（`pplx_export/config.py:73-75`）。`GET /api/auth/linked-accounts` を介して確認できます。このエンドポイントは、ログイン済みアカウントごとに `user_id` / `email` / `display_name` を返します。[API 認証](../reference/api/api-authentication.md) を参照してください。 |

### `[bot_space]`

BOT スペースは、`pplx-ask` が質問を完了した後のスレッドの集中保管場所です（`pplx_export/config.py:76-79`）。スペース自体は `pplx-ask space-create` を介して実際に作成でき（[pplx-ask](pplx-ask.md) を参照）、ここに登録します。

| フィールド | 型 | 意味 |
|---|---|---|
| `uuid` | string | スペース UUID。`pplx-ask` は完了したスレッドをここに移動します（`pplx_export/ask_cli.py:156-158`）。空の場合は移動手順をスキップします。 |
| `slug` | string | スペースの URL スラッグ。`BOT_SPACE_SLUG` に読み込まれます（`pplx_export/config.py:79`）。実行時に CLI はこれを読み取りません。フィクスチャメンテナンスツールがこれを消費し、それに基づいて ID 置換ペアを構築します（`tests/scrub_fixtures.py:446-447`）。 |

<a id="cli-标志而非配置字段" data-pplx-source-anchor="true"></a>
### CLI フラグであり設定フィールドではない

TOML にはパスや Cookie 設定はありません。これらは呼び出しごとに選択されます：

| 関心事 | 設定場所 |
|---|---|
| 設定ファイルパス | `--config PATH`、または `PPLX_EXPORT_CONFIG` |
| Cookie ソース | `--cookies-from BROWSER` / `--cookies FILE` |
| データパス | `--transport cookie\|webbridge`（`pplx-export` のみ；デフォルト `cookie`） |
| 起動時アカウント検証をスキップ | `--skip-auth-check`（両方のエントリポイント）——[マルチアカウント Cookie モデル](#多账户-cookie-模型) を参照 |

完全なフラグリファレンスは [pplx-export](pplx-export.md) を参照してください。

<a id="配置缺失降级模式" data-pplx-source-anchor="true"></a>
## 設定がない場合：縮退モード

何も読み込まれなかった場合、モジュールレベルのレジストリは空のままで、`LOADED_CONFIG_PATH` は `None` になります（`pplx_export/config.py:83-85`）。シナリオごとの動作（`resolve_cli_account`、`pplx_export/commands/common.py:51-90`）：

| シナリオ | 動作 |
|---|---|
| デフォルトパスに設定なし、`--account` 未指定 | 縮退モード：warning を記録し、コマンドはプレースホルダアカウント（`username='default'`）で実行されます。メール所有権検証はスキップされます。日常的なオフラインコマンドは影響を受けません（`pplx_export/commands/common.py:86-90`）。 |
| 設定なし、明示的な `--account` | `SystemExit`、検索順序を示し、`config.example.toml` を指します（`pplx_export/commands/common.py:67-74`）。 |
| 設定は読み込み済み、`--account` 未登録 | `SystemExit`、読み込まれたファイルパスを示し、`[accounts.<name>]` の追加を要求します（`pplx_export/commands/common.py:77-82`）。 |
| 明示的なパス（`--config` / 環境変数）が存在しない | strict モードで `ConfigError` をスローします（`pplx_export/config.py:140-146`）。 |
| ファイルは存在するが解析に失敗 | 常に `ConfigError` をスローします——設定の破損は黙って縮退すべきではありません（`pplx_export/config.py:147-150`）。 |
| `--account` 未指定、設定は読み込み済み | `default_account` を取得します（`pplx_export/commands/common.py:84-85`）。 |

「オフラインコマンド」の対象範囲と、縮退実行とアーカイブの相互作用については、[オフライン操作](../architecture/offline-operations.md) を参照してください。

<a id="多账户-cookie-模型" data-pplx-source-anchor="true"></a>
## マルチアカウント Cookie モデル

複数のアカウントが同じブラウザにログインしている場合、Cookie ストアは**アカウントごとに** 1 つのセッション Cookie を保持します。設定内の `email` フィールドは、ツールにどれが必要かを伝えます：

- ログイン済みアカウントごとに 1 つの `__Secure-pplx.session.<uid>` Cookie があります（`ACCOUNT_SESSION_PREFIX`、`pplx_export/core/cookies/loaders.py:171`）。`<uid>` サフィックスはアカウントの `user_id` です。
- **現在アクティブな**アカウントは、トークンが現在 `__Secure-next-auth.session-token` に書き込まれているアカウントです（`ACTIVE_SESSION_COOKIE`、`pplx_export/core/cookies/loaders.py:172`）。アカウントの切り替え = ターゲットアカウントのアカウント別 Cookie 値をその Cookie に書き込むことです。ブラウザ UI は必要ありません（`pplx_export/core/cookies/loaders.py:180-187`）。
- 起動時に transport は `GET https://www.perplexity.ai/api/auth/session` をプローブし、返されたメールを `accounts.<name>.email` と比較します（`pplx_export/commands/common.py:126-130`）。
- 一致しない場合、`_try_switch_account`（`pplx_export/commands/common.py:190-215`）は `list_account_tokens`（`pplx_export/core/cookies/loaders.py:175-206`、優先 `www.` サブドメインのエントリ）を介してブラウザ内のすべてのアカウントトークンを列挙し、それぞれを `__Secure-next-auth.session-token` に書き込んで試し、最初に一致したもので transport を再構築します。
- すべて一致しない場合、コマンドは終了し、2 つのメールを表示して、ブラウザでターゲットアカウントにログインするよう求めます（`pplx_export/commands/common.py:142-145`）。[トラブルシューティング](troubleshooting.md) を参照してください。
- `email` が登録されていないアカウントは、検証なしで通過し、正しいアカウントでブラウザにログインしていることを自分で確認するよう warning を表示します（`pplx_export/commands/common.py:146-149`）。

完全な切り替えフローとセッションエンドポイントのセマンティクスについては、[質問とアカウント](../architecture/ask-and-accounts.md) および [API 認証](../reference/api/api-authentication.md) を参照してください。

**検証のスキップ（`--skip-auth-check`）。** 上記の起動時セッションプローブは、数秒（ネットワークが悪い場合は数分）をかけて「アカウント B を A として使用する」という所有権保護を提供します。ブラウザにターゲットアカウントでログインしていることが確実な場合、`--skip-auth-check`（`pplx-export` と `pplx-ask` で共有）はこのプローブを完全にスキップし、直接作業を開始します（`pplx_export/commands/common.py`、`make_transport`）：

- 起動時に `GET /api/auth/session` を送信しません。ネットワークの変動により、最初の実際のリクエストの前に長時間の待機が発生することはなくなります（現在はハートビートがあります）。
- ツールは現在ログインしているアカウントを信頼します。上記の起動時メール所有権検証とマルチアカウント自動切り替えは実行されません。
- **遅延セーフティネット**：`batch` では、一般的なエクスポートエラーが蓄積（3 回失敗）した後、1 回限りのアカウント検証を実行し、結果を通知します。Cookie の有効期限切れ、アカウントとターゲットの不一致、またはアカウントが正常（エラーがネットワーク/レート制限によるものであり、認証によるものではないことを示す）のいずれかです（`pplx_export/commands/common.py`、`report_account_status`；`pplx_export/commands/batch_cmd.py`）。
- **トレードオフ**：遅延検証は Cookie の有効期限切れをキャッチできますが、**アカウントは有効だが間違って使用されており、エラーなしでエクスポートできる**ケースはキャッチできません。`--skip-auth-check` を使用する場合は、ターゲットアカウントでログインしていることを自分で確認する必要があります。

ログインが正しいことがわかっている場合の高速で無人実行に適しています。起動時の所有権保護や自動アカウント切り替えに依存する場合は、これを使用しないでください。

<a id="cookie-缓存" data-pplx-source-anchor="true"></a>
## Cookie キャッシュ

検証が成功すると、解析された Cookie はキャッシュされ、以降の実行ではブラウザにアクセスしません：

| プロパティ | 値 |
|---|---|
| パス | `<归档根>/index/.cookies.json`——`--out`（`pplx_export/commands/common.py:111`）に従う |
| 鮮度期間 | 12 時間（`CACHE_MAX_AGE_S = 12 * 3600`、`pplx_export/core/cookies/cache.py:22`）；期限切れまたは破損したキャッシュはキャッシュなしとして扱われる |
| 内容 | `fetched_at`、`source`、`account_email`、`cookies`（`pplx_export/core/cookies/cache.py:62-66`） |
| 書き込み | アトミック書き込み：一時ファイルを `0o600` で作成後、`os.replace`（`pplx_export/core/cookies/cache.py:49-67`） |
| Git | `.gitignore` によって無視済み（`**/index/.cookies.json`） |

Cookie 解析順序（`cookies.resolve`、`pplx_export/core/cookies/loaders.py:270-302`）：明示的な `--cookies-from` → 明示的な `--cookies` ファイル → 新鮮なキャッシュ → 自動検出ブラウザ（edge → chrome → firefox → safari）。アカウント検証が成功するたびにキャッシュがリフレッシュされます（`pplx_export/commands/common.py:150`）。

<a id="保护你的文件" data-pplx-source-anchor="true"></a>
## ファイルを保護する

- `config.toml` に対して `chmod 600` を実行します。個人データ（メール、ユーザー ID）が含まれています。
- Cookie キャッシュはツールによって `0o600` で書き込まれます。セッション Cookie はログイン資格情報と同等です。
- `--cookies` 用の Cookie ファイルを手動で作成する場合も、`chmod 600` を実行します。

<a id="认证失败时" data-pplx-source-anchor="true"></a>
## 認証に失敗した場合

Cookie の期限切れ、自動切り替えで見つからないアカウント、ブラウザのキーチェーン権限エラー、およびその他の認証失敗については、[トラブルシューティング](troubleshooting.md) を参照してください。
