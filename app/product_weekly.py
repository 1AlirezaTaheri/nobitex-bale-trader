"""Generate a fresh local weekly report; optional delivery requires a user-test receipt."""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.forward_report import generate
from app.product_ops import (
    DEFAULT_ROOT,
    PRODUCT,
    configure_stdio,
    delivery_verified,
    disable_http_logs,
    recording_options,
)
from notify.product import Delivery, ProductBale


def persian_summary(summary):
    text = [
        "گزارش SHADOW؛ راهبردها اعتبارسنجی نشده‌اند و سود تضمین‌شده نیست.",
        f"ثبت واقعی: {summary['snapshots']}؛ بازه روزانه کامل: {summary['observed_intervals']}.",
        "وقفه در مشاهده: "
        + ("بله؛ ارزیابی پیوسته معتبر نیست." if summary["interrupted"] else "فعلاً ثبت نشده است."),
    ]
    if not summary["snapshots"]:
        text.append("هنوز داده آینده‌نگر نداریم؛ اعداد اولیه عملکرد محسوب نمی‌شوند.")
    else:
        for name in ("A", "D", "B1", "B4_25", "B4_50", "B4_75"):
            row = summary["accounts"][name]
            text.append(
                f"{name}: بازده {row['net_return']:+.2%}؛ افت {row['max_drawdown']:.2%}؛ هزینه {row['costs']:.3f} USDT"
            )
    for months in ("3", "6", "12"):
        statuses = summary["checkpoints"][months]["candidates"]
        text.append(
            f"بازبینی {months} ماه: "
            + "; ".join(f"{name}={v['status']}" for name, v in statuses.items())
        )
    text.append("گذر از بازبینی فقط ادامه مشاهده است؛ اجازه معامله واقعی نیست.")
    if summary["latest_hash"]:
        text.append("اثر زنجیره برای نگهداری مستقل: " + summary["latest_hash"])
    return "\n".join(text)


async def deliver(summary, output, http, options, receipt=None):
    notifier = (
        ProductBale(http, options.bale_bot_token.get_secret_value(), options.bale_chat_id)
        if delivery_verified(options, receipt)
        else None
    )
    if notifier is None:
        print("آزمون صریح بله تأیید نشده؛ خروجی فقط محلی است.")
    box = Delivery(notifier)
    task = asyncio.create_task(box.work())
    box.emit(persian_summary(summary), Path(output) / "weekly.png")
    await box.close(task)


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bale", action="store_true")
    args = parser.parse_args()
    output = args.output or PRODUCT / ("weekly_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    disable_http_logs()
    try:
        options = recording_options()
        summary = generate(args.root, output)
        (output / "weekly.fa.txt").write_text(persian_summary(summary) + "\n", encoding="utf-8")
        print(persian_summary(summary))
        if args.bale:

            async def execute():
                async with httpx.AsyncClient(timeout=8, trust_env=False) as http:
                    await deliver(summary, output, http, options)

            asyncio.run(execute())
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, ValidationError):
        print("گزارش ساخته نشد؛ ریشه، ساعت و تمامیت داده محلی را با doctor بررسی کنید.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
