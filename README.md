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

## テスト

```bash
python -m pytest tests/ -q
```

在庫判定ロジック・状態保存はネットワーク不要でテストできます。
