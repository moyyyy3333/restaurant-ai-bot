"""Best-effort operator alerts that never block payment processing."""

import json
import urllib.parse
import urllib.request

from config import ADMIN_USER_IDS, TELEGRAM_BOT_TOKEN, TELEGRAM_NOTIFY_CHAT_ID


def telegram_chat_ids() -> list[str]:
    if TELEGRAM_NOTIFY_CHAT_ID:
        return [TELEGRAM_NOTIFY_CHAT_ID]
    return [str(user_id) for user_id in ADMIN_USER_IDS]


def notify_admin(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not telegram_chat_ids():
        print("  ! Telegram payment alert skipped: notification chat is not configured")
        return False
    delivered = False
    for chat_id in telegram_chat_ids():
        body = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=body,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                delivered = bool(json.load(response).get("ok")) or delivered
        except Exception as exc:
            print(f"  ! Telegram payment alert failed: {exc}")
    return delivered
