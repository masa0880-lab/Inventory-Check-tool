"""在庫状態が変化したときの通知 (コンソール / Webhook / メール)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import requests

from .config import Config
from .checker import CheckResult

logger = logging.getLogger(__name__)


def _build_message(result: CheckResult, previous: str | None) -> tuple[str, str]:
    prev_label = previous or "（初回）"
    title = f"在庫状態が変化しました: {result.product.name}"
    body = (
        f"商品: {result.product.name}\n"
        f"URL: {result.product.url}\n"
        f"状態: {prev_label} → {result.status.label}\n"
        f"詳細: {result.detail}"
    )
    return title, body


def notify(config: Config, result: CheckResult, previous: str | None) -> None:
    """設定されているすべての通知チャネルへ送信する."""
    title, body = _build_message(result, previous)
    _dispatch(config, title, body)


def send_test(config: Config) -> None:
    """在庫状態に関係なく、テスト通知を送る (Discord 連携の動作確認用)."""
    title = "🔔 テスト通知 (在庫チェックツール)"
    body = (
        "これはテスト通知です。\n"
        "このメッセージが届いていれば、通知の連携は正常に動いています。\n"
        "実際の在庫通知は、商品が「在庫あり」に変化したときに届きます。"
    )
    _dispatch(config, title, body)


def _dispatch(config: Config, title: str, body: str) -> None:
    """各通知チャネル (コンソール / Webhook / メール) へ送信する."""
    if config.console:
        print("\n" + "=" * 50)
        print(f"🔔 {title}")
        print(body)
        print("=" * 50 + "\n", flush=True)

    if config.webhook.enabled and config.webhook.url:
        try:
            _send_webhook(config, title, body)
        except Exception as exc:  # noqa: BLE001 - 通知失敗で処理を止めない
            logger.error("Webhook通知に失敗しました: %s", exc)

    if config.email.enabled:
        try:
            _send_email(config, title, body)
        except Exception as exc:  # noqa: BLE001
            logger.error("メール通知に失敗しました: %s", exc)


def _send_webhook(config: Config, title: str, body: str) -> None:
    text = f"*{title}*\n{body}"
    fmt = config.webhook.format.lower()
    if fmt == "discord":
        payload = {"content": text}
    elif fmt == "raw":
        payload = {"title": title, "body": body}
    else:  # slack (default)
        payload = {"text": text}

    resp = requests.post(config.webhook.url, json=payload, timeout=15)
    resp.raise_for_status()


def _send_email(config: Config, title: str, body: str) -> None:
    email = config.email
    if not email.to_addrs:
        logger.warning("メール通知が有効ですが to_addrs が空です")
        return

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = title
    msg["From"] = email.from_addr or email.username
    msg["To"] = ", ".join(email.to_addrs)

    with smtplib.SMTP(email.smtp_host, email.smtp_port, timeout=20) as server:
        if email.use_tls:
            server.starttls()
        if email.username:
            server.login(email.username, email.password)
        server.send_message(msg)
