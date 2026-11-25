import sys

from app.config import ConfigError, Settings
from exchange.nobitex import Spec

CONFIRMATION = "I UNDERSTAND THE RISK"
CHECKLIST = (
    "Review backtest and benchmark, including trade count and weaknesses.",
    "Complete 2–4 weeks of paper trading and compare results with the backtest.",
    "Run verify_exchange and resolve every UNVERIFIED live contract.",
    "Confirm exchange-side protection or consciously set ALLOW_UNPROTECTED_POSITIONS=true.",
    "Set MAX_CAPITAL_QUOTE to an amount you can afford to lose.",
    "Test data/KILL, cancellation, and all Bale commands in PAPER mode.",
)


def live_startup(settings: Settings, spec: Spec) -> None:
    if settings.mode != "live":
        return
    print("PAPER-TO-LIVE CHECKLIST:", flush=True)
    for item in CHECKLIST:
        print(f"  [ ] {item}", flush=True)
    print(
        "WARNING: No confirmed exchange-side protection; any acquired BTC would be unprotected offline.",
        flush=True,
    )
    blockers = [f"UNVERIFIED {name}" for name in spec.unverified()]
    if not settings.allow_unprotected_positions:
        blockers.append(
            "ALLOW_UNPROTECTED_POSITIONS=true required without verified native protection"
        )
    if not settings.nobitex_private_key or not settings.nobitex_public_key:
        blockers.append("Nobitex API key pair missing")
    if not sys.stdin.isatty():
        blockers.append("interactive local console required")
    if blockers:
        raise ConfigError("LIVE blocked: " + "; ".join(blockers))
    try:
        accepted = input(f"Acknowledge each item by typing {CONFIRMATION}: ") == CONFIRMATION
    except EOFError:
        accepted = False
    if not accepted:
        raise ConfigError("LIVE confirmation declined")
    raise ConfigError("This build has no certified live order transport")
