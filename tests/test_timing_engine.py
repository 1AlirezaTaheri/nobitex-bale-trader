import asyncio
import logging
import time
from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.config import ConfigError
from app.timing_config import TimingConfig
from app.timing_engine import TimingEngine, TimingLedger, risk_overlay_targets
from app.universe import DailyHistory
from data.history import History
from data.store import Store
from exchange.base import Book, Side
from exchange.paper import PaperExchange
from execution import ReconcileError
from risk.portfolio import PortfolioLimits
from strategy.timing import Candidate

BTC = "BTC/USDT"
DAY = 86400


@pytest.fixture
def timing_engine(settings, risk, app_cfg, market, store, tmp_path, monkeypatch):
    now = 73800 + 500 * DAY + 30
    monkeypatch.setattr(time, "time", lambda: now)
    market.book = replace(market.book, ts=now)
    with Store(tmp_path / "timing-candles.db") as candles:
        exchange = PaperExchange(
            market,
            store,
            D(100),
            risk.fee,
            risk.slippage,
            settings.max_capital_quote,
            symbols=(BTC,),
            allow_additions=True,
        )
        engine = TimingEngine(
            settings,
            TimingConfig(),
            Candidate.A,
            (BTC,),
            PortfolioLimits(),
            risk,
            app_cfg,
            exchange,
            {BTC: History(candles, market, DailyHistory(BTC, 300), 73800)},
            store,
            None,
            tmp_path / "KILL",
            logging.getLogger("timing-test"),
        )
        monkeypatch.setattr(engine, "emit", lambda message: None)
        exchange.halted = engine.stopping
        engine.books = {BTC: market.book}
        engine.reconciled = engine.data_ready = True
        asyncio.run(engine.reconcile(now))
        yield engine, now


def test_timing_addition_reduction_and_restart_reconciliation(timing_engine):
    engine, now = timing_engine

    async def scenario():
        for weight, side in (
            (D("0.25"), Side.BUY),
            (D("0.5"), Side.BUY),
            (D("0.25"), Side.SELL),
            (D(0), Side.SELL),
        ):
            await engine._place_delta(
                BTC,
                weight,
                D(100),
                now - 30 - DAY,
                "test target",
                side_only=side,
            )
            await engine.reconcile(now)
        restored = TimingLedger(engine.exchange, engine.store, (BTC,), 60)
        await restored.reconcile()
        assert restored.managers[BTC].position().quantity == 0
        assert restored.managers[BTC].position().stop == 0
        assert engine.store.db.execute("SELECT count(*) FROM intent").fetchone()[0] == 4
        assert engine.store.get("portfolio_closure_cursor") == 1

    asyncio.run(scenario())


def test_rejected_timing_order_is_consumed_without_replay(timing_engine, market, monkeypatch):
    engine, now = timing_engine
    market.book = Book(now, ((D(100), D(10)),), ((D("100.1"), D("0.001")),))
    engine.books = {BTC: market.book}
    monkeypatch.setattr(engine, "_targets", lambda expected: ({BTC: D(1)}, {BTC: []}))

    async def scenario():
        await engine._process_close(now - 30, now)
        await engine._process_close(now - 30, now)
        await engine.reconcile(now)
        assert engine.ledger.managers[BTC].position().quantity == 0
        assert engine.store.db.execute("SELECT state FROM intent").fetchone()[0] == "cancelled"
        assert engine.store.db.execute("SELECT count(*) FROM intent").fetchone()[0] == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("command", ["/pause", "/stop"])
def test_pause_and_stop_apply_even_when_command_queue_is_full(timing_engine, command):
    engine, now = timing_engine

    async def scenario():
        for _ in range(engine.commands.maxsize):
            engine.commands.put_nowait("/status")
        await engine.enqueue(command)
        await engine._place_delta(BTC, D(1), D(100), now - 30 - DAY, "blocked", side_only=Side.BUY)
        assert engine.store.db.execute("SELECT count(*) FROM intent").fetchone()[0] == 0
        if command == "/stop":
            assert engine.kill.exists() and engine.stop.is_set()
        else:
            assert engine.manual_pause and engine.store.get("manual_pause")

    asyncio.run(scenario())


