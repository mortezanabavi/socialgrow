import requests
import json
import logging

import os

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_admin_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "0")
TELEGRAM_ADMIN_CHAT_ID = int(_admin_id) if _admin_id.isdigit() else 0
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_telegram_message(text, chat_id=None, reply_to_message_id=None, reply_markup=None):
    """
    Sends a text message to Telegram admin.
    """
    if chat_id is None:
        chat_id = TELEGRAM_ADMIN_CHAT_ID

    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=12)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", {})
        else:
            logger.error(f"Telegram sendMessage error: {data}")
            return None
    except Exception as e:
        logger.error(f"Telegram sendMessage exception: {e}")
        return None


def notify_admin_new_user_message(session, message):
    """
    Sends notification to admin when user posts a message.
    """
    user_label = session.name or session.phone_or_email
    if not user_label and session.user:
        user_label = session.user.phone_number or session.user.email
    if not user_label:
        user_label = f"کاربر مهمان #{session.id}"

    user_info = f"👤 <b>کاربر:</b> {user_label}"
    if session.phone_or_email:
        user_info += f"\n📞 <b>تماس:</b> <code>{session.phone_or_email}</code>"

    text = (
        f"💬 <b>پیام جدید از پشتیبانی آنلاین سوشال گرو</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>شناسه گفتگو:</b> <code>#{session.id}</code>\n"
        f"{user_info}\n\n"
        f"✉️ <b>پیام کاربر:</b>\n"
        f"<blockquote>{message.text}</blockquote>\n\n"
        f"💡 <i>برای پاسخ دادن به این پیام، کافیست روی همین پیام در تلگرام Reply کنید.</i>"
    )

    result = send_telegram_message(text)
    if result:
        tg_msg_id = result.get("message_id")
        message.telegram_msg_id = tg_msg_id
        message.save(update_fields=["telegram_msg_id"])

        if not session.telegram_thread_msg_id:
            session.telegram_thread_msg_id = tg_msg_id
            session.save(update_fields=["telegram_thread_msg_id"])
        return tg_msg_id
    return None
