import time
from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal

from data.store import Store
from exchange.base import (
    Balance,
    Book,
    Candle,
    Exchange,
    ExchangeError,
    MarketData,
    NotFound,
    Order,
    Request,
    Rules,
    Side,
    State,
)

D = Decimal


def to_dict(obj: Order | Request) -> dict:
    return {k: str(v) if isinstance(v, D) else v for k, v in asdict(obj).items()}


def order_from(obj: dict) -> Order:
    return Order(
        obj["id"],
        State(obj["state"]),
        *(D(obj[k]) for k in ("filled", "quote", "fee_base", "fee_quote")),
        obj["client_id"],
    )


def executable_quote(book, side, qty, limit, slippage, min_quote):
    """Shared all-or-cancel depth walk. No partial fill or optimistic price improvement."""
    buy = side == Side.BUY
    remaining, quote = qty, D(0)
    for price, available in book.asks if buy else book.bids:
        adjusted = price * (1 + slippage if buy else 1 - slippage)
        if (buy and adjusted > limit) or (not buy and adjusted < limit):
            break
        take = min(remaining, available)
        quote += take * adjusted
        remaining -= take
        if not remaining:
            break
    return quote if not remaining and quote >= min_quote else None


class PaperExchange(Exchange):
    """Atomic simulated IOC fills at executable depth, with a hard limit and quote fees."""

    def __init__(
        self,
        market: MarketData,
        store: Store,
        cash: D,
        fee: D,
        slippage: D,
        capital: D,
        max_age: int = 90,
        halted: Callable[[], bool] | None = None,
        symbols: tuple[str, ...] = ("BTC/USDT",),
        allow_additions: bool = False,
    ):
        self.market, self.store = market, store
        self.fee, self.slippage, self.capital, self.max_age = fee, slippage, capital, max_age
        self.halted = halted or (lambda: False)
        self.symbols = symbols
        self.allow_additions = allow_additions
        if store.get("paper_wallet") is None:
            store.set(
                "paper_wallet", {"USDT": str(cash), **{s.split("/")[0]: "0" for s in symbols}}
            )

    async def get_candles(self, symbol: str, frame: str, start: int, end: int) -> list[Candle]:
        return await self.market.get_candles(symbol, frame, start, end)

    async def get_orderbook(self, symbol: str) -> Book:
        return await self.market.get_orderbook(symbol)

    async def get_symbol_rules(self, symbol: str) -> Rules:
        return await self.market.get_symbol_rules(symbol)

    async def get_fees(self, symbol: str) -> D:
        return self.fee

    async def get_balances(self) -> dict[str, Balance]:
        return {k: Balance(D(v), D(v)) for k, v in self.store.get("paper_wallet").items()}

    async def list_open_orders(self, symbol: str) -> list[Order]:
        return []

    async def get_order(self, symbol: str, order_id: str, *, by_client: bool = False) -> Order:
        import json

        row = self.store.db.execute(
            "SELECT p.result, s.symbol FROM paper_orders p LEFT JOIN paper_order_scope s USING (cid) WHERE cid=?",
            (order_id,),
        ).fetchone()
        if not row or (row[1] or "BTC/USDT") != symbol:
            raise NotFound("Paper order not found")
        return order_from(json.loads(row[0]))

    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        return await self.get_order(symbol, order_id)

    async def place_order(self, symbol: str, request: Request) -> Order:
        import json

        if symbol not in self.symbols:
            raise ExchangeError("Symbol not in simulated wallet")
        base = symbol.split("/")[0]
        payload = json.dumps(to_dict(request), sort_keys=True)
        row = self.store.db.execute(
            "SELECT p.payload,p.result,s.symbol FROM paper_orders p LEFT JOIN paper_order_scope s USING (cid) WHERE cid=?",
            (request.client_id,),
        ).fetchone()
        if row:
            if payload != row[0] or (row[2] or "BTC/USDT") != symbol:
                raise ExchangeError("Conflicting simulated client order ID")
            return order_from(json.loads(row[1]))
        book, rules = await self.get_orderbook(symbol), await self.get_symbol_rules(symbol)
        if self.halted():
            raise ExchangeError("Kill switch or shutdown prevented paper submission")
        if not -10 <= int(time.time()) - book.ts <= self.max_age:
            raise ExchangeError("Paper execution refused stale order book")
        qty, limit = request.quantity, request.limit
        if (
            qty <= 0
            or limit <= 0
            or qty % rules.quantity_step
            or limit % rules.price_tick
            or qty < rules.min_quantity
            or qty * limit < rules.min_quote
        ):
            raise ExchangeError("Paper order violates symbol rules")
        buy = request.side == Side.BUY
        wallet = {k: D(v) for k, v in self.store.get("paper_wallet").items()}
        quote = None
        if (
            buy
            and qty * limit * (1 + self.fee) <= min(wallet["USDT"], self.capital)
            and (self.allow_additions or wallet[base] == 0)
        ) or (not buy and qty <= wallet[base]):
            quote = executable_quote(book, request.side, qty, limit, self.slippage, rules.min_quote)
        if (
            buy
            and quote is not None
            and request.stop_distance
            and request.stop_distance >= quote / qty
        ):
            quote = None
        fee = quote * self.fee if quote is not None else D(0)
        if quote is not None:
            wallet[base] += qty if buy else -qty
            wallet["USDT"] += -quote - fee if buy else quote - fee
        order = (
            Order(request.client_id, State.FILLED, qty, quote, D(0), fee, request.client_id)
            if quote is not None
            else Order(request.client_id, State.CANCELLED, client_id=request.client_id)
        )
        if self.halted():
            raise ExchangeError("Kill switch or shutdown prevented paper submission")
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO paper_orders VALUES (?,?,?)",
                (request.client_id, payload, json.dumps(to_dict(order))),
            )
            self.store.db.execute(
                "INSERT INTO paper_order_scope VALUES (?,?)", (request.client_id, symbol)
            )
            self.store.write("paper_wallet", {k: str(v) for k, v in wallet.items()})
        return order
