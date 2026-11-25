import argparse
import asyncio
import contextlib
import signal
import sqlite3
import time

import httpx

from app.config import ROOT, ConfigError, load
from app.engine import Engine
from app.logging_setup import configure
from app.portfolio_config import load_portfolio
from app.portfolio_engine import PortfolioEngine
from app.safety import live_startup
from app.timing_config import load_timing
from app.timing_engine import TimingEngine
from app.universe import DailyHistory
from data.history import History
from data.store import Store, single_instance
from exchange.base import ExchangeError
from exchange.nobitex import NobitexClient, Spec
from exchange.paper import PaperExchange
from execution import ReconcileError
from notify import BaleNotifier, ConsoleNotifier, NotifyError, Outbox
from strategy.timing import Candidate


def install_signals(engine: Engine):
    loop = asyncio.get_running_loop()
    previous = {}
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        value = getattr(signal, name, None)
        if value is not None:
            previous[value] = signal.signal(
                value, lambda *_: loop.call_soon_threadsafe(engine.stop.set)
            )
    handler = None
    try:
        import ctypes
        import os

        if os.name == "nt":
            # Windows grants only a short best-effort grace period for close/logoff/shutdown events.
            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
            def handler(event):
                if event in {0, 1, 2, 5, 6}:
                    loop.call_soon_threadsafe(engine.stop.set)
                    return True
                return False

            ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True)
    except (AttributeError, OSError):
        pass

    def restore():
        for value, callback in previous.items():
            signal.signal(value, callback)
        if handler is not None:
            with contextlib.suppress(AttributeError, OSError):
                import ctypes

                ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, False)

    return restore


