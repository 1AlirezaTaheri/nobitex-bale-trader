import asyncio
from decimal import Decimal

import pytest

from data.store import Store
from exchange.base import (
    Balance,
    ExchangeError,
    NotFound,
    Order,
    Request,
    Side,
    State,
    TemporaryError,
)
from exchange.paper import PaperExchange
from execution import OrderManager, Position, ReconcileError, order_key
from execution.protection import Protection

D = Decimal
SYMBOL = "BTC/USDT"


def paper(market, store, *, capital=D(100), halted=None):
    return PaperExchange(market, store, D(100), D("0.0025"), D("0.0015"), capital, halted=halted)


def buy(cid="buy1", qty=D("0.1")):
    return Request(cid, Side.BUY, qty, D(101), D(5))


def test_client_id_is_deterministic_and_distinguishes_operations():
    args = (SYMBOL, "4h", 1800, "entry")
    assert order_key(*args) == order_key(*args)
    assert order_key(*args, 1) != order_key(*args, 2)
    assert len(order_key(*args)) <= 32


def test_atomic_paper_fill_and_idempotency(store, market):
    async def scenario():
        exchange = paper(market, store)
        first = await exchange.place_order(SYMBOL, buy())
        balances = await exchange.get_balances()
        assert first.state == State.FILLED
        assert balances["BTC"].total == D("0.1")
        assert balances["USDT"].total == D(100) - first.quote - first.fee_quote
        assert await exchange.place_order(SYMBOL, buy()) == first
        assert await exchange.get_balances() == balances
        with pytest.raises(ExchangeError):
            await exchange.place_order(SYMBOL, buy(qty=D("0.2")))

    asyncio.run(scenario())


def test_timing_style_additions_are_explicit_and_keep_stop_unset(store, market):
    async def scenario():
        exchange = PaperExchange(
            market, store, D(100), D("0.0025"), D("0.0015"), D(100), allow_additions=True
        )
        manager = OrderManager(exchange, store, SYMBOL, 60, allow_additions=True)
        await manager.submit(Request("first", Side.BUY, D("0.1"), D(101)), "target")
        await manager.submit(Request("second", Side.BUY, D("0.1"), D(101)), "target increase")
        assert manager.position().quantity == D("0.2")
        assert manager.position().stop == 0
        assert (await exchange.get_balances())["BTC"].total == D("0.2")

    asyncio.run(scenario())


def test_additions_remain_rejected_without_explicit_opt_in(store, market):
    async def scenario():
        exchange = paper(market, store)
        manager = OrderManager(exchange, store, SYMBOL, 60)
        await manager.submit(buy("first"), "entry")
        with pytest.raises(ReconcileError, match="single-position"):
            await manager.submit(buy("second"), "increase")

    asyncio.run(scenario())


def test_paper_persists_across_restart(tmp_path, market):
    path = tmp_path / "durable.db"
    with Store(path) as store:
        first = asyncio.run(paper(market, store).place_order(SYMBOL, buy()))
    with Store(path) as restored:
        exchange = paper(market, restored)
        assert asyncio.run(exchange.get_order(SYMBOL, "buy1")) == first
        assert asyncio.run(exchange.get_balances())["BTC"].total == D("0.1")


def test_paper_refuses_cap_violation_even_if_wallet_large(store, market):
    exchange = paper(market, store, capital=D(1))
    order = asyncio.run(exchange.place_order(SYMBOL, buy()))
    assert order.state == State.CANCELLED
    assert asyncio.run(exchange.get_balances())["USDT"].total == 100


def test_paper_no_partial_fill_when_depth_insufficient(store, market):
    from dataclasses import replace

    market.book = replace(market.book, asks=((D("100.1"), D("0.01")),))
    exchange = paper(market, store)
    order = asyncio.run(exchange.place_order(SYMBOL, buy()))
    assert order.state == State.CANCELLED
    assert order.filled == 0


def test_paper_stale_book_and_kill_prevent_execution(store, market):
    exchange = paper(market, store, halted=lambda: True)
    with pytest.raises(ExchangeError):
        asyncio.run(exchange.place_order(SYMBOL, buy()))
    exchange.halted = lambda: False
    from dataclasses import replace

    market.book = replace(market.book, ts=0)
    with pytest.raises(ExchangeError):
        asyncio.run(exchange.place_order(SYMBOL, buy()))
    assert asyncio.run(exchange.get_balances())["BTC"].total == 0


def test_order_manager_full_round_trip_and_fees(store, market):
    async def scenario():
        exchange = paper(market, store)
        manager = OrderManager(exchange, store, SYMBOL, 60)
        await manager.reconcile()
        await manager.submit(buy(), "entry")
        position = manager.position()
        assert position.quantity == D("0.1")
        assert position.stop > 0
        await manager.submit(Request("sell1", Side.SELL, position.quantity, D(99)), "exit")
        balances, _ = await manager.reconcile()
        final = manager.position()
        assert final.quantity == 0 and final.cost == 0 and final.stop == 0
        assert final.realized == balances["USDT"].total - 100
        assert final.realized < 0 and final.closed_count == 1

    asyncio.run(scenario())


def test_position_drift_is_never_silently_adopted(store, market):
    exchange = paper(market, store)
    store.set("paper_wallet", {"BTC": "0.1", "USDT": "100"})
    with pytest.raises(ReconcileError, match="balance"):
        asyncio.run(OrderManager(exchange, store, SYMBOL, 60).reconcile())


