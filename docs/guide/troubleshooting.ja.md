---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/troubleshooting.zh-CN.md"
translation_source_sha256: "2ecc68fa7d02955edcb4baf4bdcfbfbdb1d35a08790030237e409c3a025a01bc"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="故障排查" data-pplx-source-anchor="true"></a>
# トラブルシューティング

FAQ 形式：各項目は **問題 → 原因 → 修正** で構成。完全なエラーセマンティクス（ステータスコード、終端状態、
リトライ規律）については[レスポンスとエラー](../reference/api/api-responses-errors.md)と
[レート制限とエラー](../architecture/rate-limiting-errors.md)を参照。

<a id="裸请求-api-遭遇-cloudflare-403" data-pplx-source-anchor="true"></a>
## ベアリクエスト API で Cloudflare 403

**問題**：手動 `curl` / スクリプトから `www.perplexity.ai` の REST エンドポイントにリクエストすると、ブラウザからコピーした cookie を使っても 403 と Cloudflare チャレンジページが返る——しかし同じエンドポイントをツール経由では正常に動作する。

**原因**：Cloudflare がサイトの前に立ちはだかり、`cf_clearance` / `__cf_bm` はブラウザの TLS フィンガープリントに紐づいている。ベアクライアントのフィンガープリントが一致しないため、チャレンジが発生する。ツールが通るのは、Python `urllib` + ブラウザからインポートした cookie + デスクトップ Chrome `User-Agent`
（`pplx_export/core/http/cookie_transport.py:29`）を使っているから。Cloudflare がレート制限でブロックする場合も 403 になる——その場合も同じチャレンジ形態のレスポンスが返る。

**修正**：

- ツールのトランスポートを迂回しないこと。`pplx-export` / `pplx-ask` を使って呼び出し、一時的なスクリプトは書かない。
- ツール内部では、HTTP 200 だが JSON ではないレスポンスボディ（Cloudflare の通過ページ）をデータではなく転送エラーとして分類する（`pplx_export/core/http/cookie_transport.py:133`）。
- ツール内で 403 が出始めたら、まずペースを落とし（[レート制限](rate-limiting.md)を参照）、cookie をリフレッシュする。チャレンジが続く場合はブラウザで再ログインする。
- 403 には2つの顔があることに注意：Cloudflare のレート制限チャレンジ（ペースを落とせば解消）と API レベルの 403（cookie の有効期限切れ——即座にスローされ、バックオフしない。次のセクション参照）。設計ページでは後者をマッピングしている（[rate-limiting-errors.md](../architecture/rate-limiting-errors.md)）。

背景：[API 認証](../reference/api/api-authentication.md)。

<a id="401-错误-cookie-过期" data-pplx-source-anchor="true"></a>
## 401 エラー / cookie の期限切れ

**問題**：認証エラーでコマンドが失敗する——`pplx-export` が `AuthTransportError: 鉴权失败 401` をスローするか、`pplx-ask ask` が HTTP 401/403 で「cookie を更新」というメッセージとともに終了する。

**原因**：セッション cookie の有効期限が切れているか、無効になっている。`401`/`403` は認証失敗とみなされ、即座にスローされる——バックオフはしない。なぜならバックオフでは死んだセッションは回復しないから（`pplx_export/core/http/cookie_transport.py:82`；
`pplx_export/core/errors.py:68`）。`batch` は認証失敗が3回連続すると fail-fast し、死んだ cookie がキュー全体を消費するのを防ぐ。

**修正**：

1. ブラウザで再ログイン（またはサイトを再度開く）して、セッション cookie を更新する。
2. ツールの cookie キャッシュをリフレッシュする。`<out>/index/.cookies.json` は12時間の有効期間内であれば再利用される（`pplx_export/core/cookies/cache.py:22`）。そのため、再ログイン後は次のいずれかを実行：
   - `--cookies-from <browser>` を付けて一度実行し、ブラウザから強制的に再インポートする。または
   - `<out>/index/.cookies.json` を削除し、次回の実行時に自動的に再インポートさせる。
