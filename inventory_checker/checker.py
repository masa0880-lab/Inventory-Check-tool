"""商品ページを取得し在庫状態を判定する."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import requests
from bs4 import BeautifulSoup

from .config import Config, Product


class StockStatus(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"
    ERROR = "error"

    @property
    def label(self) -> str:
        return {
            StockStatus.IN_STOCK: "在庫あり",
            StockStatus.OUT_OF_STOCK: "在庫なし",
            StockStatus.UNKNOWN: "判定不能",
            StockStatus.ERROR: "取得エラー",
        }[self]


@dataclass
class CheckResult:
    product: Product
    status: StockStatus
    detail: str = ""


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw and kw in text]


def determine_status(
    text: str,
    out_of_stock_keywords: list[str],
    in_stock_keywords: list[str],
) -> tuple[StockStatus, str]:
    """ページ本文テキストから在庫状態を判定する.

    判定順序:
      1. 在庫なしを示す語が含まれていれば OUT_OF_STOCK
      2. 在庫ありを示す語 (例: カートに入れる) が含まれていれば IN_STOCK
      3. どちらも無ければ UNKNOWN
    在庫なしのフレーズは具体的なため優先して評価する。
    """
    out_hits = _matched_keywords(text, out_of_stock_keywords)
    if out_hits:
        return StockStatus.OUT_OF_STOCK, "一致: " + ", ".join(out_hits)

    in_hits = _matched_keywords(text, in_stock_keywords)
    if in_hits:
        return StockStatus.IN_STOCK, "一致: " + ", ".join(in_hits)

    return StockStatus.UNKNOWN, "在庫を示すキーワードが見つかりませんでした"


def check_product(
    product: Product, config: Config, session: requests.Session | None = None
) -> CheckResult:
    """1商品の在庫状態をチェックする."""
    out_kw = product.out_of_stock or config.out_of_stock_keywords
    in_kw = product.in_stock or config.in_stock_keywords

    sess = session or requests.Session()
    # 実ブラウザに近いヘッダーを送る(一部サイトはこれが無いと 403/404 を返すため)
    headers = {
        "User-Agent": config.user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    try:
        resp = sess.get(
            product.url,
            headers=headers,
            timeout=config.request_timeout_seconds,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return CheckResult(product, StockStatus.ERROR, f"リクエスト失敗: {exc}")

    # 文字化け対策: requests の推定にまかせつつ、apparent_encoding をフォールバックに使う
    if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding

    soup = BeautifulSoup(resp.text, "html.parser")
    # スクリプト/スタイルを除いた可視テキストで判定 (ノイズ低減)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    visible_text = soup.get_text(separator=" ", strip=True)

    status, detail = determine_status(visible_text, out_kw, in_kw)
    return CheckResult(product, status, detail)
