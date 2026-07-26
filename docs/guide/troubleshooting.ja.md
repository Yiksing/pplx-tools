---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/troubleshooting.zh-CN.md"
translation_source_sha256: "dadb0d4e847c97d5c11b428f8e9b7e8ea0c5272322a5d3a6202214ba49b0c249"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="故障排查" data-pplx-source-anchor="true"></a>
# トラブルシューティング

FAQ 形式：各項目は **問題 → 原因 → 修正** の順で構成。完全なエラーセマンティクス（ステータスコード、終端状態、リトライ規律）については[レスポンスとエラー](../reference/api/api-responses-errors.md)および[レート制限とエラー](../architecture/rate-limiting-errors.md)を参照。

<a id="裸请求-api-遭遇-cloudflare-403" data-pplx-source-anchor="true"></a>
## ベアリクエスト API で Cloudflare 403

**問題**：手動 `curl` / スクリプトによる `www.perplexity.ai` の REST エンドポイントへのリクエストが 403 と Cloudflare チャレンジページを返す——ブラウザからコピーした cookie を使用しても。一方、同じエンドポイントをツール経由で使用すると正常に動作する。

**原因**：Cloudflare がサイトの前面にあり、`cf_clearance` / `__cf_bm` はブラウザの TLS フィンガープリントにバインドされている。ベアクライアントのフィンガープリントが一致しないため、チャレンジがトリガーされる。ツールが機能するのは、Python `urllib` + ブラウザからインポートした cookie + デスクトップ Chrome `User-Agent`（`pplx_export/core/http/cookie_transport.py:29`）を使用しているため。Cloudflare はレート制限の際にも 403 を返す可能性があり、その場合も同じチャレンジ形式のレスポンスとなる。

**修正**：

- ツールのトランスポートをバイパスしない。`pplx-export` / `pplx-ask` を使用して呼び出しを行い、一時的なスクリプトを書かない。
- ツール内部では、HTTP 200 だが非 JSON のレスポンスボディ（Cloudflare の通過ページ）をデータではなく転送エラーとして分類する（`pplx_export/core/http/cookie_transport.py:133`）。
- ツール内で 403 が発生し始めたら、まずペースを落とし（[レート制限](rate-limiting.md)を参照）、cookie を更新する。チャレンジが続く場合は、ブラウザで再ログインする必要がある。
- 403 には2つの側面があることに注意：Cloudflare のレート制限チャレンジ（ペースを落とせば解消）と API レベルの 403（cookie の有効期限切れ——即座にスローされ、バックオフしない。次のセクションを参照）。設計ページでは後者をマッピングしている（[rate-limiting-errors.md](../architecture/rate-limiting-errors.md)）。

背景：[API 認証](../reference/api/api-authentication.md)。

<a id="401-错误-cookie-过期" data-pplx-source-anchor="true"></a>
## 401 エラー / cookie の期限切れ

**問題**：認証エラーによりコマンドが失敗する——`pplx-export` が `AuthTransportError: 鉴权失败 401` をスローするか、`pplx-ask ask` が HTTP 401/403 の「cookie を更新」メッセージで終了する。

**原因**：セッション cookie の有効期限が切れているか、無効になっている。`401`/`403` は認証失敗として扱われ、即座にスローされる——バックオフは行われない。なぜなら、バックオフでは期限切れのセッションを回復できないため（`pplx_export/core/http/cookie_transport.py:82`；`pplx_export/core/errors.py:68`）。`batch` は連続3回の認証失敗後にフェイルファストし、無効な cookie がキュー全体を消費するのを防ぐ。

**修正**：

1. ブラウザで再ログイン（またはサイトを再度開く）して、セッション cookie を更新する。
2. ツールの cookie キャッシュを更新する。`<out>/index/.cookies.json` は12時間の有効期間内に再利用される（`pplx_export/core/cookies/cache.py:22`）ため、再ログイン後は次のいずれかを実行：
   - `--cookies-from <browser>` を指定して実行し、ブラウザからの再インポートを強制する。または
   - `<out>/index/.cookies.json` を削除し、次回の実行時に自動的に再インポートさせる。
3. 検証に成功した実行ごとにキャッシュが再保存される（`pplx_export/commands/common.py:150`）ため、通常の実行で自動的に新鮮さが保たれる。

設定の詳細：[クイックスタート](getting-started.md) · [設定](configuration.md)。

<a id="linux-cookie-解密" data-pplx-source-anchor="true"></a>
## Linux での cookie 復号

