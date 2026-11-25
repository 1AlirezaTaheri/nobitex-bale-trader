import json
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import Settings


class SafeFormatter(logging.Formatter):
    def __init__(self, secrets: tuple[str, ...]):
        super().__init__()
        self.secrets = secrets

    def format(self, record: logging.LogRecord) -> str:
        text = record.getMessage()
        for value in self.secrets:
            if value:
                text = text.replace(value, "[REDACTED]")
        text = re.sub(r"(?i)(/bot)[^/\s]+", r"\1[REDACTED]", text)
        # No external response bodies, HTTP URLs, headers, settings dumps, or raw tracebacks.
        return json.dumps(
            {
                "utc": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + "Z",
                "level": record.levelname,
                "event": text,
            },
            ensure_ascii=True,
        )


def configure(settings: Settings, directory: Path) -> logging.Logger:
    import time

    directory.mkdir(parents=True, exist_ok=True)
    values = (settings.nobitex_public_key, settings.nobitex_private_key, settings.bale_bot_token)
    formatter = SafeFormatter(tuple(v.get_secret_value() for v in values if v))
    formatter.converter = time.gmtime
    logger = logging.getLogger("trader")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(settings.log_level)
    handler = RotatingFileHandler(
        directory / "bot.jsonl", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).disabled = True
    return logger