3. 検証に成功した実行ごとにキャッシュが再保存される（`pplx_export/commands/common.py:150`）ため、通常の実行で自動的に新鮮さが保たれる。

設定の詳細：[クイックスタート](getting-started.md) · [設定](configuration.md)。

<a id="linux-cookie-解密" data-pplx-source-anchor="true"></a>
## Linux での cookie 復号

**問題**：Linux で auto-detect（または `--cookies-from chrome` など）がブラウザの cookie ストアを読み取れない。ブラウザはログイン状態であるにもかかわらず。

**仕組み**：Linux 上の Chromium 系ブラウザは、OS のキーリングに保存された鍵で cookie データベースを暗号化し、実行時に Secret Service D-Bus API を介してその鍵を取得する。`browser_cookie3` は純粋な Python の `jeepney` を使って D-Bus にアクセスする——これはツールとともに Linux にインストールされ、追加設定は不要——キーリングが応答しない場合は、レガシーな `peanuts` パスワードにフォールバックする。このパスワードは、Chrome が以前にキーリングなしの環境で書き込んだ cookie のみを復号できる。キーリングは存在するが D-Bus クエリがトランスポートレベルで失敗する場合（セッションバスが匿名アクセスを拒否するなど）、`browser_cookie3` 自身のフォールバックチェーンは機能しない。ツールはこの状況を検出し、キーリングをバイパスして Chromium のデフォルトパスワード——つまり Chromium がキーリングなしの環境で自身が使用する鍵——を使って再試行する（`pplx_export/core/cookies/loaders.py:62-104`、
ロードパスは `loaders.py:136-153` に組み込み）。Firefox はこれらに一切関与しない：その `cookies.sqlite` は暗号化されていない。

**マトリックス**：

| レイヤー | 状況 | 結果 |
|---|---|---|
| ブラウザ | Firefox | 摩擦ゼロ——`cookies.sqlite` は暗号化されていない |
| ブラウザ | Chromium + キーリング到達可能 | 正常——Secret Service 経由で鍵を取得 |
| ブラウザ | Chromium + キーリングなし | `peanuts` パス——Chrome が以前にキーリングなしで書き込んだ場合のみ有効 |
| ブラウザ | Chromium + キーリング到達不能（D-Bus レベルで失敗） | ツールが自動的に Chromium デフォルトパスワードで再試行——到達性は `peanuts` パスと同じ |
| インストール方法 | ネイティブパッケージ | auto-detect（browser_cookie3 組み込みパス） |
| インストール方法 | snap / flatpak | auto-detect——組み込みプロファイルレジストリが `~/snap/<name>/...` と `~/.var/app/<app-id>/...` 下のプロファイルをカバー（`pplx_export/core/cookies/profiles.py:37-67`） |
| デスクトップ環境 | GNOME | 通常はそのまま動作（gnome-keyring） |
| デスクトップ環境 | KDE | KWallet 設定で **Use KWallet for the Secret Service interface** にチェックを入れる |
| デスクトップ環境 | ヘッドレス / 最小構成 | D-Bus セッションバスなし → `peanuts` パス |
| ディストリビューション | Debian / Ubuntu | `libsecret-1-0` + `gnome-keyring` をインストール |
| ディストリビューション | Fedora / RHEL | `libsecret` + `gnome-keyring` をインストール；最小構成 / server インストールではキーリングがまったくないことが多い——最も一般的な失敗原因 |
| ディストリビューション | Arch | 仕組みは同じ、パッケージ名のみ異なる |

サンドボックスインストールでは追加パラメータ不要：まずネイティブパスをプローブし、次にレジストリに従って明示的な `cookie_file=` で snap/flatpak の cookie データベースをプローブする（`pplx_export/core/cookies/loaders.py:155-168`）。

