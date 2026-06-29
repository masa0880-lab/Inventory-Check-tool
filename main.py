#!/usr/bin/env python3
"""定期的に商品の在庫をチェックするツールのエントリポイント.

使い方:
    # 1回だけチェック (cron などから定期実行する場合に便利)
    python main.py --once

    # 常駐して config の interval_minutes ごとに繰り返しチェック
    python main.py

    # 設定ファイル/状態ファイルのパスを指定
    python main.py --config config.json --state state.json
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime

import requests

from inventory_checker.checker import StockStatus, check_product
from inventory_checker.config import load_config
from inventory_checker.notifier import notify, send_test
from inventory_checker.state import StateStore

logger = logging.getLogger("inventory_check")


def run_once(config_path: str, state_path: str) -> None:
    config = load_config(config_path)
    store = StateStore(state_path)
    session = requests.Session()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("在庫チェック開始 (%s) — 対象 %d 件", timestamp, len(config.products))

    for product in config.products:
        result = check_product(product, config, session=session)
        previous = store.get(product.url)
        logger.info(
            "[%s] %s (前回: %s)",
            result.status.label,
            product.name,
            previous or "なし",
        )

        if result.status == StockStatus.ERROR:
            # 取得エラーは状態を更新せず、ログのみ (ネットワーク一時障害などを変化として扱わない)
            logger.warning("  取得エラー: %s", result.detail)
            continue

        status_value = result.status.value
        changed = previous != status_value
        should_notify = changed and status_value in config.notify_on

        if should_notify:
            notify(config, result, previous)

        store.set(product.url, status_value)


def run_loop(config_path: str, state_path: str) -> None:
    config = load_config(config_path)
    interval_seconds = max(config.interval_minutes * 60, 5)
    logger.info(
        "常駐モードで起動しました。%.0f 分ごとにチェックします。Ctrl+C で停止。",
        config.interval_minutes,
    )
    while True:
        try:
            run_once(config_path, state_path)
        except Exception as exc:  # noqa: BLE001 - 1回の失敗でループを止めない
            logger.error("チェック中にエラーが発生しました: %s", exc)
        time.sleep(interval_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="商品の在庫を定期チェックするツール")
    parser.add_argument(
        "--config", default="config.json", help="設定ファイルのパス (既定: config.json)"
    )
    parser.add_argument(
        "--state",
        default="state.json",
        help="状態保存ファイルのパス (既定: state.json)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="1回だけチェックして終了する (cron 向け)",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="在庫に関係なくテスト通知を1回送って終了する (通知連携の確認用)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        if args.test_notify:
            send_test(load_config(args.config))
            logger.info("テスト通知を送信しました。")
        elif args.once:
            run_once(args.config, args.state)
        else:
            run_loop(args.config, args.state)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("停止しました。")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
