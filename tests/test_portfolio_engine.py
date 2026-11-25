import asyncio
import logging
import time
from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.portfolio_engine import PortfolioEngine, aligned_recent
from app.universe import DailyHistory
from backtest.portfolio import historical_book, simulate
from data.history import History
from data.store import Store
from exchange.base import Candle, ExchangeError, Request, Side
from exchange.paper import PaperExchange
from execution import ReconcileError
from execution.portfolio import PortfolioLedger
from notify import RESUME_CONFIRMATION, ConsoleNotifier, Outbox, authorized_command
from risk.portfolio import PortfolioLimits
from strategy.layered import DAY, Layer, LayeredConfig
from tests.test_layered import SYMBOLS, bars


def build(settings, risk, app_cfg, market, store, tmp_path, monkeypatch):
    now = 73800 + 500 * DAY + 30
    monkeypatch.setattr(time, "time", lambda: now)
    candles = Store(tmp_path / "candles.db")
    for s in SYMBOLS:
        candles.insert(s, "1d", bars(500))
    market.book = replace(market.book, ts=now)
    p = PaperExchange(market, store, D(100), risk.fee, risk.slippage, D(100), symbols=SYMBOLS)
    histories = {s: History(candles, market, DailyHistory(s, 300), 73800) for s in SYMBOLS}
    e = PortfolioEngine(
        settings,
        LayeredConfig(),
        PortfolioLimits(),
        risk,
        app_cfg,
        p,
        histories,
        store,
        Outbox(ConsoleNotifier()),
        tmp_path / "KILL",
        logging.getLogger("portfolio-test"),
    )
    p.halted = e.stopping
    return e, candles, now


def test_multisymbol_ledger_restart_closure_and_drift(market, store, risk):
    async def scenario():
        paper = PaperExchange(
            market, store, D(100), risk.fee, risk.slippage, D(100), symbols=SYMBOLS
        )
        ledger = PortfolioLedger(paper, store, SYMBOLS, 60)
        await ledger.reconcile()
        for i, s in enumerate(SYMBOLS[:2]):
            await ledger.managers[s].submit(
                Request(str(i), Side.BUY, D(".1"), D(101), D(5)),
                "entry",
                metadata=(f"lot:{s}", {"layer": str(Layer.TREND), "entry_ts": 0}),
            )
        restarted = PortfolioLedger(paper, store, SYMBOLS, 60)
        await restarted.reconcile()
        assert len(restarted.lots()) == 2
        await restarted.managers["BTC/USDT"].submit(
            Request("exit", Side.SELL, D(".1"), D(99)), "stop"
        )
        from risk.portfolio import PortfolioRisk

        state = PortfolioRisk()
        restarted.update_closures(PortfolioLimits(), state)
        assert state.streak == 1
        restarted.update_closures(PortfolioLimits(), state)
        assert state.streak == 1
        assert len(restarted.lots()) == 1
        wallet = store.get("paper_wallet")
        wallet["SOL"] = ".1"
        store.set("paper_wallet", wallet)
        with pytest.raises(ReconcileError, match="base balance"):
            await restarted.reconcile()

    asyncio.run(scenario())


def test_wrong_symbol_lookup_and_metadata_scope_rejected(market, store, risk):
    async def scenario():
        paper = PaperExchange(
            market, store, D(100), risk.fee, risk.slippage, D(100), symbols=SYMBOLS
        )
        ledger = PortfolioLedger(paper, store, SYMBOLS, 60)
        await ledger.reconcile()
        req = Request("same", Side.BUY, D(".1"), D(101), D(5))
        await ledger.managers["BTC/USDT"].submit(
            req, "entry", metadata=("lot:BTC/USDT", {"layer": str(Layer.TREND), "entry_ts": 0})
        )
        with pytest.raises(ReconcileError, match="different symbol"):
            await ledger.managers["ETH/USDT"].submit(req, "entry")
        from exchange.base import NotFound

        with pytest.raises(NotFound):
            await paper.get_order("ETH/USDT", "same")
        with pytest.raises(ExchangeError, match="Conflicting"):
            await paper.place_order("ETH/USDT", req)

    asyncio.run(scenario())


def test_stale_start_and_wake_consume_close_without_order(
    settings, risk, app_cfg, market, store, tmp_path, monkeypatch
):
    async def scenario():
        e, cache, now = build(settings, risk, app_cfg, market, store, tmp_path, monkeypatch)
        try:
            ts = 73800 + 499 * DAY
            cache.insert("BTC/USDT", "1d", [Candle(ts, 150, 161, 149, 160, 10000)])
            await e.startup(now)
            await e.tick(now)
            assert e.data_ready and e.primed
            assert store.get("processed_signal") == 73800 + 499 * DAY
            assert not e.ledger.lots()
            assert e.strategy.entries(
                e.features, {}
            )  # A genuine entry signal was suppressed, not absent.
            e.last_tick = now - 1000
            await e.tick(now)
            assert not e.ledger.lots()
            assert store.db.execute("SELECT count(*) FROM intent").fetchone()[0] == 0
        finally:
            cache.__exit__()

    asyncio.run(scenario())