**問題**：Linux で、auto-detect（または `--cookies-from chrome` など）がブラウザの cookie ストアを読み取れない。ブラウザはログイン状態であるにもかかわらず。

**仕組み**：Linux 上の Chromium 系ブラウザは、OS のキーリングに保存された鍵を使用して cookie データベースを暗号化し、実行時に Secret Service D-Bus API を介してその鍵を取得する。`browser_cookie3` は純粋な Python の `jeepney` を介して D-Bus にアクセスする——これはツールとともに Linux にインストールされ、追加設定は不要——キーリングが応答しない場合は、レガシーな `peanuts` パスワードにフォールバックする。このパスワードは、Chrome が以前にキーリングなしで書き込んだ cookie のみを復号できる。キーリングは存在するが、D-Bus クエリ自体がトランスポート層で失敗する場合（セッションバスが匿名アクセスを拒否するなど）、`browser_cookie3` 自身のフォールバックチェーンは機能しない。ツールはこの状況を認識し、キーリングをバイパスして再試行し、Chromium のデフォルトパスワード——つまり Chromium がキーリングなしで使用する鍵——を使用する（`pplx_export/core/cookies/loaders.py:62-104`、ロードパスは `loaders.py:136-153`）。Firefox はこれらに関与しない：その `cookies.sqlite` は暗号化されていない。

**マトリックス**：

| レベル | 状況 | 結果 |
|---|---|---|
| ブラウザ | Firefox | 摩擦なし——`cookies.sqlite` は暗号化されていない |
| ブラウザ | Chromium + キーリング到達可能 | 正常——Secret Service 経由で鍵を取得 |
| ブラウザ | Chromium + キーリングなし | `peanuts` パス——Chrome が以前にキーリングなしで書き込んだ場合のみ有効 |
| ブラウザ | Chromium + キーリング到達不能（D-Bus レベルで失敗） | ツールは自動的に Chromium デフォルトパスワードで再試行——到達性は `peanuts` パスと同じ |
| インストール方法 | ネイティブパッケージ | auto-detect（browser_cookie3 組み込みパス） |
| インストール方法 | snap / flatpak | auto-detect——組み込みプロファイルレジストリが `~/snap/<name>/...` と `~/.var/app/<app-id>/...` 下のプロファイルをカバー（`pplx_export/core/cookies/profiles.py:37-67`） |
| デスクトップ環境 | GNOME | 通常はそのまま動作（gnome-keyring） |
| デスクトップ環境 | KDE | KWallet 設定で **Use KWallet for the Secret Service interface** にチェックを入れる |
| デスクトップ環境 | ヘッドレス / 最小構成 | D-Bus セッションバスなし → `peanuts` パス |
| ディストリビューション | Debian / Ubuntu | `libsecret-1-0` + `gnome-keyring` をインストール |
| ディストリビューション | Fedora / RHEL | `libsecret` + `gnome-keyring` をインストール；最小構成 / サーバーインストールではキーリングがまったくないことが多い——最も一般的な失敗原因 |
| ディストリビューション | Arch | 仕組みは同じ、パッケージ名のみ異なる |

サンドボックスインストールでは追加パラメータは不要：まずネイティブパスをプローブし、次にレジストリに従って明示的な `cookie_file=` で snap/flatpak の cookie データベースをプローブする（`pplx_export/core/cookies/loaders.py:155-168`）。

**シナリオ → 推奨チャネル**：

| シナリオ | 推奨チャネル |
|---|---|
| Firefox がインストールされている | `--cookies-from firefox`——摩擦なし |
| デスクトップ GNOME / KDE | auto-detect で十分 |
| snap / flatpak ブラウザ | auto-detect——レジストリでカバー済み；それ以外はブラウザ拡張機能で `--cookies FILE` をエクスポート |
| ヘッドレスサーバー | `--cookies FILE`——汎用フォールバック；最終手段は `--transport webbridge` |

<a id="导出用了错误的账户多账户" data-pplx-source-anchor="true"></a>
## エクスポートに誤ったアカウントが使用された（複数アカウント）

**問題**：スレッドのアーカイブが誤ったアカウントのセッションで取得された——例えば、`--account alice` の実行が実際には `bob` でデータを取得した、またはアーカイブに対象外のアカウントのスレッドが含まれている。