def test_quote_cash_drift_is_detected_even_when_base_matches(store, market):
    async def scenario():
        exchange = paper(market, store)
        manager = OrderManager(exchange, store, SYMBOL, 60)
        await manager.reconcile()
        store.set("paper_wallet", {"BTC": "0", "USDT": "99"})
        with pytest.raises(ReconcileError, match="Quote balance"):
            await manager.reconcile()

    asyncio.run(scenario())


def test_crash_after_exchange_fill_recovers_without_resubmission(store, market):
    async def scenario():
        exchange = paper(market, store)
        manager = OrderManager(exchange, store, SYMBOL, 60)
        original = manager._apply
        manager._apply = lambda *_: (_ for _ in ()).throw(TemporaryError("Crash window"))
        with pytest.raises(TemporaryError):
            await manager.submit(buy(), "entry")
        assert manager.position().quantity == 0
        assert manager.active()[0]["state"] == State.UNKNOWN
        manager._apply = original
        await manager.reconcile()
        assert manager.position().quantity == D("0.1")
        assert not manager.active()
        assert store.db.execute("SELECT count(*) FROM paper_orders").fetchone()[0] == 1

    asyncio.run(scenario())


class MockExecution:
    def __init__(self):
        self.current = Order("123", State.OPEN, client_id="buy1")
        self.placed = 0
        self.cancelled = 0
        self.cancel_succeeds = True

    async def place_order(self, symbol, request):
        self.placed += 1
        return self.current

    async def get_order(self, *args, **kwargs):
        return self.current

    async def cancel_order(self, *args):
        self.cancelled += 1
        if self.cancel_succeeds:
            self.current = Order(
                "123", State.CANCELLED, self.current.filled, self.current.quote, client_id="buy1"
            )
        return self.current

    async def list_open_orders(self, symbol):
        return [] if self.current.state.terminal else [self.current]

    async def get_balances(self):
        cash = D(90) - self.current.quote
        return {
            "BTC": Balance(self.current.filled, self.current.filled),
            "USDT": Balance(cash, cash),
        }


def test_partial_fill_and_cancel_account_only_new_cumulative_quantity(store):
    async def scenario():
        exchange = MockExecution()
        manager = OrderManager(exchange, store, SYMBOL, 60)
        await manager.submit(buy(), "entry")
        exchange.current = Order("123", State.PARTIAL, D("0.04"), D(4), client_id="buy1")
        await manager.reconcile()
        assert manager.position().quantity == D("0.04")
        await manager.reconcile()
        assert manager.position().quantity == D("0.04")
        await manager.reconcile(cancel=True)
        assert exchange.cancelled == 1 and not manager.active()
        assert manager.position().quantity == D("0.04")

    asyncio.run(scenario())


def test_cancel_timeout_never_allows_unconfirmed_replacement(store):
    async def scenario():
        exchange = MockExecution()
        exchange.cancel_succeeds = False
        manager = OrderManager(exchange, store, SYMBOL, 60)
        await manager.submit(buy(), "entry")
        with pytest.raises(ReconcileError, match="Cancel not confirmed"):
            await manager.replace("buy1", buy("buy2"), "replace")
        assert exchange.placed == 1

    asyncio.run(scenario())


def test_partial_buy_is_not_automatically_topped_up(store):
    async def scenario():
        exchange = MockExecution()
        manager = OrderManager(exchange, store, SYMBOL, 60)
        await manager.submit(buy(), "entry")
        exchange.current = Order("123", State.PARTIAL, D("0.04"), D(4), client_id="buy1")
        await manager.reconcile()
        with pytest.raises(ReconcileError, match="Partial entry"):
            await manager.replace("buy1", buy("buy2", D("0.06")), "replace")
        assert exchange.placed == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "bad",
    [
        Order("123", State.PARTIAL, D("0.2"), D(20), client_id="buy1"),
        Order("123", State.OPEN, D("0.01"), D(1), client_id="buy1"),
        Order("other", State.FILLED, D("0.1"), D(10), client_id="buy1"),
    ],
)
def test_impossible_order_updates_block_trading(store, bad):
    async def scenario():
        exchange = MockExecution()
        manager = OrderManager(exchange, store, SYMBOL, 60)
        await manager.submit(buy(), "entry")
        exchange.current = bad
        with pytest.raises(ReconcileError):
            await manager.reconcile()

    asyncio.run(scenario())


def test_unknown_live_outcome_is_not_treated_as_a_rejection(store):
    async def scenario():
        exchange = MockExecution()

        async def unknown(*args, **kwargs):
            raise TemporaryError("connection lost")

        exchange.place_order = unknown
        manager = OrderManager(exchange, store, SYMBOL, 60)
        with pytest.raises(TemporaryError):
            await manager.submit(buy(), "entry")
        exchange.current = Order("unrelated", State.OPEN)

        async def missing(*args, **kwargs):
            raise NotFound("not found")

        exchange.get_order = missing
        with pytest.raises(ReconcileError, match="outcome unknown"):
            await manager.reconcile()

    asyncio.run(scenario())


def test_unowned_open_order_is_a_hard_reconciliation_fault(store):
    exchange = MockExecution()
    with pytest.raises(ReconcileError, match="External"):
        asyncio.run(OrderManager(exchange, store, SYMBOL, 60).reconcile())


def test_persistent_software_protection_only_tightens(store, market):
    manager = OrderManager(paper(market, store), store, SYMBOL, 60)
    with store.db:
        manager.save_position(Position(D(1), D(100), D(90)))
    protection = Protection(manager)
    protection.tighten(D(110), D(5))
    assert manager.position().stop == 105
    protection.tighten(D(100), D(10))
    assert manager.position().stop == 105
    assert protection.hit(D(104))
    assert not protection.hit(D(106))
    assert not protection.exchange_resident
