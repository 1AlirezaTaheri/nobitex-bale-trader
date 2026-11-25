"""Product orchestration around the unchanged SHADOW account economics."""

import argparse
import asyncio
import json
import math
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from app import forward_shadow
from app.forward_report import summarize
from app.product_ops import (
    DEFAULT_ROOT,
    PRODUCT,
    atomic_json,
    clock_check,
    configure_stdio,
    delivery_verified,
    disk_check,
    product_logger,
    recording_options,
    startup_checks,
)
from app.product_weekly import persian_summary
from data.store import single_instance
from exchange.base import ExchangeError
from notify import NotifyError
from notify.product import Delivery, ProductBale, shadow_command

HELP = "فقط SHADOW: /status وضعیت، /help راهنما، /pause توقف ثبت، /resume ادامه ثبت، /stop توقف محلی پایدار، /report خلاصه. وقفه بازسازی نمی‌شود."


class Controls:
    def __init__(self, root, delivery):
        self.root, self.delivery = Path(root), delivery

    async def dispatch(self, command):
        if command == "/stop":
            atomic_json(self.root / "KILL", {"local_shadow_stop": True})
            self.delivery.emit(
                "SHADOW متوقف شد؛ هیچ سفارش یا موجودی صرافی تغییر نکرد. شروع دوباره نیازمند حذف دستی KILL همین ریشه است."
            )
        elif command == "/pause":
            atomic_json(self.root / "PAUSE", {"paused": True})
            self.delivery.emit(
                "ثبت SHADOW مکث شد؛ مرزهای ازدست‌رفته بازسازی نمی‌شوند و مواجهه اقتصادی قبلی حذف نمی‌شود."
            )
        elif command == "/resume":
            self.root.joinpath("PAUSE").unlink(missing_ok=True)
            self.delivery.emit("ثبت در مرز واقعی بعدی از سر گرفته می‌شود؛ LIVE فعال نشده است.")
        elif command in ("/status", "/report"):
            summary, _ = summarize(self.root)
            state = "مکث" if (self.root / "PAUSE").exists() else "در حال مشاهده"
            self.delivery.emit("وضعیت ثبت: " + state + "\n" + persian_summary(summary))
        elif command == "/help":
            self.delivery.emit(HELP)


async def poll(bot, controls, stop, started):
    offset_path = controls.root / "bale_offset.json"
    try:
        offset = json.loads(offset_path.read_bytes())["offset"] if offset_path.exists() else 0
        if type(offset) is not int or offset < 0:
            raise ValueError("Invalid notification offset")
    except (OSError, ValueError, TypeError, KeyError):
        controls.delivery.emit("کنترل بله به علت خطای نشانگر محلی غیرفعال شد؛ doctor را اجرا کنید.")
        return
    failures = 0
    while not stop.is_set():
        try:
            batch = await bot.call("getUpdates", {"offset": offset, "limit": 100, "timeout": 3})
            if not isinstance(batch, list):
                raise NotifyError("Invalid updates")
            for update in sorted(
                (u for u in batch if isinstance(u, dict) and type(u.get("update_id")) is int),
                key=lambda u: u["update_id"],
            ):
                if update["update_id"] < offset or stop.is_set():
                    continue
                command = shadow_command(update, bot.chat_id, int(time.time()), started)
                offset = update["update_id"] + 1
                atomic_json(offset_path, {"offset": offset})
                if command:
                    await controls.dispatch(command)
            failures = 0
            delay = 0.5
        except NotifyError:
            failures += 1
            if failures in (1, 5):
                controls.delivery.emit(
                    "دریافت فرمان بله قطع است؛ کنترل محلی PAUSE/KILL و Ctrl+C در دسترس است."
                )
            delay = min(60, 2 ** min(failures, 6))
        except (ValueError, OSError, KeyError):
            controls.delivery.emit(
                "کنترل بله به علت خطای وضعیت محلی غیرفعال شد؛ doctor را اجرا کنید."
            )
            return
        try:
            await asyncio.wait_for(stop.wait(), delay)
        except TimeoutError:
            pass


