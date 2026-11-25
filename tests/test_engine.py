import asyncio
import logging
import time

from app.engine import Engine
from data.history import History, boundary
from data.store import Store
from exchange.base import Candle, Side
from exchange.paper import PaperExchange
from notify import ConsoleNotifier, Outbox
from tests.test_backtest import Scripted


def engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path):
    candle_store = Store(tmp_path / "candles.db")
    paper = PaperExchange(
        market, store, app_cfg.paper_cash, risk.fee, risk.slippage, settings.max_capital_quote
    )
    history = History(candle_store, market, cfg, 1800)
    box = Outbox(ConsoleNotifier())
    engine = Engine(
        settings,
        cfg,
        risk,
        app_cfg,
        paper,
        history,
        store,
        box,
        tmp_path / "KILL",
        logging.getLogger("test-engine"),
    )
    paper.halted = engine.stopping
    return engine, candle_store


def fill_history(market, cfg):
    end = boundary(int(time.time()) - 12, cfg.seconds, 1800)
    market.rows = [
        Candle(end - (cfg.warmup - i) * cfg.seconds, 100, 101, 99, 100, 10)
        for i in range(cfg.warmup)
    ]


def test_first_startup_primes_fresh_signal_without_entry_replay(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        fill_history(market, cfg)
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            engine.strategy = Scripted(cfg, [cfg.warmup - 1])
            await engine.startup(int(time.time()))
            await engine.tick(int(time.time()))
            assert engine.data_ready and engine.primed
            assert engine.manager.position().quantity == 0
            assert store.get("processed_signal") == market.rows[-1].ts
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_pause_and_resume_cannot_bypass_safety_fault(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            await engine.command("/pause")
            assert engine.manual_pause
            await engine.command("/resume")
            assert engine.manual_pause
            engine.latch("test safety fault")
            await engine.command("/resume")
            assert engine.manual_pause and store.get("fault") == "test safety fault"
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_stop_command_sets_persistent_kill_and_prevents_order(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            await engine.enqueue("/stop")
            assert engine.kill.exists() and engine.stop.is_set()
            await engine.order(Side.BUY, "test", int(time.time()))
            assert not engine.manager.active()
            assert store.db.execute("SELECT count(*) FROM paper_orders").fetchone()[0] == 0
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_pause_is_persisted_immediately_before_poll_offset_ack(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            await engine.enqueue("/pause")
            assert engine.manual_pause and store.get("manual_pause") is True
            assert engine.commands.empty()
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_position_reconciles_before_data_signal(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        from execution import ReconcileError

        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        store.set("paper_wallet", {"BTC": "0.1", "USDT": "90"})
        try:
            try:
                await engine.startup(int(time.time()))
            except ReconcileError:
                pass
            else:
                raise AssertionError("Startup should have stopped on balance drift")
            assert not engine.reconciled and not market.requests
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_runtime_downtime_re_primes_without_old_signal(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        fill_history(market, cfg)
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            now = int(time.time())
            await engine.startup(now)
            engine.primed = True
            engine.last_tick = now - 1000
            engine.strategy = Scripted(cfg, [cfg.warmup - 1])
            await engine.tick(now)
            assert engine.manager.position().quantity == 0
            assert engine.primed
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_wide_spread_blocks_entry_but_not_software_stop_exit(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    from dataclasses import replace
    from decimal import Decimal as D

    from exchange.base import Request

    async def scenario():
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            await engine.startup(int(time.time()))
            engine.data_ready = True
            market.book = replace(market.book, asks=((D(110), D(10)),))
            engine.book = market.book
            await engine.order(Side.BUY, "wide entry", 1800, D(5))
            assert store.db.execute("SELECT count(*) FROM intent").fetchone()[0] == 0
            market.book = replace(market.book, asks=((D("100.1"), D(10)),))
            await engine.manager.submit(Request("entry", Side.BUY, D("0.1"), D(101), D(5)), "entry")
            market.book = replace(market.book, asks=((D(110), D(10)),))
            engine.book = market.book
            await engine.order(Side.SELL, "software stop", 1800)
            assert engine.manager.position().quantity == 0
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_stale_data_recovery_retries_sync_in_same_frame(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        fill_history(market, cfg)
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            now = int(time.time())
            await engine.startup(now)
            await engine.tick(now)
            assert engine.data_ready
            engine.data_ready = False
            calls = []
            original = engine.history.sync

            async def counted(*args):
                calls.append(1)
                return await original(*args)

            engine.history.sync = counted
            await engine.tick(now + 1)
            assert calls == [1] and engine.data_ready
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_manual_pause_keeps_existing_software_stop_active(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    from dataclasses import replace
    from decimal import Decimal as D

    from exchange.base import Request

    async def scenario():
        fill_history(market, cfg)
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            await engine.startup(int(time.time()))
            await engine.manager.submit(
                Request("held-entry", Side.BUY, D("0.1"), D(101), D(5)), "entry"
            )
            await engine.enqueue("/pause")
            market.book = replace(market.book, bids=((D(90), D(10)),), asks=((D("90.1"), D(10)),))
            await engine.tick(int(time.time()))
            assert engine.manual_pause
            assert engine.manager.position().quantity == 0
            assert engine.manager.position().closed_count == 1
        finally:
            candles.__exit__()

    asyncio.run(scenario())


def test_failed_shutdown_reconciliation_is_not_reported_clean(
    settings, cfg, risk, app_cfg, market, store, tmp_path
):
    async def scenario():
        engine, candles = engine_for(settings, cfg, risk, app_cfg, market, store, tmp_path)
        try:
            await engine.startup(int(time.time()))
            store.set("paper_wallet", {"BTC": "0", "USDT": "99"})
            assert not await engine.shutdown()
            assert store.get("clean_stop") is False
        finally:
            candles.__exit__()

    asyncio.run(scenario())
