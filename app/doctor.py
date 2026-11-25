"""Offline Persian diagnostics: no HTTP client, no exchange/Bale requests."""

import argparse
import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.config import ROOT, ConfigError, load
from app.forward_report import summarize
from app.forward_shadow import config_for, hashed, registration, safe_root
from app.portfolio_config import load_portfolio
from app.product_ops import (
    DEFAULT_ROOT,
    BaleOptions,
    configure_stdio,
    database_check,
    delivery_verified,
    startup_checks,
)
from app.timing_config import load_timing


def diagnose(root):
    checks = []

    def check(name, operation):
        try:
            detail = operation()
            checks.append({"check": name, "status": "PASS", "detail": detail})
        except (
            OSError,
            ValueError,
            ConfigError,
            KeyError,
            TypeError,
            sqlite3.Error,
            ValidationError,
        ):
            checks.append(
                {
                    "check": name,
                    "status": "FAIL",
                    "detail": "خطا؛ تنظیمات یا داده محلی را بررسی کنید. مقدار محرمانه نمایش داده نمی‌شود.",
                }
            )

    def configuration():
        settings, *_ = load()
        portfolio, *_ = load_portfolio()
        timing = load_timing()
        if settings.mode != "paper" or portfolio.enabled or timing.enabled:
            raise ValueError("Only disabled PAPER experiments expected")
        return "تنظیمات معتبر؛ PAPER و پیش‌فرض راهبردها غیرفعال."

    root = safe_root(root)
    check("پیکربندی و مسدودبودن LIVE", configuration)
    check("دیسک، SQLite ریشه و ساعت محلی", lambda: startup_checks(root))
    check(
        "پیش‌ثبت و حداقل تاریخ",
        lambda: {
            "not_before": registration(int(time.time()))["not_before"],
            "independent_utc": "UNVERIFIED",
            "local_utc": datetime.now(UTC).isoformat(),
        },
    )

    def chain():
        summary, _ = summarize(root)
        if (root / "configuration.json").exists():
            config = json.loads((root / "configuration.json").read_bytes())
            expected = config_for(registration(int(time.time())), config["fee"])
            if hashed(config) != hashed(expected):
                raise ValueError("Old experiment source fingerprint")
        return {
            "snapshots": summary["snapshots"],
            "intervals": summary["observed_intervals"],
            "interrupted": summary["interrupted"],
            "pause": (root / "PAUSE").exists(),
            "kill": (root / "KILL").exists(),
        }

    check("زنجیره و سازگاری آزمایش", chain)
    for path in sorted((ROOT / "data").glob("*.db")):
        check("SQLite محلی " + path.name, lambda p=path: database_check(p) or "ok")
    try:
        options = BaleOptions()
        bale = (
            "آزمون صریح کاربر ثبت شده؛ تحویل فعلی بررسی نشده."
            if delivery_verified(options)
            else "غیرفعال یا آزمون صریح کاربر انجام نشده؛ کنسول در دسترس است."
        )
    except ValidationError:
        bale = "پیکربندی بله نامعتبر؛ مقادیر نمایش داده نمی‌شود."
    checks.append({"check": "بله (بدون اتصال)", "status": "UNVERIFIED", "detail": bale})
    checks.append(
        {
            "check": "سخت‌افزار، خواب، زمان‌بند، آسیب‌پذیری و عملکرد آینده",
            "status": "UNVERIFIED",
            "detail": "در این بررسی آفلاین آزموده نمی‌شود.",
        }
    )
    return {"offline": True, "checks": checks, "failed": sum(c["status"] == "FAIL" for c in checks)}


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        result = diagnose(args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result["failed"] else 0
    except (OSError, ValueError, KeyError):
        print("بررسی آفلاین رد شد؛ ریشه معتبر لازم است. هیچ اتصالی برقرار نشد.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