**シナリオ → 推奨チャネル**：

| シナリオ | 推奨チャネル |
|---|---|
| Firefox を使用 | `--cookies-from firefox`——摩擦ゼロ |
| デスクトップ GNOME / KDE | auto-detect で十分 |
| snap / flatpak ブラウザ | auto-detect——レジストリがカバー；それ以外はブラウザ拡張機能で `--cookies FILE` をエクスポート |
| ヘッドレスサーバー | `--cookies FILE`——汎用フォールバック；最終手段は `--transport webbridge` |

<a id="导出用了错误的账户多账户" data-pplx-source-anchor="true"></a>
## エクスポートに誤ったアカウントが使用される（複数アカウント）

**問題**：スレッドのアーカイブが誤ったアカウントのセッションで取得される——例えば `--account alice` の実行が実際には `bob` でデータを取得する、またはアーカイブに対象アカウント以外のスレッドが含まれる。

**原因**：同じブラウザに複数のアカウントがログインしている場合、アクティブなセッショントークン（`__Secure-next-auth.session-token`）が別のアカウントのものである可能性がある。対象アカウントの `email` がユーザーレベルの設定に登録されていない場合、ツールはそれを認識できず、warning を記録するだけである。

**ツールの防止機構**（`pplx_export/commands/common.py:93`）：起動時にトランスポートが `GET /api/auth/session` を呼び出し、リアルタイムの email と登録値を比較する。不一致の場合、ブラウザ内の各アカウントのセッション cookie を自動的に列挙し（`__Secure-pplx.session.<user_id>`）、アクティブなトークンを一つずつ置き換えてセッションをプローブし、対象の email に到達するまで続ける（`pplx_export/commands/common.py:190`；
`pplx_export/core/cookies/loaders.py:175`）。トークンが一致しない場合、コマンドは明確なエラーメッセージで中止される——誤ったアカウントで静かに続行することは決してない。

**修正**：

- `[accounts.<name>]` の下に各アカウントの `email` を登録し（[設定](configuration.md)を参照）、明示的に `--account` を渡す。
- 起動ログの行 `[auth] cookie 来源 …，当前账户: …` を確認する——これはデータ取得前にリアルタイムのセッション email を報告する。
- 既存のアーカイブを監査する：各スレッドの `thread.json` には `export_via` フィールドがあり、エクスポートを実行したアカウントが記録されている（`pplx_export/sites/perplexity/fs_writer.py:229`）。`pplx-export sync-deleted`
もこのフィールドを使用してオンライン検証のアカウントを選択する。

仕組みの詳細：[API 認証](../reference/api/api-authentication.md) ·
[質問とアカウント](../architecture/ask-and-accounts.md)。

<a id="找不到配置文件降级模式" data-pplx-source-anchor="true"></a>
## 「設定ファイルが見つかりません」——デグレードモード

**問題**：起動時にユーザーレベルの設定ファイルが見つからず、コマンドがデグレードモードで実行されるという warning が表示される。または明示的な `--account alice` がエラーになり、`config.example.toml` を指し示す。

**原因**：3つの検索場所のいずれにも設定ファイルがない——`--config PATH`、環境変数 `PPLX_EXPORT_CONFIG`、デフォルトの `~/.config/pplx-export/config.toml`
（`pplx_export/config.py:113`）。2つの関連するが異なる状況：**明示的に指定**された設定パスが存在しない場合は `ConfigError` がスローされる；設定が破損している（パースできない）場合は常に `ConfigError` がスローされる——破損した設定が静かにデグレードされることは決してない。

**デグレードモードの影響**：