def test_expired_execution_window_is_rechecked_after_public_reads(
    timing_engine, market, monkeypatch
):
    engine, now = timing_engine

    async def delayed_rules(symbol):
        future = now + engine.app.entry_delay_seconds + 1
        monkeypatch.setattr(time, "time", lambda: future)
        market.book = replace(market.book, ts=future)
        return market.rules

    monkeypatch.setattr(market, "get_symbol_rules", delayed_rules)
    asyncio.run(
        engine._place_delta(BTC, D(1), D(100), now - 30 - DAY, "expired", side_only=Side.BUY)
    )
    assert engine.store.db.execute("SELECT count(*) FROM intent").fetchone()[0] == 0


def test_timing_constructor_refuses_non_paper_transport(timing_engine):
    engine, _ = timing_engine
    with pytest.raises(ConfigError, match="simulated PAPER"):
        TimingEngine(
            engine.settings,
            engine.cfg,
            engine.candidate,
            engine.symbols,
            engine.limits,
            engine.risk_config,
            engine.app,
            object(),
            engine.histories,
            engine.store,
            engine.outbox,
            engine.kill,
            engine.logger,
        )


def test_risk_overlay_scales_only_increases_and_never_blocks_reductions():
    assert risk_overlay_targets(
        {"BTC": D("1"), "ETH": D("0.25")},
        {"BTC": D("0.2"), "ETH": D("0.8")},
        D("0.5"),
    ) == {"BTC": D("0.5"), "ETH": D("0.25")}
    assert risk_overlay_targets({"BTC": D("0.4")}, {"BTC": D("0.8")}, D("0.5")) == {"BTC": D("0.4")}


def test_timing_ledger_refuses_unscoped_intents_before_exchange_access(store, market):
    exchange = PaperExchange(
        market, store, D(100), D("0.0025"), D("0.0015"), D(100), symbols=(BTC,)
    )
    ledger = TimingLedger(exchange, store, (BTC,), 60)
    with store.db:
        store.db.execute(
            "INSERT INTO intent VALUES (?,?,?,?,?,?)",
            ("unscoped", "{}", 0, "unknown", None, "test"),
        )
    with pytest.raises(ReconcileError, match="Unscoped or unexpected"):
        asyncio.run(ledger.reconcile())


def test_stale_daily_signal_is_consumed_without_order_or_replay(
    settings, risk, app_cfg, market, store, tmp_path, monkeypatch
):
    async def scenario():
        expected = 73800 + 500 * DAY
        exchange = PaperExchange(
            market,
            store,
            D(100),
            risk.fee,
            risk.slippage,
            settings.max_capital_quote,
            symbols=(BTC,),
            allow_additions=True,
        )
        candle_store = Store(tmp_path / "timing-candles.db")
        history = History(candle_store, market, DailyHistory(BTC, 300), 73800)
        engine = TimingEngine(
            settings,
            TimingConfig(),
            Candidate.A,
            (BTC,),
            PortfolioLimits(),
            risk,
            app_cfg,
            exchange,
            {BTC: history},
            store,
            None,
            tmp_path / "KILL",
            logging.getLogger("timing-test"),
        )
        engine.data_ready = engine.reconciled = True
        engine.stale_signal_to_skip = expected - DAY
        monkeypatch.setattr(engine, "emit", lambda message: None)
        calls = []

        def targets(value):
            calls.append(value)
            return {BTC: D(1)}, {BTC: []}

        monkeypatch.setattr(engine, "_targets", targets)
        try:
            await engine._process_close(expected, expected + 5)
            await engine._process_close(expected, expected + 5)
            assert store.get("processed_signal") == expected - DAY
            assert store.get("accepted_target")[BTC] == "1"
            assert store.db.execute("SELECT count(*) FROM intent").fetchone()[0] == 0
            assert (await exchange.get_balances())["BTC"].total == 0
            assert calls == [expected]
        finally:
            candle_store.__exit__()

    asyncio.run(scenario())
