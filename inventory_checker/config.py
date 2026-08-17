"""設定ファイル (config.json) の読み込みと検証."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_OUT_OF_STOCK_KEYWORDS = [
    "在庫切れ",
    "在庫がございません",
    "申し訳ございません",
    "販売を終了",
    "予約受付を終了",
    "お取り扱いできません",
    "SOLD OUT",
    "売り切れ",
    "入荷待ち",
    "入荷予定はございません",
    "現在お取り扱いできません",
]

DEFAULT_IN_STOCK_KEYWORDS = [
    "カートに入れる",
    "在庫あり",
    "ご注文手続きへ",
    "レジに進む",
    "今すぐ購入",
    "ご購入手続きへ",
]


@dataclass
class Product:
    name: str
    url: str
    # 監視対象をショップ単位でグルーピングするための識別名 (省略時は「その他」扱い)
    shop: str = ""
    # 商品ごとにキーワードを上書きしたい場合に使用 (省略時はグローバル設定を使う)
    out_of_stock: list[str] | None = None
    in_stock: list[str] | None = None


@dataclass
class WebhookConfig:
    enabled: bool = False
    url: str = ""
    format: str = "slack"  # "slack" | "discord" | "raw"


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    use_tls: bool = True
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)


@dataclass
class Config:
    interval_minutes: float = 30.0
    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = 20.0
    # どの状態に変化したときに通知するか: "in_stock" / "out_of_stock" / "unknown"
    notify_on: list[str] = field(default_factory=lambda: ["in_stock"])
    products: list[Product] = field(default_factory=list)
    console: bool = True
    webhook: WebhookConfig = field(default_factory=WebhookConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    out_of_stock_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_OUT_OF_STOCK_KEYWORDS)
    )
    in_stock_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_IN_STOCK_KEYWORDS)
    )


def _require(data: dict[str, Any], key: str, context: str) -> Any:
    if key not in data:
        raise ValueError(f"設定エラー: {context} に必須項目 '{key}' がありません")
    return data[key]


def _expand_env(value: Any) -> Any:
    """設定値の文字列に含まれる ${VAR} / $VAR を環境変数で置換する.

    CI(GitHub Actions)などで Webhook URL や認証情報を Secret から
    渡せるようにするための仕組み。未定義の変数はそのまま残す。
    """
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_config(path: str | Path) -> Config:
    """JSON 設定ファイルを読み込んで Config を返す."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {path}\n"
            f"config.example.json をコピーして作成してください。"
        )

    with path.open(encoding="utf-8") as fh:
        data = _expand_env(json.load(fh))

    products: list[Product] = []
    for raw in data.get("products", []):
        products.append(
            Product(
                name=_require(raw, "name", "products[]"),
                url=_require(raw, "url", "products[]"),
                shop=raw.get("shop", ""),
                out_of_stock=raw.get("out_of_stock"),
                in_stock=raw.get("in_stock"),
            )
        )

    if not products:
        raise ValueError("設定エラー: 'products' が空です。監視する商品を1件以上指定してください。")

    notifications = data.get("notifications", {})
    webhook_raw = notifications.get("webhook", {})
    email_raw = notifications.get("email", {})
    keywords = data.get("stock_keywords", {})

    return Config(
        interval_minutes=float(data.get("interval_minutes", 30)),
        user_agent=data.get("user_agent", DEFAULT_USER_AGENT),
        request_timeout_seconds=float(data.get("request_timeout_seconds", 20)),
        notify_on=list(data.get("notify_on", ["in_stock"])),
        products=products,
        console=bool(notifications.get("console", True)),
        webhook=WebhookConfig(
            enabled=bool(webhook_raw.get("enabled", False)),
            url=webhook_raw.get("url", ""),
            format=webhook_raw.get("format", "slack"),
        ),
        email=EmailConfig(
            enabled=bool(email_raw.get("enabled", False)),
            smtp_host=email_raw.get("smtp_host", ""),
            smtp_port=int(email_raw.get("smtp_port", 587)),
            use_tls=bool(email_raw.get("use_tls", True)),
            username=email_raw.get("username", ""),
            password=email_raw.get("password", ""),
            from_addr=email_raw.get("from_addr", ""),
            to_addrs=list(email_raw.get("to_addrs", [])),
        ),
        out_of_stock_keywords=list(
            keywords.get("out_of_stock", DEFAULT_OUT_OF_STOCK_KEYWORDS)
        ),
        in_stock_keywords=list(keywords.get("in_stock", DEFAULT_IN_STOCK_KEYWORDS)),
    )
