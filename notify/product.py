"""Official Bale transport and bounded best-effort SHADOW delivery."""

import asyncio
from pathlib import Path

import httpx

from notify import BaleNotifier, ConsoleNotifier, NotifyError, authorized_command

SHADOW_COMMANDS = frozenset({"/status", "/help", "/pause", "/resume", "/stop", "/report"})


def owner_message(update, chat_id, now, started, expected):
    if not isinstance(update, dict) or type(chat_id) is not int or chat_id <= 0:
        return False
    message = update.get("message")
    if not isinstance(message, dict) or any(str(k).startswith("forward_") for k in message):
        return False
    if message.get("text") != expected:
        return False
    if any(
        not isinstance(message.get(key), dict) or type(message[key].get("id")) is not int
        for key in ("chat", "from")
    ):
        return False
    # Reuse the existing private sender/chat/time checks without widening legacy commands.
    proxy = {**update, "message": {**message, "text": "/status"}}
    return authorized_command(proxy, chat_id, now, started) == "/status"


def shadow_command(update, chat_id, now, started):
    message = update.get("message", {}) if isinstance(update, dict) else {}
    text = message.get("text") if isinstance(message, dict) else None
    if isinstance(text, str) and text in SHADOW_COMMANDS:
        return text if owner_message(update, chat_id, now, started, text) else None
    return None


class ProductBale(BaleNotifier):
    async def send(self, message):
        result = await self._call(
            "sendMessage", {"chat_id": self.chat_id, "text": message[:3500]}, 8
        )
        if not isinstance(result, dict) or type(result.get("message_id")) is not int:
            raise NotifyError("Invalid sendMessage acknowledgement")

    async def call(self, method, data=None):
        if method not in {"getMe", "getWebhookInfo", "getUpdates"}:
            raise NotifyError("Unsupported setup method")
        return await self._call(method, data or {}, 8)

    async def photo(self, path, caption):
        try:
            picture = Path(path).read_bytes()
            if not picture.startswith(b"\x89PNG\r\n\x1a\n") or len(picture) > 8_000_000:
                raise NotifyError("Invalid report image")
            response = await self.http.post(
                f"https://tapi.bale.ai/bot{self.token}/sendPhoto",
                data={"chat_id": str(self.chat_id), "caption": caption[:900]},
                files={"photo": ("weekly.png", picture, "image/png")},
                timeout=8,
                follow_redirects=False,
            )
            if response.status_code != 200:
                raise NotifyError(f"Bale sendPhoto failed (HTTP {response.status_code})")
            body = response.json()
            if not isinstance(body, dict) or body.get("ok") is not True:
                raise NotifyError("Bale sendPhoto rejected")
            result = body.get("result")
            if not isinstance(result, dict) or type(result.get("message_id")) is not int:
                raise NotifyError("Invalid sendPhoto acknowledgement")
        except (httpx.HTTPError, ValueError, OSError):
            raise NotifyError("Bale sendPhoto unavailable") from None


def diagnostic(error):
    # Only our transport's fixed messages are inspected, never emitted.
    text = str(error) if isinstance(error, NotifyError) else ""
    for code, message in (
        ("401", "توکن بله پذیرفته نشد؛ مقدار محلی را بررسی کنید."),
        ("403", "دسترسی بله رد شد؛ شروع گفتگوی خصوصی و مجوز بازو را بررسی کنید."),
        ("429", "محدودیت درخواست بله؛ بعداً دوباره تلاش کنید."),
    ):
        if code in text:
            return message
    return "ارتباط یا پاسخ بله معتبر نبود؛ اینترنت، تنظیمات و وضعیت سرویس را بررسی کنید."


class Delivery:
    def __init__(self, notifier=None, logger=None):
        self.notifier = notifier or ConsoleNotifier()
        self.logger = logger
        self.queue = asyncio.Queue(maxsize=32)

    def emit(self, message, photo=None):
        if self.logger:
            self.logger.info(message)
        if self.queue.full():
            print("صف اعلان پر است؛ " + message, flush=True)
        else:
            self.queue.put_nowait((message, photo))

    async def work(self):
        while True:
            message, photo = await self.queue.get()
            try:
                await self.notifier.send(message)
                if photo and isinstance(self.notifier, ProductBale):
                    await self.notifier.photo(photo, "فقط SHADOW؛ بدون معامله واقعی یا تضمین سود")
            except Exception:
                # A failing notifier must not crash the recorder; never expose exception text.
                print("ارسال اعلان ناموفق؛ کنسول: " + message, flush=True)
            finally:
                self.queue.task_done()
            if isinstance(self.notifier, ProductBale):
                await asyncio.sleep(1.25)

    async def close(self, worker):
        try:
            await asyncio.wait_for(self.queue.join(), 18)
        except TimeoutError:
            print("مهلت ارسال اعلان پایان یافت؛ گزارش محلی مرجع است.", flush=True)
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
