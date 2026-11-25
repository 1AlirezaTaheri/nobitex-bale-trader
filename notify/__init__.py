import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

COMMANDS = frozenset(
    {"/status", "/balance", "/positions", "/pnl", "/pause", "/resume", "/stop", "/mode", "/help"}
)
RESUME_CONFIRMATION = "/resume I UNDERSTAND THE RISK"
PORTFOLIO_COMMANDS = frozenset({"/portfolio", "/layers", "/risk", RESUME_CONFIRMATION})


def authorized_command(update: dict, chat_id: int, now: int, started: int) -> str | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat, sender, ts, text = (message.get(k) for k in ("chat", "from", "date", "text"))
    if (
        not isinstance(chat, dict)
        or chat.get("type") != "private"
        or chat.get("id") != chat_id
        or not isinstance(sender, dict)
        or sender.get("id") != chat_id
        or sender.get("is_bot")
        or type(ts) is not int
        or not max(started, now - 120) <= ts <= now + 5
        or "forward_date" in message
        or "forward_origin" in message
        or "sender_chat" in message
        or "edit_date" in message
        or not isinstance(text, str)
    ):
        return None
    return text.strip() if text.strip() in COMMANDS | PORTFOLIO_COMMANDS else None


class NotifyError(Exception):
    pass


class Notifier(ABC):
    @abstractmethod
    async def send(self, message: str) -> None: ...


class ConsoleNotifier(Notifier):
    async def send(self, message: str) -> None:
        print(message, flush=True)


class BaleNotifier(Notifier):
    def __init__(self, http: httpx.AsyncClient, token: str, chat_id: int):
        if not token or any(not (c.isascii() and (c.isalnum() or c in ":_-")) for c in token):
            raise NotifyError("Invalid Bale bot token format")
        self.http, self.token, self.chat_id = http, token, chat_id

    async def _call(self, method: str, data: dict, timeout: int) -> object:
        try:
            response = await self.http.post(
                f"https://tapi.bale.ai/bot{self.token}/{method}",
                json=data,
                timeout=timeout,
                follow_redirects=False,
            )
            if response.status_code != 200:
                raise NotifyError(f"Bale {method} failed (HTTP {response.status_code})")
            body = response.json()
            if not isinstance(body, dict) or body.get("ok") is not True:
                raise NotifyError(f"Bale {method} was rejected")
            return body.get("result")
        except (httpx.HTTPError, ValueError):
            raise NotifyError(f"Bale {method} unavailable") from None

    async def send(self, message: str) -> None:
        await self._call("sendMessage", {"chat_id": self.chat_id, "text": message[:3500]}, 8)

    async def poll(
        self,
        dispatch: Callable[[str], Awaitable[None]],
        stop: asyncio.Event,
        started: int,
        offset: int,
        save_offset: Callable[[int], None],
    ) -> None:
        failures = 0
        while not stop.is_set():
            try:
                batch = await self._call(
                    "getUpdates", {"offset": offset, "timeout": 20, "limit": 50}, 26
                )
                if not isinstance(batch, list):
                    raise NotifyError("Invalid Bale update batch")
                failures = 0
                valid = [
                    u for u in batch if isinstance(u, dict) and type(u.get("update_id")) is int
                ]
                for update in sorted(valid, key=lambda u: u["update_id"]):
                    if stop.is_set():
                        break
                    if update["update_id"] < offset:
                        continue
                    command = authorized_command(update, self.chat_id, int(time.time()), started)
                    if command:
                        await dispatch(command)
                    offset = update["update_id"] + 1
                    save_offset(offset)
                await asyncio.sleep(0.5)
            except NotifyError:
                failures += 1
                if failures in (1, 3):
                    print(
                        "Bale polling unavailable; local Ctrl+C and data/KILL remain available.",
                        flush=True,
                    )
                await asyncio.sleep(min(60, 2 ** min(failures, 6)))


@dataclass
class Outbox:
    notifier: Notifier

    def __post_init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)

    def emit(self, message: str) -> None:
        if self.queue.full():
            print("Notification queue full; console fallback: " + message, flush=True)
        else:
            self.queue.put_nowait(message)

    async def work(self) -> None:
        while True:
            message = await self.queue.get()
            try:
                await self.notifier.send(message)
            except NotifyError:
                print("Bale delivery failed; console fallback: " + message, flush=True)
            finally:
                self.queue.task_done()
            if isinstance(self.notifier, BaleNotifier):
                await asyncio.sleep(1.25)