**原因**：同じブラウザに複数のアカウントがログインしている場合、アクティブなセッショントークン（`__Secure-next-auth.session-token`）が別のアカウントのものである可能性がある。対象アカウントの `email` がユーザーレベルの設定に登録されていない場合、ツールはそれを認識できず、warning を記録するのみ。

**ツールの防止メカニズム**（`pplx_export/commands/common.py:93`）：起動時にトランスポートが `GET /api/auth/session` を呼び出し、リアルタイムのメールアドレスと登録値を比較する。不一致の場合、ブラウザ内の各アカウントのセッション cookie を自動的に列挙し（`__Secure-pplx.session.<user_id>`）、アクティブなトークンを順次置き換えてセッションをプローブし、対象のメールアドレスにヒットするまで続ける（`pplx_export/commands/common.py:190`；`pplx_export/core/cookies/loaders.py:175`）。トークンが一致しない場合、コマンドは明確なエラーで中止される——誤ったアカウントで静かに続行されることは決してない。

**修正**：

- `[accounts.<name>]` の下に各アカウントの `email` を登録し（[設定](configuration.md)を参照）、明示的に `--account` を渡す。
- 起動ログの行 `[auth] cookie 来源 …，当前账户: …` を確認する——これはデータ取得前にリアルタイムのセッションメールアドレスを報告する。
- 既存のアーカイブを監査する：各スレッドの `thread.json` には `export_via` フィールドがあり、エクスポートを実行したアカウントが記録されている（`pplx_export/sites/perplexity/fs_writer.py:229`）。`pplx-export sync-deleted` もこのフィールドを使用してオンライン検証のアカウントを選択する。

メカニズムの詳細：[API 認証](../reference/api/api-authentication.md) · [質問とアカウント](../architecture/ask-and-accounts.md)。

<a id="找不到配置文件降级模式" data-pplx-source-anchor="true"></a>
## 「設定ファイルが見つかりません」——デグレードモード

**問題**：起動時に warning が表示され、ユーザーレベルの設定ファイルが見つからず、コマンドがデグレードモードで実行される。または、明示的な `--account alice` がエラーを報告し、`config.example.toml` を指す。

**原因**：3つの検索場所すべてに設定ファイルがない——`--config PATH`、環境変数 `PPLX_EXPORT_CONFIG`、デフォルトの `~/.config/pplx-export/config.toml`（`pplx_export/config.py:113`）。2つの関連するが異なる状況：**明示的に指定された**設定パスが存在しない場合は `ConfigError` がスローされる；設定が破損している（解析不能）場合は常に `ConfigError` がスローされる——破損した設定が静かにデグレードされることは決してない。

**デグレードモードの影響**：

- アカウントレジストリが空になり、cookie 所有権の検証がスキップされ warning が表示され、コマンドはプレースホルダアカウント `default` で実行される（`pplx_export/commands/common.py:51`）。明示的な `--account` は直接エラーになる。
- `pplx-ask ask` は BOT スペースへの自動移動をスキップし（結果の JSON で `moved_to_bot` は `false` のまま）、テレメトリは空のユーザー ID を運ぶ；質問とアーカイブ自体は通常通り動作する。
- アーカイブはユーザー名でフォールバックされたアカウントディレクトリに保存される。

**修正**：`config.example.toml` を `~/.config/pplx-export/config.toml` にコピーし、`[accounts.<name>]`（`display_name` / `email` / `user_id`）、`[bot_space]`、`default_account` を入力する——[設定](configuration.md)を参照。

<a id="entry_expired-与-entry_deleted-的区别" data-pplx-source-anchor="true"></a>
## ENTRY_EXPIRED と ENTRY_DELETED の違い

**問題**：スレッドのエクスポートまたは差分同期中に `ENTRY_EXPIRED` または `ENTRY_DELETED` が報告され、そのスレッドが二度と取得できなくなる。

**原因**：両方とも `GET /rest/thread/<uuid>` の HTTP 400 で返され、エラーコードが異なり、かつ終端状態である——スレッドはプラットフォーム上に存在しなくなった：

| エラーコード | 意味 | ツールのマッピング | 終端状態 |
|---|---|---|---|
| `ENTRY_EXPIRED` | プラットフォームがスレッドを消去（約3か月の保持期間） | `EntryExpiredError`（`pplx_export/core/errors.py:24`） | `expired` |
| `ENTRY_DELETED` | スレッドがユーザー/リモートによって削除された（`DELETE /rest/thread/delete_thread_by_entry_uuid` の下流の動作） | `EntryDeletedError`、`EntryExpiredError` のサブクラス（`pplx_export/core/errors.py:30`） | `deleted` |