- アカウントレジストリが空になり、cookie の帰属チェックはスキップされて warning が表示され、コマンドはプレースホルダアカウント `default` で実行される（`pplx_export/commands/common.py:51`）。明示的な `--account` の場合は直接エラーになる。
- `pplx-ask ask` は BOT スペースへの自動移動をスキップし（結果 JSON の `moved_to_bot` は `false` のまま）、テレメトリは空の user id を送信する；質問とアーカイブ自体は通常通り動作する。
- アーカイブはユーザー名でフォールバックされたアカウントディレクトリに保存される。

**修正**：`config.example.toml` を `~/.config/pplx-export/config.toml` にコピーし、`[accounts.<name>]`（`display_name` / `email` / `user_id`）、`[bot_space]`、`default_account` を記入する——[設定](configuration.md)を参照。

<a id="entry_expired-与-entry_deleted-的区别" data-pplx-source-anchor="true"></a>
## ENTRY_EXPIRED と ENTRY_DELETED の違い

**問題**：スレッドのエクスポートまたは差分同期中に `ENTRY_EXPIRED` または `ENTRY_DELETED` が報告され、そのスレッドが以後取得できなくなる。

**原因**：どちらも `GET /rest/thread/<uuid>` の HTTP 400 で返され、エラーコードが異なり、かつ終端状態である——スレッドはプラットフォーム上に存在しなくなっている：

| エラーコード | 意味 | ツールのマッピング | 終端状態 |
|---|---|---|---|
| `ENTRY_EXPIRED` | プラットフォームがスレッドを消去（約3ヶ月の保持期間） | `EntryExpiredError`（`pplx_export/core/errors.py:24`） | `expired` |
| `ENTRY_DELETED` | スレッドがユーザー/リモートによって能動的に削除された（`DELETE /rest/thread/delete_thread_by_entry_uuid` の下流での現れ） | `EntryDeletedError`、`EntryExpiredError` のサブクラス（`pplx_export/core/errors.py:30`） | `deleted` |

**アーカイブにとっての意味**：

- どちらの状態も決してリトライされない——差分同期でも、`--force` を付けてもリトライされない。終端状態のマークは `<out>/index/batch_state.json` に存在する。
- ツールは**ローカルアーカイブを決して削除または移動しない**——リポジトリのコピーがバックアップとなる。エクスポートコマンドは終端状態を記録した後、正常終了する（`pplx_export/commands/export_cmd.py:51`）。
- サブクラス関係は意図的な設計：`EntryExpiredError` のみを認識する既存のパスでも `ENTRY_DELETED` を終端状態として扱う；サブクラスを認識するパス（batch / export / sync-deleted / search-mode-backfill）は正確に `deleted` として分類する。
- 実践上のポイント：早めにエクスポートすること。約3ヶ月の消去期間を過ぎると、成果物やレポートのソースリンクも回復不能に期限切れとなる。

関連：[差分同期](incremental-sync.md) · [レスポンスとエラー](../reference/api/api-responses-errors.md)。

<a id="无法下载的资产toolu_-句柄" data-pplx-source-anchor="true"></a>
## ダウンロードできないアセット（`toolu_` ハンドル）

**問題**：`assets/assets_manifest.json` 内の一部のエントリのバージョンが `"no_download_channel": true` とマークされ、`assets/files/` の下に対応するファイルがない。

**原因**：`toolu_` プレフィックスを持つ cloud-workspace ハンドル（URL 形式を持たない DOC_FILE / CODE_FILE / UNKNOWN）には API ダウンロード経路がない：`GET /rest/assets/<asset_uuid>/data` はそれらに対して 404 `ASSET_NOT_FOUND` を返し、`file-repository/download` は `file:repo/...` ハンドルを拒否する（400）。これは**既知のアーカイブ完全性の境界**であり、エクスポートの欠陥ではない。`pplx-export assets-backfill` はこれらのバージョンを `no_download_channel` とマークしてスキップする（`pplx_export/commands/assets_backfill_cmd.py:356`）。

**修正**：