async def run(
    smoke_seconds: int | None,
    portfolio_paper: bool = False,
    timing_paper: bool = False,
    timing_candidate: str | None = None,
) -> int:
    settings, cfg, risk, app = load()
    spec = Spec.load()
    if timing_paper and settings.mode != "paper":
        raise ConfigError("Daily timing PAPER is explicitly PAPER-only; LIVE is blocked")
    if timing_candidate is not None and not timing_paper:
        raise ConfigError("--timing-candidate requires explicit --timing-paper")
    if portfolio_paper and timing_paper:
        raise ConfigError("Choose exactly one isolated PAPER strategy")
    live_startup(settings, spec)
    p_cfg, p_limits, universe = load_portfolio()
    timing_cfg = load_timing() if timing_paper else None
    candidate = Candidate(timing_candidate or (timing_cfg.candidate if timing_cfg else "A"))
    timing_symbols = ("BTC/USDT", "ETH/USDT") if candidate == Candidate.D else ("BTC/USDT",)
    if timing_paper and not set(timing_symbols).issubset(timing_cfg.symbols):
        raise ConfigError(
            "Timing PAPER configuration omits an asset required by the selected candidate"
        )
    if timing_paper and p_cfg.enabled:
        raise ConfigError(
            "Disable the separate LayeredPortfolio configuration before selecting timing PAPER"
        )
    use_timing = timing_paper
    use_portfolio = not use_timing and (portfolio_paper or p_cfg.enabled)
    if use_portfolio and settings.mode != "paper":
        raise ConfigError("LayeredPortfolio is research PAPER only; LIVE is forbidden")
    if smoke_seconds is not None and (use_portfolio or use_timing) and settings.mode != "paper":
        raise ConfigError("Smoke runs are PAPER only")
    directory = ROOT / app.data_directory
    kill = directory / "KILL"
    if kill.exists():
        raise ConfigError(
            "data/KILL exists. Trading remains stopped. Review positions before removing it."
        )
    if smoke_seconds is not None and settings.mode != "paper":
        raise ConfigError("Smoke runs are PAPER only")
    logger = configure(settings, ROOT / "logs")
    state_name = (
        f"timing_v3_{candidate.value}_paper.db"
        if use_timing
        else "portfolio_paper.db"
        if use_portfolio
        else "paper.db"
    )
    candle_name = "timing_v3_candles.db" if use_timing else "candles.db"
    if (
        use_timing
        and not (directory / candle_name).exists()
        and (directory / "candles.db").exists()
    ):
        # SQLite's backup API reads a consistent snapshot, leaving the old cache untouched.
        with (
            sqlite3.connect((directory / "candles.db").as_uri() + "?mode=ro", uri=True) as source,
            sqlite3.connect(directory / candle_name) as target,
        ):
            source.backup(target)
    async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=5), trust_env=False) as http:
        with (
            Store(directory / state_name) as store,
            Store(directory / candle_name) as candle_store,
        ):
            market = NobitexClient(spec, http)  # Never pass private keys to public PAPER transport.
            observed_fee = await market.get_fees(cfg.symbol)
            risk = risk.model_copy(update={"fee": max(risk.fee, observed_fee)})
            exchange = PaperExchange(
                market,
                store,
                min(app.paper_cash, settings.max_capital_quote),
                risk.fee,
                risk.slippage,
                settings.max_capital_quote,
                app.book_max_age_seconds,
                symbols=(
                    timing_symbols
                    if use_timing
                    else universe.symbols
                    if use_portfolio
                    else (cfg.symbol,)
                ),
                allow_additions=use_timing,
            )
            notifier = (
                BaleNotifier(
                    http, settings.bale_bot_token.get_secret_value(), settings.bale_chat_id
                )
                if not use_timing and settings.bale_bot_token and settings.bale_chat_id
                else ConsoleNotifier()
            )
            outbox = Outbox(notifier)
            history = History(
                candle_store,
                market,
                cfg,
                spec.offset(cfg.timeframe),
                spec.raw["history_limit"],
            )
            if use_timing:
                histories = {
                    symbol: History(
                        candle_store,
                        market,
                        DailyHistory(symbol, timing_cfg.warmup),
                        spec.offset("1d"),
                        spec.raw["history_limit"] - 1,
                    )
                    for symbol in timing_symbols
                }
                engine = TimingEngine(
                    settings,
                    timing_cfg,
                    candidate,
                    timing_symbols,
                    p_limits,
                    risk,
                    app,
                    exchange,
                    histories,
                    store,
                    outbox,
                    kill,
                    logger,
                )
                for item in histories.values():
                    item.halted = engine.stopping
            elif use_portfolio:
                histories = {
                    symbol: History(
                        candle_store,
                        market,
                        DailyHistory(symbol, p_cfg.warmup),
                        spec.offset("1d"),
                        spec.raw["history_limit"] - 1,
                    )
                    for symbol in universe.symbols
                }
                engine = PortfolioEngine(
                    settings,
                    p_cfg,
                    p_limits,
                    risk,
                    app,
                    exchange,
                    histories,
                    store,
                    outbox,
                    kill,
                    logger,
                )
                for item in histories.values():
                    item.halted = engine.stopping
            else:
                engine = Engine(
                    settings, cfg, risk, app, exchange, history, store, outbox, kill, logger
                )
            exchange.halted = engine.stopping
            history.halted = engine.stopping
            restore = install_signals(engine)
            sender = asyncio.create_task(outbox.work(), name="notifications")
            tasks = []
            exit_code, cycles, deadline = 0, 0, time.monotonic() + (smoke_seconds or 10**10)
            if isinstance(notifier, BaleNotifier):
                tasks.append(
                    asyncio.create_task(
                        notifier.poll(
                            engine.enqueue,
                            engine.stop,
                            int(time.time()),
                            store.get("bale_offset", 0),
                            lambda value: store.set("bale_offset", value),
                        ),
                        name="bale-polling",
                    )
                )

            async def deadline_watch() -> None:
                await asyncio.sleep(max(0, deadline - time.monotonic()))
                engine.stop.set()

            if smoke_seconds is not None:
                tasks.append(asyncio.create_task(deadline_watch(), name="smoke-deadline"))

            async def kill_watch() -> None:
                while not engine.stop.is_set():
                    if kill.exists():
                        engine.stop.set()
                        return
                    await asyncio.sleep(0.5)

            tasks.append(asyncio.create_task(kill_watch(), name="kill-watch"))
            try:
                await engine.startup(int(time.time()))
                while not engine.stopping():
                    try:
                        await engine.tick(int(time.time()))
                        if engine.data_ready:
                            cycles += 1
                    except ReconcileError as error:
                        engine.reconciled = False
                        engine.latch(str(error))
                        exit_code = 1
                    except ExchangeError as error:
                        engine.data_ready = False
                        engine.api_errors += 1
                        if engine.api_errors in (1, app.api_error_limit):
                            engine.emit(f"API/data error ({engine.api_errors}): {error}")
                        if engine.api_errors >= app.api_error_limit:
                            engine.latch("Repeated API/data errors; restart only after diagnosis")
                    heartbeat_now = int(time.time())
                    if heartbeat_now - engine.last_heartbeat >= app.heartbeat_seconds:
                        engine.last_heartbeat = heartbeat_now
                        engine.emit(
                            f"Heartbeat: data_ready={engine.data_ready}, "
                            f"reconciled={engine.reconciled}, fault={engine.fault or 'none'}. "
                            "No new entry is permitted without fresh market data."
                        )
                    # Commands remain usable during market-data failure, without exposing a resume bypass.
                    while not engine.commands.empty() and not engine.stopping():
                        await engine.command(engine.commands.get_nowait())
                    if any(t.done() and not t.cancelled() and t.exception() for t in tasks):
                        engine.latch("A control task failed; review local log")
                        exit_code = 1
                        engine.stop.set()
                    wait = min(app.poll_seconds, max(0.1, deadline - time.monotonic()))
                    try:
                        await asyncio.wait_for(engine.stop.wait(), timeout=wait)
                    except TimeoutError:
                        pass
                if smoke_seconds is not None:
                    engine.emit(f"Smoke completed: {cycles} healthy data cycles.")
                    if cycles == 0:
                        exit_code = 1
            finally:
                for task in tasks:
                    task.cancel()
                outcomes = await asyncio.gather(*tasks, return_exceptions=True)
                if any(
                    isinstance(outcome, BaseException)
                    and not isinstance(outcome, asyncio.CancelledError)
                    for outcome in outcomes
                ):
                    exit_code = 1
                    engine.emit(
                        "WARNING: Control task failed; final reconciliation will still run."
                    )
                try:
                    clean = await asyncio.wait_for(engine.shutdown(), timeout=15)
                    if not clean:
                        exit_code = 1
                    await asyncio.wait_for(outbox.queue.join(), timeout=10)
                except TimeoutError:
                    print(
                        "Shutdown/notification grace period expired; inspect positions before restarting."
                    )
                    exit_code = 1
                finally:
                    sender.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await sender
                    restore()
            return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Safety-first Nobitex PAPER trader")
    parser.add_argument("--smoke-seconds", type=int, choices=range(10, 301), metavar="10..300")
    parser.add_argument(
        "--portfolio-paper",
        action="store_true",
        help="Explicit opt-in to NOT VALIDATED LayeredPortfolio research PAPER",
    )
    parser.add_argument(
        "--timing-paper",
        action="store_true",
        help="Explicit opt-in to isolated daily Timing V3 PAPER; never LIVE",
    )
    parser.add_argument(
        "--timing-candidate",
        choices=[candidate.value for candidate in Candidate],
        help="Select A/B/C/D for --timing-paper; defaults to configured candidate A",
    )
    args = parser.parse_args()
    try:
        with single_instance(ROOT / "data" / "bot.lock"):
            return asyncio.run(
                run(
                    args.smoke_seconds,
                    args.portfolio_paper,
                    args.timing_paper,
                    args.timing_candidate,
                )
            )
    except (ConfigError, ExchangeError, NotifyError) as error:
        print(f"Startup/operation refused: {error}", flush=True)
        return 2
    except (OSError, sqlite3.Error):
        print(
            "Local storage, lock, or filesystem unavailable. Another bot may be running; "
            "check permissions, disk health and available space.",
            flush=True,
        )
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        # Raw exception messages may contain credentials/URLs. Do not dump them automatically.
        print(
            f"Unexpected failure ({type(error).__name__}); trading halted. "
            "Preserve databases and inspect the safe local logs.",
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