**アーカイブへの影響**：

- 両方の状態で再試行は決して行われない——差分同期でも、`--force` を追加しても。終端状態マーカーは `<out>/index/batch_state.json` に存在する。
- ツールは**ローカルアーカイブを決して削除または移動しない**——リポジトリのコピーがバックアップとなる。エクスポートコマンドは終端状態を記録した後、正常に終了する（`pplx_export/commands/export_cmd.py:51`）。
- サブクラス関係は意図的な設計：`EntryExpiredError` のみを認識する既存のパスは、`ENTRY_DELETED` を終端状態として扱い続ける；サブクラスを認識するパス（batch / export / sync-deleted / search-mode-backfill）は、正確に `deleted` として分類する。
- 実践上のポイント：早めにエクスポートする。約3か月の消去期間を過ぎると、成果物/レポートのソースリンクも回復不能に期限切れになる。

関連：[差分同期](incremental-sync.md) · [レスポンスとエラー](../reference/api/api-responses-errors.md)。

<a id="无法下载的资产toolu_-句柄" data-pplx-source-anchor="true"></a>
## ダウンロードできないアセット（`toolu_` ハンドル）

**問題**：`assets/assets_manifest.json` 内の一部のエントリのバージョンが `"no_download_channel": true` とマークされ、`assets/files/` の下に対応するファイルがない。

**原因**：`toolu_` プレフィックスを持つクラウドワークスペースハンドル（URL 形式のない DOC_FILE / CODE_FILE / UNKNOWN）には API ダウンロードチャネルがない：`GET /rest/assets/<asset_uuid>/data` はそれらに対して 404 `ASSET_NOT_FOUND` を返し、`file-repository/download` は `file:repo/...` ハンドルを拒否する（400）。これは**既知のアーカイブ完全性の境界**であり、エクスポートの欠陥ではない。`pplx-export assets-backfill` はこれらのバージョンを `no_download_channel` とマークしてスキップする（`pplx_export/commands/assets_backfill_cmd.py:356`）。

**修正**：

- 現時点ではダウンロード不可——このマークはこの境界を意図的に記録したもの。
- コンテンツはインラインで保持されていることが多い：サブエージェントのページ抽出テキストとステップペイロードはスレッドの raw JSON（`raw_entries.json` / `raw_blocks.json`）およびレンダリングされた `turns/` に保存されている——まずそこを確認する。
- `file-repository/list-files` は将来の救済パスとして追跡されている。[API 発見ロードマップ](../reference/api/api-discovery-roadmap.md)を参照。

マニフェストレイアウト：[アーカイブレイアウト](archive-layout.md)。

<a id="日志在哪里" data-pplx-source-anchor="true"></a>
## ログはどこにありますか？

**コンソール**：デフォルトは INFO レベルの進捗；`-v` / `--verbose` で DEBUG に切り替え（リクエストトレース、内部判定）；warning と error は常に表示。

**ファイル**：`--log-file` を渡すと、完全な DEBUG ストリームがファイルに書き込まれる（`pplx_export/core/logging.py:45`）：

- `--log-file` に値がない場合、`<out>/index/logs/<cmd>-<timestamp>.log` に書き込まれる（`pplx_export/commands/common.py:218`）——例：`pplx-ask-ask-20260723-120000.log`。
- `--log-file PATH` は指定されたパスに書き込まれる。

**診断に役立つその他のステータスファイル**（すべて `<out>/index/` の下）：

| ファイル | 内容 |
|---|---|
| `.cookies.json` | cookie キャッシュ（12時間の有効期間；0o600 アトミック書き込み——ログイン相当の資格情報のため、機密扱い） |
| `batch_state.json` | スレッドごとのエクスポート状態、`expired` / `deleted` 終端状態マーカーを含む |
| `answer_variants_log.jsonl` | 回答書き換えバリアントのレジストリ |
| `library_*.json` | 各アカウントのライブラリインデックススナップショット |

<a id="参见" data-pplx-source-anchor="true"></a>
## 関連項目

- [クイックスタート](getting-started.md) —— 初回セットアップと cookie インポート
- [設定](configuration.md) —— アカウント、BOT スペース、デグレードモード
- [pplx-ask](pplx-ask.md) —— インタラクティブクエリ CLI
- [pplx-export](pplx-export.md) —— アーカイブ CLI
- [レート制限](rate-limiting.md) —— ペースとバックオフ規律
