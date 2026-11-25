"""Portfolio coordination over the existing symbol-scoped order state machine."""

from decimal import Decimal as D

from execution import OrderManager, ReconcileError
from risk import down, up
from risk.portfolio import PortfolioRisk
from strategy.layered import Layer, Lot


def limit_price(book, side, rules, slippage):
    if side == "buy":
        return up(book.ask * (1 + 2 * slippage), rules.price_tick)
    return down(book.bid * (1 - 2 * slippage), rules.price_tick)


class PortfolioLedger:
    def __init__(self, exchange, store, symbols, timeout, *, allow_additions=False):
        self.exchange, self.store = exchange, store
        self.managers = {
            s: OrderManager(
                exchange,
                store,
                s,
                timeout,
                shared_check=self.check,
                allow_additions=allow_additions,
            )
            for s in symbols
        }

    def check(self, balances):
        positions = {s.split("/")[0]: m.position() for s, m in self.managers.items()}
        if set(balances) != set(positions) | {"USDT"} or any(
            balances[base].total != p.quantity for base, p in positions.items()
        ):
            raise ReconcileError("Portfolio base balance does not match independent ledgers")
        baseline = self.store.get("initial_quote")
        if baseline is None:
            if self.store.db.execute("SELECT count(*) FROM intent").fetchone()[0] or any(
                p.quantity for p in positions.values()
            ):
                raise ReconcileError("Missing portfolio starting cash")
            baseline = str(balances["USDT"].total)
            self.store.set("initial_quote", baseline)
        expected = D(baseline) + sum((p.realized - p.cost for p in positions.values()), D(0))
        if abs(balances["USDT"].total - expected) > D("0.000000000000000001"):
            raise ReconcileError("Portfolio quote balance does not match independent ledgers")

    def lots(self):
        result = {}
        for symbol, manager in self.managers.items():
            p = manager.position()
            if not p.quantity:
                continue
            metadata = self.store.get(f"lot:{symbol}")
            if not metadata or p.stop <= 0:
                raise ReconcileError("Held position missing valid sleeve/protection metadata")
            try:
                result[symbol] = Lot(
                    symbol,
                    Layer(metadata["layer"]),
                    p.quantity,
                    p.cost,
                    p.stop,
                    int(metadata["entry_ts"]),
                )
            except (KeyError, TypeError, ValueError):
                raise ReconcileError("Invalid held sleeve metadata") from None
        return result

    async def reconcile(self, cancel=False):
        if any(
            row[0] not in self.managers
            for row in self.store.db.execute(
                "SELECT DISTINCT coalesce(s.symbol,'') FROM intent i LEFT JOIN intent_scope s USING (cid)"
            )
        ):
            raise ReconcileError("Unscoped or unexpected symbol intent")
        for manager in self.managers.values():
            await manager.reconcile_orders(cancel=cancel)
        balances = await self.exchange.get_balances()
        self.check(balances)
        self.lots()
        return balances

    def update_closures(self, limits, state: PortfolioRisk):
        cursor = self.store.get("portfolio_closure_cursor", 0)
        rows = list(
            self.store.db.execute(
                "SELECT seq,pnl,ts FROM portfolio_closure WHERE seq>? ORDER BY seq", (cursor,)
            )
        )
        if rows:
            for _, pnl, ts in rows:
                state.closed(limits, D(pnl), ts)
            with self.store.db:
                self.store.write("portfolio_risk", state.dump())
                self.store.write("portfolio_closure_cursor", rows[-1][0])
