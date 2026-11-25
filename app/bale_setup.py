"""Explicit user-operated Bale setup; never called by doctor or tests over real HTTP."""

import argparse
import asyncio
import re
import secrets
import time

import httpx
from pydantic import ValidationError

from app.config import ROOT
from app.product_ops import (
    RECEIPT,
    BaleOptions,
    atomic_bytes,
    atomic_json,
    configure_stdio,
    disable_http_logs,
    receipt_binding,
)
from notify import NotifyError
from notify.product import ProductBale, diagnostic, owner_message


def save_chat(path, chat_id, expected_token):
    text = path.read_text(encoding="utf-8-sig")
    # Refuse a concurrent configuration edit; credentials are never printed.
    values = BaleOptions(_env_file=path)
    if not values.bale_bot_token or values.bale_bot_token.get_secret_value() != expected_token:
        raise ValueError("Configuration changed")
    if values.bale_chat_id not in (None, chat_id):
        raise ValueError("Existing owner differs; manual configuration required")
    line = "BALE_CHAT_ID=" + str(chat_id)
    text = (
        re.sub(r"(?m)^\s*BALE_CHAT_ID\s*=.*$", line, text)
        if re.search(r"(?m)^\s*BALE_CHAT_ID\s*=", text)
        else text.rstrip() + "\n" + line + "\n"
    )
    atomic_bytes(path, text.encode("utf-8"))


async def setup(options, find_chat, http, *, env_path=None, receipt_path=None, duration=90):
    if not options.bale_bot_token:
        raise ValueError("Token missing")
    token = options.bale_bot_token.get_secret_value()
    bot = ProductBale(http, token, options.bale_chat_id or 1)
    me = await bot.call("getMe")
    if not isinstance(me, dict) or me.get("is_bot") is not True:
        raise NotifyError("Invalid getMe response")
    if not find_chat:
        if not options.bale_chat_id:
            raise ValueError("Owner missing")
        await bot.send("آزمون صریح کاربر موفق بود. فقط PAPER/SHADOW؛ هیچ سفارش واقعی ارسال نمی‌شود.")
        atomic_json(
            receipt_path or RECEIPT,
            {
                "binding": receipt_binding(options),
                "user_test": True,
                "tested_utc_unix": int(time.time()),
            },
        )
        print(
            "درخواست پیام آزمایشی پذیرفته شد؛ دریافت آن را در بله بررسی کنید. شناسه نمایش داده نمی‌شود."
        )
        return 0
    info = await bot.call("getWebhookInfo")
    if not isinstance(info, dict) or info.get("url"):
        raise ValueError("Webhook active or invalid; no automatic changes")
    challenge = "/setup " + secrets.token_urlsafe(18)
    started, offset = int(time.time()), 0
    deadline = time.monotonic() + duration
    print("در گفتگوی خصوصی همین بازو، این عبارت یک‌بارمصرف را بفرستید: " + challenge, flush=True)
    while time.monotonic() < deadline:
        updates = await bot.call("getUpdates", {"offset": offset, "limit": 100, "timeout": 3})
        if not isinstance(updates, list):
            raise NotifyError("Invalid update batch")
        for update in updates:
            if not isinstance(update, dict) or type(update.get("update_id")) is not int:
                continue
            if update["update_id"] < offset:
                continue
            offset = update["update_id"] + 1
            message = update.get("message")
            chat = message.get("chat") if isinstance(message, dict) else None
            identity = chat.get("id") if isinstance(chat, dict) else None
            if owner_message(update, identity, int(time.time()), started, challenge):
                save_chat(env_path or ROOT / ".env", identity, token)
                print("گفتگوی مالک در .env ثبت شد؛ اکنون فرمان --test را اجرا کنید.", flush=True)
                return 0
        await asyncio.sleep(0.3)
    print("پیام تازه و معتبر دریافت نشد؛ هیچ شناسه‌ای ثبت نشد.")
    return 2


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--find-chat", action="store_true")
    group.add_argument("--test", action="store_true")
    args = parser.parse_args()
    disable_http_logs()
    try:
        options = BaleOptions()

        async def execute():
            async with httpx.AsyncClient(timeout=8, trust_env=False) as http:
                return await setup(options, args.find_chat, http)

        return asyncio.run(execute())
    except NotifyError as error:
        print(diagnostic(error))
    except (ValidationError, ValueError, OSError, RuntimeError):
        print(
            "راه‌اندازی رد شد؛ MODE باید paper باشد، توکن در .env و مالک معتبر لازم است. وب‌هوک خودکار تغییر نمی‌کند."
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