async def monitor(root, delivery, stop):
    previous_wall, previous_mono = time.time(), time.monotonic()
    last_day = datetime.fromtimestamp(previous_wall, UTC).date()
    last_heartbeat, last_gap, last_count = previous_mono, None, None
    while not stop.is_set():
        wall, mono = time.time(), time.monotonic()
        clock_check(previous_wall, previous_mono, wall, mono)
        previous_wall, previous_mono = wall, mono
        disk_check(root)
        atomic_json(root / "clock.json", {"wall": wall})
        summary, _ = summarize(root, int(wall))
        gap = len(summary["missing_boundaries"]) + len(
            summary["outstanding_missed_boundaries_after_last_snapshot"]
        )
        if gap and gap != last_gap:
            delivery.emit(
                f"هشدار شکاف SHADOW: {gap} مرز روزانه مشاهده نشده؛ هیچ قیمت یا معامله‌ای بازسازی نمی‌شود."
            )
        last_gap = gap
        if summary["snapshots"] and summary["snapshots"] != last_count:
            delivery.emit(
                f"ثبت واقعی SHADOW ذخیره شد؛ تعداد کل {summary['snapshots']}؛ بازه کامل {summary['observed_intervals']}."
            )
        last_count = summary["snapshots"]
        day = datetime.fromtimestamp(wall, UTC).date()
        if day != last_day:
            delivery.emit("گزارش روزانه UTC\n" + persian_summary(summary))
            last_day = day
        if mono - last_heartbeat >= 4 * 3600:
            delivery.emit(
                f"ضربان SHADOW: فرایند روشن است؛ {summary['snapshots']} ثبت واقعی. روشن بودن معادل عملکرد نیست."
            )
            last_heartbeat = mono
        try:
            await asyncio.wait_for(stop.wait(), 15)
        except TimeoutError:
            pass


async def run(args):
    if args.mode != "shadow" or not math.isfinite(args.max_seconds) or args.max_seconds < 0:
        raise ValueError("Invalid mode/runtime; LIVE blocked")
    options = recording_options()  # Reject MODE=live; optional Bale errors fall back to console.
    root = forward_shadow.safe_root(args.root)
    if not root.is_relative_to(PRODUCT.resolve()):
        raise ValueError("Product requires its own final_product experiment root")
    startup_checks(root)
    root.mkdir(parents=True, exist_ok=True)
    with single_instance(root / "product.lock"):
        if (root / "KILL").exists():
            raise ValueError("Local KILL exists")
        logger = product_logger(root, options)
        async with httpx.AsyncClient(timeout=8, trust_env=False) as http:
            bot = None
            if args.bale and delivery_verified(options):
                bot = ProductBale(
                    http, options.bale_bot_token.get_secret_value(), options.bale_chat_id
                )
                try:
                    info = await bot.call("getWebhookInfo")
                    if not isinstance(info, dict) or info.get("url"):
                        bot = None
                except NotifyError:
                    bot = None
            if args.bale and bot is None:
                print(
                    "بله فعال نشد؛ آزمون صریح کاربر یا اتصال معتبر موجود نیست. اعلان کنسولی فعال است."
                )
            delivery = Delivery(bot, logger)
            worker = asyncio.create_task(delivery.work())
            stop = asyncio.Event()
            controls = Controls(root, delivery)
            tasks = []
            delivery.emit(
                "شروع مشاهده SHADOW نسخه product-shadow-v2؛ معامله واقعی مسدود است. تا مرز واقعی ثبت آینده‌نگر نداریم."
            )
            try:
                recorder = asyncio.create_task(forward_shadow.run(args))
                watcher = asyncio.create_task(monitor(root, delivery, stop))
                tasks.extend((recorder, watcher))
                if bot:
                    tasks.append(
                        asyncio.create_task(poll(bot, controls, stop, int(time.time()) + 1))
                    )
                done, _ = await asyncio.wait(
                    (recorder, watcher), return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    await task
                return 0
            except Exception:
                delivery.emit(
                    "هشدار: ثبت SHADOW متوقف شد؛ خطای داده، ساعت یا ذخیره‌سازی. doctor را اجرا کنید؛ هیچ سفارش واقعی ارسال نشده است."
                )
                raise
            finally:
                stop.set()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                delivery.emit(
                    "پایان فرایند SHADOW؛ گزارش محلی را بررسی کنید. این پیام تضمین دریافت در بله نیست."
                )
                await delivery.close(worker)
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--mode", default="shadow")
    parser.add_argument("--max-seconds", type=float, default=0)
    parser.add_argument("--bale", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0
    except (
        ValueError,
        OSError,
        RuntimeError,
        sqlite3.Error,
        httpx.HTTPError,
        ExchangeError,
        ValidationError,
        StopIteration,
        KeyError,
    ):
        print(
            "SHADOW شروع نشد یا متوقف شد؛ doctor را اجرا کنید. LIVE مسدود است؛ جزئیات محرمانه نمایش داده نمی‌شود."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
