# Inventory-Check-tool

商品ページの在庫状態を**定期的にチェック**し、状態が変化したとき(例:「在庫なし」→「在庫あり」)に通知するツールです。

最初の監視対象はセブンネットショッピングの商品です:
<https://7net.omni7.jp/detail/2110693846>

## 特長

- 複数商品の在庫を定期チェック
- 在庫状態が**変化したときだけ**通知(毎回は通知しない)
- 通知チャネル: コンソール / Webhook(Slack・Discord 互換)/ メール(SMTP)
- 在庫判定キーワードは設定でカスタマイズ可能(サイトの表記変更に対応しやすい)
- 常駐モード(`interval_minutes` ごとに繰り返し)と単発モード(`--once`、cron 向け)の両対応

## セットアップ

```bash
pip install -r requirements.txt
cp config.example.json config.json
# config.json を編集して監視対象や通知先を設定
```

## 使い方

```bash
# 常駐して定期チェック (config の interval_minutes ごと)
python main.py

# 1回だけチェックして終了 (cron などの定期実行向け)
python main.py --once

# パスを指定する場合
python main.py --config config.json --state state.json
```

### cron で定期実行する例(30分ごと)

```cron
*/30 * * * * cd /path/to/Inventory-Check-tool && /usr/bin/python3 main.py --once >> cron.log 2>&1
```

## 設定 (config.json)

| 項目 | 説明 |
| --- | --- |
| `interval_minutes` | 常駐モードでのチェック間隔(分) |
| `user_agent` | リクエスト時の User-Agent |
| `request_timeout_seconds` | HTTP タイムアウト(秒) |
| `notify_on` | 通知する状態の配列。例 `["in_stock"]` で「在庫あり」に変化したときのみ通知 |
| `products` | 監視対象商品の配列(`name` と `url`。任意で `in_stock` / `out_of_stock` キーワードを商品ごとに上書き可) |
| `notifications.console` | コンソール出力の有効/無効 |
| `notifications.webhook` | Webhook 通知設定(`format`: `slack` / `discord` / `raw`) |
| `notifications.email` | SMTP メール通知設定 |
| `stock_keywords.in_stock` | 「在庫あり」と判定する語のリスト |
| `stock_keywords.out_of_stock` | 「在庫なし」と判定する語のリスト |

### 在庫判定の仕組み

ページの可視テキストに対して次の順で判定します。

1. `out_of_stock` の語が含まれる → **在庫なし**
2. `in_stock` の語(例:「カートに入れる」)が含まれる → **在庫あり**
3. どちらも無い → **判定不能 (unknown)**

「在庫なし」の表記の方が具体的なため優先して評価します。

> **注意:** 既定のキーワードはセブンネットショッピングの一般的な表記を想定した初期値です。
> 実際のページ表記やサイト改修に合わせて、初回実行時にログ(判定結果と一致キーワード)を確認し、
> 必要に応じて `config.json` の `stock_keywords` を調整してください。
>
> また、商品ページが JavaScript で在庫情報を後から描画する場合、HTML 取得だけでは
> 在庫を判定できないことがあります(その場合 `unknown` になります)。その際は対象 API の利用や
> ヘッドレスブラウザの導入など、取得方法の拡張が必要です。

## クラウドで定期実行する (GitHub Actions)

専用サーバーを用意せず、GitHub Actions のスケジュール実行で定期チェックできます。
`.github/workflows/inventory-check.yml` が**日本時間 9:00〜21:00 のあいだ 3分ごと**に
在庫をチェックし、在庫が変化したとき Discord に通知します。

GitHub Actions の cron は最短5分間隔のため、3分間隔は「1つのジョブ内で
`python main.py`(ループモード)を3分ごとに回し、約59分で終了 → 次の毎時 cron で再起動」
という方式で実現しています(cron は UTC 基準。UTC 0〜11時 = JST 9〜20時 に毎時起動)。

> **重要(実行コスト):** この方式はジョブがほぼ連続稼働するため、Actions の実行時間を
> 多く消費します。**private リポジトリの無料枠(月2,000分)では数日で上限に達し停止**します。
> 常時無料で回すには、**リポジトリを public にする**(Actions が無制限・無料になる)ことを推奨します。
> private のまま使う場合は、間隔を広げる(`config.ci.json` の `interval_minutes` と
> ワークフローの構成変更)か、使用量を **Settings → Billing** で監視してください。

### セットアップ手順

1. **Discord の Webhook URL を用意する**
   Discord のチャンネル設定 →「連携サービス」→「ウェブフック」→「新しいウェブフック」で
   URL をコピーします。
2. **リポジトリに Secret を登録する**
   GitHub のリポジトリで **Settings → Secrets and variables → Actions → New repository secret** を開き、
   - Name: `DISCORD_WEBHOOK_URL`
   - Secret: コピーした Webhook URL
   を登録します。
3. ワークフローはデフォルトブランチ(`main`)にマージされると自動で有効になります。
   **Actions** タブの「Inventory Check」から `Run workflow` で手動実行して動作確認できます。

### 通知のテスト

在庫の状態に関係なく、Discord連携が正しく動くか確認できます。

- **GitHub上で:** Actions タブ →「Inventory Check」→「Run workflow」→
  **「テスト通知を送る」にチェック**を入れて実行すると、Discord にテストメッセージが届きます。
- **ローカルで:** `python main.py --test-notify --config config.ci.json`
  (環境変数 `DISCORD_WEBHOOK_URL` を設定しておく)

### 仕組みのポイント

- 設定ファイル `config.ci.json` の `${DISCORD_WEBHOOK_URL}` が実行時に Secret で置換されます
  (URL をリポジトリに直接書かないため安全)。
- 前回の在庫状態 `state.json` は Actions のキャッシュで実行間に引き継がれ、
  **状態が変化したときだけ**通知されます。
- チェック間隔は `config.ci.json` の `interval_minutes` で調整できます(既定3分)。
  時間帯を変えたい場合はワークフローの `cron`(UTC 基準、JST との時差9時間)と、
  1ジョブの実行時間 `--max-runtime` を編集してください。

> **注意:** GitHub のスケジュール実行は、リポジトリが60日間操作されないと自動停止します。
> また実ページの在庫表記に合わせて `config.ci.json` の `stock_keywords` を調整してください。

## テスト

```bash
python -m pytest tests/ -q
```

在庫判定ロジック・状態保存はネットワーク不要でテストできます。