def test_multisymbol_ambiguous_fill_recovers_without_resubmission(market, store, risk):
    async def scenario():
        paper = PaperExchange(
            market, store, D(100), risk.fee, risk.slippage, D(100), symbols=SYMBOLS
        )
        ledger = PortfolioLedger(paper, store, SYMBOLS, 60)
        await ledger.reconcile()
        manager = ledger.managers["ETH/USDT"]

        def lost_response(*args):
            raise ExchangeError("simulated lost fill acknowledgment")

        manager._apply = lost_response
        with pytest.raises(ExchangeError):
            await manager.submit(
                Request("ambiguous", Side.BUY, D(".1"), D(101), D(5)),
                "entry",
                metadata=("lot:ETH/USDT", {"layer": str(Layer.TREND), "entry_ts": 0}),
            )
        restored = PortfolioLedger(paper, store, SYMBOLS, 60)
        await restored.reconcile()
        assert restored.lots()["ETH/USDT"].qty == D(".1")
        await restored.reconcile()
        assert store.db.execute("SELECT count(*) FROM paper_orders").fetchone()[0] == 1
        assert restored.managers["BTC/USDT"].position().quantity == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("halt", [False, True])
def test_pause_and_halt_keep_stops_active_when_other_feed_fails(
    halt, settings, risk, app_cfg, market, store, tmp_path, monkeypatch
):
    async def scenario():
        e, cache, now = build(settings, risk, app_cfg, market, store, tmp_path, monkeypatch)
        try:
            await e.startup(now)
            await e.ledger.managers["BTC/USDT"].submit(
                Request("held", Side.BUY, D(".1"), D(101), D(5)),
                "entry",
                metadata=("lot:BTC/USDT", {"layer": str(Layer.TREND), "entry_ts": now - DAY}),
            )
            await e.enqueue("/pause")
            assert store.get("manual_pause")
            e.risk.halted = halt
            original = market.get_orderbook
            market.book = replace(market.book, bids=((D(90), D(10)),), asks=((D("90.1"), D(10)),))

            async def mixed(s):
                if s == "ETH/USDT":
                    raise ExchangeError("offline ETH")
                return await original(s)

            market.get_orderbook = mixed
            with pytest.raises(ExchangeError, match="offline ETH"):
                await e.tick(now)
            assert not e.ledger.lots() and e.manual_pause
            assert e.risk.halted == halt
            assert store.db.execute("SELECT count(*) FROM portfolio_closure").fetchone()[0] == 1
        finally:
            cache.__exit__()

    asyncio.run(scenario())


def test_kill_and_resume_cannot_clear_fault(
    settings, risk, app_cfg, market, store, tmp_path, monkeypatch
):
    async def scenario():
        e, cache, now = build(settings, risk, app_cfg, market, store, tmp_path, monkeypatch)
        try:
            await e.startup(now)
            await e.tick(now)
            await e.enqueue("/pause")
            e.latch("persistent test fault")
            e.risk.halted = True
            await e.command(RESUME_CONFIRMATION)
            assert e.risk.halted and e.manual_pause and store.get("fault")
            await e.enqueue("/stop")
            assert e.kill.exists() and e.stop.is_set()
            assert await e.shutdown()
        finally:
            cache.__exit__()

    asyncio.run(scenario())


def test_simulation_and_paper_same_features_size_fill_and_stop(
    settings, risk, app_cfg, market, store, tmp_path, monkeypatch
):
    async def scenario():
        e, cache, now = build(settings, risk, app_cfg, market, store, tmp_path, monkeypatch)
        try:
            await e.startup(now)
            await e.tick(now)  # Prime, never enter on startup.
            nxt = 73800 + 500 * DAY
            for s in SYMBOLS:
                row = (
                    Candle(nxt, 150, 160, 149, 159, 10000)
                    if s == "BTC/USDT"
                    else Candle(nxt, 100, 101, 99, 100, 10000)
                )
                cache.insert(s, "1d", [row])
            now2 = now + DAY
            monkeypatch.setattr(time, "time", lambda: now2)
            market.book = historical_book(D(160), 10000, now2, PortfolioLimits())
            # A normal daily close with no laptop outage: last poll was 15 seconds ago.
            e.last_tick = now2 - 15
            await e.tick(now2)
            lots = e.ledger.lots()
            assert "BTC/USDT" in lots
            data = aligned_recent(cache, SYMBOLS, nxt + DAY, 73800)
            features = {s: e.strategy.prepare(rows)[-1] for s, rows in data.items()}
            assert features == e.features
            model_entries = e.strategy.entries(features, {})
            assert model_entries[0].symbol == "BTC/USDT"
            qty = lots["BTC/USDT"].qty
            rules = {s: market.rules for s in SYMBOLS}
            for s in SYMBOLS:
                data[s] += [
                    Candle(nxt + DAY, 160, 161, 159, 160, 10000),
                    Candle(nxt + 2 * DAY, 160, 161, 159, 160, 10000),
                ]
            sim = simulate(data, e.cfg, e.limits, rules, risk.fee, risk.slippage, D(100), start=501)
            assert D(str(sim.trades[0].quantity)) == qty
            fill = D(160) * D("1.001") * (1 + risk.slippage)
            assert lots["BTC/USDT"].stop == fill - model_entries[0].distance
            assert lots["BTC/USDT"].cost == qty * fill * (1 + risk.fee)
            assert store.get("entry_consumed:BTC/USDT") == nxt
        finally:
            cache.__exit__()

    asyncio.run(scenario())


def test_bale_new_commands_remain_exact_whitelisted_unedited():
    now = 10000
    message = {
        "chat": {"id": 12, "type": "private"},
        "from": {"id": 12},
        "date": now,
        "text": RESUME_CONFIRMATION,
    }
    assert authorized_command({"message": message}, 12, now, now - 10) == RESUME_CONFIRMATION
    for patch in (
        {"edit_date": now},
        {"text": "/resume yes"},
        {"text": "/risk extra"},
        {"from": {"id": 13}},
        {"date": now - 121},
    ):
        assert authorized_command({"message": {**message, **patch}}, 12, now, now - 1000) is None
