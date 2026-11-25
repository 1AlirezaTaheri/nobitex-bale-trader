import json
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256

from data.store import Store
from exchange.base import Balance, Exchange, ExchangeError, NotFound, Order, Request, Side, State
from exchange.paper import order_from, to_dict

D = Decimal


class ReconcileError(ExchangeError):
    pass


@dataclass(frozen=True)
class Position:
    quantity: D = D(0)
    cost: D = D(0)
    stop: D = D(0)
    realized: D = D(0)
    trade_pnl: D = D(0)
    closed_count: int = 0
    last_closed: D = D(0)


def order_key(symbol: str, frame: str, ts: int, reason: str, attempt: int = 0) -> str:
    return "nb" + sha256(f"{symbol}:{frame}:{ts}:{reason}:{attempt}".encode()).hexdigest()[:22]


class OrderManager:
    def __init__(
        self,
        exchange: Exchange,
        store: Store,
        symbol: str,
        timeout: int,
        *,
        shared_check=None,
        allow_additions: bool = False,
    ):
        self.exchange, self.store, self.symbol, self.timeout = exchange, store, symbol, timeout
        self.shared_check = shared_check
        self.allow_additions = allow_additions
        self.position_key = f"position:{symbol}" if shared_check else "position"

    def position(self) -> Position:
        return Position(
            **{
                k: int(v) if k == "closed_count" else D(v)
                for k, v in self.store.get(self.position_key, {}).items()
            }
        )

    def save_position(self, position: Position) -> None:
        self.store.write(self.position_key, {k: str(v) for k, v in asdict(position).items()})

    def active(self) -> list:
        scope = (
            " AND cid IN (SELECT cid FROM intent_scope WHERE symbol=?)" if self.shared_check else ""
        )
        return list(
            self.store.db.execute(
                "SELECT * FROM intent WHERE state IN (?,?,?,?)" + scope + " ORDER BY created,cid",
                (State.SUBMITTING, State.UNKNOWN, State.OPEN, State.PARTIAL)
                + ((self.symbol,) if self.shared_check else ()),
            )
        )

    def check_balances(self, balances: dict[str, Balance]) -> None:
        if self.shared_check:
            self.shared_check(balances)
            return
        p = self.position()
        if "BTC" not in balances or "USDT" not in balances or balances["BTC"].total != p.quantity:
            raise ReconcileError("Position does not match exchange balance")
        baseline = self.store.get("initial_quote")
        if baseline is None:
            if self.store.db.execute("SELECT count(*) FROM intent").fetchone()[0] or p.quantity:
                raise ReconcileError("Missing initial cash baseline; preserve state for review")
            self.store.set("initial_quote", str(balances["USDT"].total))
            baseline = self.store.get("initial_quote")
        expected = D(baseline) + p.realized - p.cost
        if abs(balances["USDT"].total - expected) > D("0.000000000000000001"):
            raise ReconcileError("Quote balance does not match independent position/cash ledger")

    def _apply(self, row, current: Order) -> None:
        previous = (
            order_from(json.loads(row["result"])) if row["result"] else Order("", State.SUBMITTING)
        )
        data = json.loads(row["request"])
        quantity, limit, side = D(data["quantity"]), D(data["limit"]), Side(data["side"])
        dq, dv = current.filled - previous.filled, current.quote - previous.quote
        db, df = current.fee_base - previous.fee_base, current.fee_quote - previous.fee_quote
        if (
            previous.state.terminal
            or (previous.id and previous.id != current.id)
            or current.state in {State.UNKNOWN, State.SUBMITTING}
            or (current.state == State.OPEN and current.filled)
            or (current.state == State.PARTIAL and not 0 < current.filled < quantity)
            or (current.client_id is not None and current.client_id != row["cid"])
            or min(dq, dv, db, df) < 0
            or current.filled > quantity
            or (current.state == State.FILLED and current.filled != quantity)
            or (current.state == State.REJECTED and current.filled)
            or (dq == 0 and (dv or db or df))
            or (dq and (dv <= 0 or (dv > dq * limit if side == Side.BUY else dv < dq * limit)))
        ):
            raise ReconcileError("Inconsistent cumulative order update; trading blocked")
        p = self.position()
        closed_before = p.closed_count
        if dq:
            if side == Side.BUY:
                if dq <= db:
                    raise ReconcileError("Invalid base fee")
                p = Position(
                    p.quantity + dq - db,
                    p.cost + dv + df,
                    p.stop
                    if self.allow_additions and D(data["stop_distance"]) == 0
                    else max(p.stop, dv / dq - D(data["stop_distance"])),
                    p.realized,
                    p.trade_pnl,
                    p.closed_count,
                    p.last_closed,
                )
            else:
                sold = dq + db
                if sold > p.quantity or df > dv:
                    raise ReconcileError("Sell fill exceeds tracked position or proceeds")
                allocation = p.cost * sold / p.quantity
                net = dv - df - allocation
                remaining = p.quantity - sold
                trade_pnl = p.trade_pnl + net
                p = Position(
                    remaining,
                    p.cost - allocation if remaining else D(0),
                    p.stop if remaining else D(0),
                    p.realized + net,
                    trade_pnl if remaining else D(0),
                    p.closed_count + int(not remaining),
                    p.last_closed if remaining else trade_pnl,
                )
        with self.store.db:
            self.save_position(p)
            if self.shared_check and p.closed_count > closed_before:
                self.store.db.execute(
                    "INSERT INTO portfolio_closure(symbol,pnl,ts) VALUES (?,?,?)",
                    (self.symbol, str(p.last_closed), int(time.time())),
                )
            self.store.db.execute(
                "UPDATE intent SET state=?,result=? WHERE cid=?",
                (current.state, json.dumps(to_dict(current)), row["cid"]),
            )

    def assert_owned(self, cid: str) -> None:
        if self.shared_check:
            owner = self.store.db.execute(
                "SELECT symbol FROM intent_scope WHERE cid=?", (cid,)
            ).fetchone()
            if owner is None or owner[0] != self.symbol:
                raise ReconcileError("Portfolio client ID belongs to a different symbol")

    async def submit(
        self, req: Request, reason: str, *, metadata: tuple[str, dict] | None = None
    ) -> Order | None:
        existing = self.store.db.execute(
            "SELECT * FROM intent WHERE cid=?", (req.client_id,)
        ).fetchone()
        if existing:
            self.assert_owned(req.client_id)
            if json.loads(existing["request"]) != to_dict(req):
                raise ReconcileError("Conflicting client order ID")
            return order_from(json.loads(existing["result"])) if existing["result"] else None
        p = self.position()
        self.check_balances(await self.exchange.get_balances())
        if (
            self.active()
            or req.quantity <= 0
            or req.limit <= 0
            or (
                req.side == Side.BUY
                and (
                    (p.quantity and not self.allow_additions)
                    or not (
                        0 < req.stop_distance < req.limit
                        or (self.allow_additions and req.stop_distance == 0)
                    )
                )
            )
            or (req.side == Side.SELL and req.quantity > p.quantity)
        ):
            raise ReconcileError(
                "Trade violates single-position, long-only, or active-intent invariant"
            )
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO intent VALUES (?,?,?,?,?,?)",
                (
                    req.client_id,
                    json.dumps(to_dict(req)),
                    int(time.time()),
                    State.SUBMITTING,
                    None,
                    reason,
                ),
            )
            if self.shared_check:
                self.store.db.execute(
                    "INSERT INTO intent_scope VALUES (?,?)", (req.client_id, self.symbol)
                )
            if metadata:
                self.store.write(*metadata)
        row = self.active()[0]
        try:
            order = await self.exchange.place_order(self.symbol, req)
            self._apply(row, order)
        except ExchangeError:
            with self.store.db:
                self.store.db.execute(
                    "UPDATE intent SET state=? WHERE cid=?", (State.UNKNOWN, req.client_id)
                )
            raise
        return order

    async def replace(self, original_id: str, req: Request, reason: str) -> Order | None:
        """Cancel, confirm terminal state, account for partial fills; never reuse a client ID."""
        row = self.store.db.execute("SELECT * FROM intent WHERE cid=?", (original_id,)).fetchone()
        if row is None or not row["result"]:
            raise ReconcileError("Cannot replace an unresolved submission")
        self.assert_owned(original_id)
        old_request = json.loads(row["request"])
        old = order_from(json.loads(row["result"]))
        if old.id == req.client_id or original_id == req.client_id:
            raise ReconcileError("Replacement requires a new ID")
        if not old.state.terminal:
            await self.exchange.cancel_order(self.symbol, old.id)
            final = await self.exchange.get_order(self.symbol, old.id)
            self._apply(row, final)
            if not final.state.terminal:
                raise ReconcileError("Cancel not confirmed; replacement forbidden")
            old = final
        remaining = D(old_request["quantity"]) - old.filled
        if req.side != Side(old_request["side"]) or req.quantity > remaining or remaining <= 0:
            raise ReconcileError("Replacement exceeds unfilled quantity or changes side")
        if req.side == Side.BUY and self.position().quantity:
            raise ReconcileError("Partial entry is protected, not automatically topped up")
        return await self.submit(req, reason)

    async def reconcile(self, *, cancel: bool = False) -> tuple[dict[str, Balance], list[Order]]:
        events = await self.reconcile_orders(cancel=cancel)
        balances = await self.exchange.get_balances()
        self.check_balances(balances)
        return balances, events

    async def reconcile_orders(self, *, cancel: bool = False) -> list[Order]:
        events = []
        initial_open = await self.exchange.list_open_orders(self.symbol)
        matches = {o.client_id: o for o in initial_open if o.client_id is not None}
        for row in self.active():
            previous = order_from(json.loads(row["result"])) if row["result"] else None
            try:
                if previous:
                    current = await self.exchange.get_order(self.symbol, previous.id)
                elif row["cid"] in matches:
                    current = matches[row["cid"]]
                else:
                    current = await self.exchange.get_order(self.symbol, row["cid"], by_client=True)
            except NotFound:
                # Paper IDs are durable and lookup includes terminal results. No such claim for live.
                from exchange.paper import PaperExchange

                if isinstance(self.exchange, PaperExchange) and not previous:
                    current = Order(row["cid"], State.CANCELLED, client_id=row["cid"])
                else:
                    raise ReconcileError("Order outcome unknown; do not resubmit") from None
            self._apply(row, current)
            if current != previous:
                events.append(current)
            if not current.state.terminal and (
                cancel or time.time() - row["created"] >= self.timeout
            ):
                await self.exchange.cancel_order(self.symbol, current.id)
                final = await self.exchange.get_order(self.symbol, current.id)
                updated = self.store.db.execute(
                    "SELECT * FROM intent WHERE cid=?", (row["cid"],)
                ).fetchone()
                self._apply(updated, final)
                if final != current:
                    events.append(final)
                if not final.state.terminal:
                    raise ReconcileError("Cancellation not confirmed; no replacement allowed")
        open_orders = await self.exchange.list_open_orders(self.symbol)
        owned = {order_from(json.loads(r["result"])).id for r in self.active() if r["result"]}
        if any(o.id not in owned for o in open_orders):
            raise ReconcileError("External or untracked open orders; manual review required")
        if {o.id for o in open_orders} != owned:
            raise ReconcileError("Order list and tracked status disagree; retry reconciliation")
        return events