- 現時点ではダウンロード不可——このマークはその境界を意図的に記録したものである。
- コンテンツはインラインで残っていることが多い：サブエージェントのページ抽出テキストとステップペイロードはスレッドの raw JSON（`raw_entries.json` / `raw_blocks.json`）とレンダリングされた `turns/` に保存されている——まずそこを確認する。
- `file-repository/list-files` は将来の救済経路として追跡されている。[API 発見ロードマップ](../reference/api/api-discovery-roadmap.md)を参照。

マニフェストのレイアウト：[アーカイブレイアウト](archive-layout.md)。

<a id="命令看似卡住-长时间无输出" data-pplx-source-anchor="true"></a>
## コマンドが停止しているように見える / 長時間出力がない

**症状**：`index` / `batch` / `export` が数分間何も出力しない；外部のタスクマネージャーが「タイムアウト」として強制終了する可能性がある。

**原因**：ほとんどの場合、バックオフ待機であり、ハングアップではない。429 / 5xx / ネットワークエラー時、トランスポート層は試行の間にスリープする——1回の待機の上限は 300 秒（`pplx_export/core/throttle.py:38-50`）。
DEBUG レベルのログでは待機が明示される：

```
19:39:31 GET www.perplexity.ai/rest/thread/<uuid> 网络错误: Remote end closed connection without response
19:39:31 退避 200.9s（连续失败 2 次）
```

**判別方法**：`-v`（または `--log-file`）を付けて実行し、バックオフのログ行を確認する；プロセスが生きていれば介入は不要。いつ中断しても安全——状態はアトミックにディスクに書き込まれ、次回の実行で自動的に不足分が補完される。

**アンチパターン**：CLI を短いハードタイムアウト付きのタスクマネージャー（エージェントのバックグラウンドタスク、`timeout(1)` スタイルの cron ラッパー）でラップし、さらに `&&` で複数アカウントを連鎖させる——最初のアカウントのバックオフが連鎖してタイムアウト全体を消費し、後続のアカウントが実行されなくなる。1回の呼び出しで1アカウント、十分な予算を確保すること：[呼び出し側のランタイム予算](rate-limiting.md#调用方运行时预算)を参照。

<a id="日志在哪里" data-pplx-source-anchor="true"></a>
## ログはどこにありますか？

**コンソール**：デフォルトは INFO レベルの進捗；`-v` / `--verbose` で DEBUG に切り替え（リクエストトレース、内部判定）；warning と error は常に表示される。

**ファイル**：`--log-file` を渡すと、完全な DEBUG ストリームがディスクに書き込まれる（`pplx_export/core/logging.py:45`）：

- `--log-file` に値がない場合、`<out>/index/logs/<cmd>-<timestamp>.log` に書き込まれる（`pplx_export/commands/common.py:218`）——例えば `pplx-ask-ask-20260723-120000.log`。
- `--log-file PATH` は指定されたパスに書き込まれる。

**診断に役立つその他の状態ファイル**（すべて `<out>/index/` の下）：

| ファイル | 内容 |
|---|---|
| `.cookies.json` | cookie キャッシュ（12時間の有効期間；0o600 アトミック書き込み——ログイン相当の資格情報なので機密扱い） |
| `batch_state.json` | スレッドごとのエクスポート状態、`expired` / `deleted` の終端状態マークを含む |
| `answer_variants_log.jsonl` | 回答書き換えバリアントのレジストリ |
| `library_*.json` | 各アカウントのライブラリインデックススナップショット |

<a id="参见" data-pplx-source-anchor="true"></a>
## 関連項目

- [クイックスタート](getting-started.md) —— 初回設定と cookie インポート
- [設定](configuration.md) —— アカウント、BOT スペース、デグレードモード
- [pplx-ask](pplx-ask.md) —— インタラクティブクエリ CLI
- [pplx-export](pplx-export.md) —— アーカイブ CLI
- [レート制限](rate-limiting.md) —— ペースとバックオフ規律
