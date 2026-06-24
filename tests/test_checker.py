"""在庫判定ロジックと状態保存のテスト (ネットワーク不要)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inventory_checker.checker import StockStatus, determine_status  # noqa: E402
from inventory_checker.config import (  # noqa: E402
    DEFAULT_IN_STOCK_KEYWORDS,
    DEFAULT_OUT_OF_STOCK_KEYWORDS,
)
from inventory_checker.state import StateStore  # noqa: E402


def test_in_stock_detected():
    text = "この商品をカートに入れる ご注文手続きへ"
    status, _ = determine_status(
        text, DEFAULT_OUT_OF_STOCK_KEYWORDS, DEFAULT_IN_STOCK_KEYWORDS
    )
    assert status == StockStatus.IN_STOCK


def test_out_of_stock_detected():
    text = "申し訳ございません。在庫切れです。"
    status, _ = determine_status(
        text, DEFAULT_OUT_OF_STOCK_KEYWORDS, DEFAULT_IN_STOCK_KEYWORDS
    )
    assert status == StockStatus.OUT_OF_STOCK


def test_out_of_stock_takes_priority():
    # カートボタンと在庫なし表記が両方ある場合は在庫なしを優先
    text = "売り切れ カートに入れる"
    status, _ = determine_status(
        text, DEFAULT_OUT_OF_STOCK_KEYWORDS, DEFAULT_IN_STOCK_KEYWORDS
    )
    assert status == StockStatus.OUT_OF_STOCK


def test_unknown_when_no_keywords():
    text = "商品説明だけがあるページ"
    status, _ = determine_status(
        text, DEFAULT_OUT_OF_STOCK_KEYWORDS, DEFAULT_IN_STOCK_KEYWORDS
    )
    assert status == StockStatus.UNKNOWN


def test_config_expands_env_vars(tmp_path, monkeypatch):
    import json

    from inventory_checker.config import load_config

    monkeypatch.setenv("MY_HOOK", "https://example.com/hook")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "products": [{"name": "x", "url": "https://example.com/x"}],
                "notifications": {
                    "webhook": {"enabled": True, "url": "${MY_HOOK}", "format": "discord"}
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.webhook.url == "https://example.com/hook"


def test_state_store_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    assert store.get("https://example.com/x") is None
    store.set("https://example.com/x", "in_stock")

    reloaded = StateStore(path)
    assert reloaded.get("https://example.com/x") == "in_stock"
