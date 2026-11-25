"""Offline operational primitives. No transport is created at import time."""

import json
import logging
import math
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import ROOT
from app.logging_setup import SafeFormatter

PRODUCT = ROOT / "reports/final_product"
DEFAULT_ROOT = PRODUCT / "shadow_v2"
RECEIPT = ROOT / ".bale_verified.json"
MIN_FREE_BYTES = 100 * 1024 * 1024


class BaleOptions(BaseSettings):
    # Exchange keys are intentionally not read into this model.
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True, env_ignore_empty=True
    )
    mode: Literal["paper"] = "paper"
    bale_bot_token: SecretStr | None = None
    bale_chat_id: int | None = Field(default=None, gt=0, le=2**52)

    @field_validator("bale_bot_token")
    @classmethod
    def token_format(cls, value):
        if value and not re.fullmatch(r"[A-Za-z0-9:_-]{8,256}", value.get_secret_value()):
            raise ValueError("Invalid token format")
        return value


def disable_http_logs():
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).disabled = True


def configure_stdio():
    """Keep Persian CLI diagnostics safe in redirected Windows task output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def recording_options():
    try:
        return BaleOptions()
    except ValidationError as error:
        # Optional notification errors cannot stop public recording; MODE errors still do.
        if any(
            item["loc"] and item["loc"][0] == "mode" for item in error.errors(include_input=False)
        ):
            raise ValueError("Only PAPER mode is permitted") from None
        print("تنظیم بله نامعتبر است؛ ثبت عمومی با اعلان کنسولی ادامه می‌یابد. doctor را اجرا کنید.")
        return BaleOptions(_env_file=None, mode="paper", bale_bot_token=None, bale_chat_id=None)


def atomic_bytes(path, data):
    """Replace mutable state only; never use this for immutable evidence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pending_", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode())


def receipt_binding(options):
    if not options.bale_bot_token or options.bale_chat_id is None:
        raise ValueError("Bale configuration incomplete")
    return sha256(
        (options.bale_bot_token.get_secret_value() + ":" + str(options.bale_chat_id)).encode()
    ).hexdigest()


def delivery_verified(options, receipt=None):
    try:
        record = json.loads(Path(receipt or RECEIPT).read_bytes())
        return (
            isinstance(record, dict)
            and record.get("binding") == receipt_binding(options)
            and record.get("user_test") is True
        )
    except (OSError, ValueError, TypeError):
        return False


def disk_check(path, minimum=MIN_FREE_BYTES):
    path = Path(path)
    while not path.exists():
        path = path.parent
    free = shutil.disk_usage(path).free
    if free < minimum:
        raise ValueError("Insufficient free disk space")
    return free


def database_check(path):
    """Read-only check of an existing SQLite file, including current WAL state."""
    path = Path(path)
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2)
    ) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity failure")


def clock_check(previous_wall, previous_monotonic, wall, monotonic):
    if not all(math.isfinite(v) for v in (previous_wall, previous_monotonic, wall, monotonic)):
        raise ValueError("Nonfinite clock")
    if wall < previous_wall or abs((wall - previous_wall) - (monotonic - previous_monotonic)) > 30:
        raise ValueError("Clock discontinuity; restart observation checks")


def startup_checks(root):
    from app.forward_shadow import config_for, hashed, registration, safe_root

    root = safe_root(root)
    binding = registration(int(time.time()))
    # Reject an incompatible root before SQLite can create WAL/SHM sidecars.
    if (root / "configuration.json").exists():
        config = json.loads((root / "configuration.json").read_bytes())
        if hashed(config) != hashed(config_for(binding, config["fee"])):
            raise ValueError("Experiment fingerprint changed; use a new root")
    free = disk_check(root)
    for filename in ("shadow.db", "public_cache.db"):
        if (root / filename).exists():
            database_check(root / filename)
    marker = root / "clock.json"
    if marker.exists() and time.time() < json.loads(marker.read_bytes())["wall"]:
        raise ValueError("Clock predates previous product execution")
    return {"free_bytes": free, "independent_clock": "UNVERIFIED"}


def product_logger(root, options):
    disable_http_logs()
    directory = Path(root) / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("product-shadow")
    for old in logger.handlers[:]:
        old.close()
        logger.removeHandler(old)
    secrets = tuple(
        v
        for v in (
            options.bale_bot_token.get_secret_value() if options.bale_bot_token else None,
            str(options.bale_chat_id) if options.bale_chat_id else None,
        )
        if v
    )
    formatter = SafeFormatter(secrets)
    formatter.converter = time.gmtime
    handler = RotatingFileHandler(
        directory / "operations.jsonl", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
