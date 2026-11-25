import asyncio
import json
import logging
import time
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from app.config import AppConfig, ConfigError, RiskConfig, Settings, StrategyConfig
from data.history import History, boundary, fresh
from data.store import Store
from exchange.base import Book, ExchangeError, Request, Side
from exchange.paper import PaperExchange
from execution import OrderManager, ReconcileError, order_key
from execution.protection import Protection
from notify import COMMANDS, Outbox
from risk import RiskState, down, size, up
from strategy import Action, build

D = Decimal


class Engine:
    def __init__(
        self,
        settings: Settings,
        cfg: StrategyConfig,
        risk: RiskConfig,
        app: AppConfig,
        exchange: PaperExchange,
        history: History,
        store: Store,
        outbox: Outbox,
        kill: Path,
        logger: logging.Logger,
    ):
        self.settings, self.cfg, self.risk_config, self.app = settings, cfg, risk, app
        self.exchange, self.history, self.store, self.outbox = exchange, history, store, outbox
        self.kill, self.logger = kill, logger
        self.stop = asyncio.Event()
        self.commands: asyncio.Queue[str] = asyncio.Queue(maxsize=16)
        self.manager = OrderManager(exchange, store, cfg.symbol, app.order_timeout_seconds)
        self.protection = Protection(self.manager)
        self.strategy = build(cfg)
        self.risk = RiskState.restore(store.get("risk", {}))
        self.manual_pause = bool(store.get("manual_pause", False))
        self.fault = store.get("fault", "")
        self.api_errors = 0
        self.data_ready = False
        self.primed = False
        self.book: Book | None = None
        self.latest_signal = "not evaluated"
        self.last_tick = 0
        self.last_reconcile = 0
        self.last_sync = 0
        self.last_heartbeat = 0
        self.last_day = store.get("summary_day", -1)
        self.reconciled = False

    def emit(self, message: str) -> None:
        self.logger.info(message)
        self.outbox.emit(f"[PAPER] {message}")

    def bind_configuration(self) -> None:
        content = [
            self.cfg.model_dump(mode="json"),
            self.risk_config.model_dump(mode="json"),
            self.app.model_dump(mode="json"),
        ]
        fingerprint = sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        previous = self.store.get("configuration_fingerprint")
        if previous and previous != fingerprint:
            raise ConfigError(
                "Strategy/risk/app configuration changed: archive the paper database and "
                "start a new experiment; never delete live state"
            )
        self.store.set("configuration_fingerprint", fingerprint)

    async def enqueue(self, command: str) -> None:
        if command == "/stop":
            self.kill.parent.mkdir(parents=True, exist_ok=True)
            self.kill.touch(exist_ok=True)
            self.stop.set()
        elif command == "/pause":
            # Persist the safe direction before acknowledging the Bale update offset.
            self.manual_pause = True
            self.store.set("manual_pause", True)
            self.emit("Manual pause enabled; software stop monitoring continues.")
        elif command in COMMANDS and not self.commands.full():
            self.commands.put_nowait(command)

    async def startup(self, now: int) -> None:
        self.bind_configuration()
        last = self.store.get("last_tick")
        if last is not None:
            gap = now - last
            if gap < -10:
                raise ConfigError("System clock moved backwards; synchronize Windows time")
            self.emit(
                f"Downtime gap: {gap} seconds; prior clean stop={self.store.get('clean_stop', False)}. "
                "Old signals will not be replayed."
            )
        self.store.set("clean_stop", False)
        await self.reconcile(now)
        self.emit("Bot started; public data only. No real orders can be placed in PAPER mode.")
        if self.manager.position().quantity:
            self.emit(
                "WARNING: Restored position has SOFTWARE-ONLY protection. Offline prices were not "
                "executed retroactively; current executable prices will be used."
            )

    def latch(self, reason: str) -> None:
        if self.fault != reason:
            self.fault = reason
            self.store.set("fault", reason)
            self.emit("Trading paused: " + reason)

    async def reconcile(self, now: int) -> None:
        self.reconciled = False
        _, events = await self.manager.reconcile()
        self.reconciled = True
        self.last_reconcile = now
        for order in events:
            self.emit(f"Order reconciled: {order.state}; filled={order.filled}.")
        self.account_for_closures(now)

    def account_for_closures(self, now: int) -> None:
        position = self.manager.position()
        accounted = self.store.get("accounted_closures", 0)
        if position.closed_count > accounted:
            self.risk.closed(self.risk_config, position.last_closed, now, self.cfg.seconds)
            with self.store.db:
                self.store.write("accounted_closures", position.closed_count)
                self.store.write("risk", self.risk.serialize())

    def stopping(self) -> bool:
        return self.stop.is_set() or self.kill.exists()

    def fresh_book(self, now: int) -> bool:
        return self.book is not None and -10 <= now - self.book.ts <= self.app.book_max_age_seconds

    async def order(self, side: Side, reason: str, ts: int, distance: D = D(0)) -> None:
        if self.stopping() or not self.fresh_book(int(time.time())) or not self.reconciled:
            return
        assert self.book is not None
        if (self.book.ask - self.book.bid) / self.book.bid > self.risk_config.max_spread:
            if side == Side.BUY:
                self.emit("Entry skipped: public spread exceeds configured maximum.")
                return
            self.emit("WARNING: Protective exit sees a wide spread; exit is not suppressed.")
        rules = await self.exchange.get_symbol_rules(self.cfg.symbol)
        balances = await self.exchange.get_balances()
        if self.stopping() or not self.fresh_book(int(time.time())):
            return
        position = self.manager.position()
        if balances["BTC"].total != position.quantity:
            raise ReconcileError("Balance changed immediately before order")
        if side == Side.BUY:
            if self.manual_pause or self.fault or not self.data_ready or position.quantity:
                return
            price = up(self.book.ask * (1 + 2 * self.risk_config.slippage), rules.price_tick)
            equity = balances["USDT"].total + position.quantity * self.book.bid
            if self.risk.observe(self.risk_config, equity, int(time.time())):
                return
            quantity = size(
                self.risk_config,
                rules,
                equity,
                balances["USDT"].free,
                self.settings.max_capital_quote,
                price,
                distance,
                self.exchange.fee,
            )
        else:
            price = down(self.book.bid * (1 - 2 * self.risk_config.slippage), rules.price_tick)
            quantity = down(min(position.quantity, balances["BTC"].free), rules.quantity_step)
        if quantity <= 0 or quantity * price < rules.min_quote or quantity < rules.min_quantity:
            if side == Side.SELL and position.quantity:
                self.latch(
                    "Position cannot be sold under current minimum-size rules; manual review required"
                )
            return
        count = self.store.db.execute("SELECT count(*) FROM intent").fetchone()[0]
        cid = order_key(self.cfg.symbol, self.cfg.timeframe, ts, reason, count)
        if side == Side.BUY:
            # Durable consumption precedes submission, preventing re-entry after crash or stop on same bar.
            if self.store.get("entry_consumed") == ts:
                return
            self.store.set("entry_consumed", ts)
        if self.stopping():
            return
        self.emit(f"Order placed (simulated intent): {side}, quantity={quantity}, reason={reason}.")
        order = await self.manager.submit(Request(cid, side, quantity, price, distance), reason)
        if order:
            self.emit(f"Order {order.state}: quantity={order.filled}, quote={order.quote}.")
        self.account_for_closures(int(time.time()))
        if side == Side.BUY and self.manager.position().quantity:
            self.emit(
                "WARNING: Position is unprotected while bot/laptop is offline; SOFTWARE ATR stop only."
            )

    async def command(self, command: str) -> None:
        p = self.manager.position()
        if command == "/help":
            self.emit(
                "Commands: "
                + " ".join(sorted(COMMANDS))
                + ". /pause blocks entries, not stops; /stop cancels tracked orders and halts, not liquidation."
            )
        elif command == "/mode":
            self.emit("Mode PAPER; switching mode remotely is forbidden.")
        elif command == "/status":
            self.emit(
                f"Status: paused={self.manual_pause}, fault={self.fault or 'none'}, "
                f"data_ready={self.data_ready}, reconciled={self.reconciled}, "
                f"book_fresh={self.fresh_book(int(time.time()))}, signal={self.latest_signal}."
            )
        elif command == "/balance":
            balances = await self.exchange.get_balances()
            self.emit(
                "Simulated balances: "
                + "; ".join(f"{k} free={v.free} total={v.total}" for k, v in balances.items())
            )
        elif command == "/positions":
            self.emit(
                f"BTC={p.quantity}, entry cost={p.cost}, software stop={p.stop}. "
                "Exchange-resident protection: NONE."
            )
        elif command == "/pnl":
            unrealized = p.quantity * self.book.bid - p.cost if self.book else D(0)
            self.emit(
                f"Realized PnL={p.realized}, mark-to-bid unrealized={unrealized}; "
                "unrealized excludes future exit fees, and is unavailable without a fresh book."
            )
        elif command == "/pause":
            self.manual_pause = True
            self.store.set("manual_pause", True)
            self.emit("Manual pause enabled; software stop monitoring continues.")
        elif command == "/resume":
            if (
                self.fault
                or not self.data_ready
                or not self.reconciled
                or not self.fresh_book(int(time.time()))
                or self.risk.drawdown_latched
                or self.risk.daily_latched
            ):
                self.emit(
                    "Resume refused: resolve safety fault/stale data/risk latch first. "
                    "No remote bypass of circuit breakers."
                )
            else:
                self.manual_pause = False
                self.store.set("manual_pause", False)
                self.emit("Manual pause disabled. Stale signals remain ignored.")

    async def tick(self, now: int) -> None:
        if self.last_tick and now < self.last_tick - 5:
            self.latch("Clock moved backwards; synchronize time and restart")
        if self.last_tick and now - self.last_tick > 2 * self.app.poll_seconds:
            self.primed = False
            self.last_sync = 0
            self.emit(f"Runtime gap: {now - self.last_tick} seconds; re-priming without replay.")
        self.last_tick = now
        self.store.set("last_tick", now)
        if self.stopping():
            self.stop.set()
            return
        if not self.reconciled or now - self.last_reconcile >= self.app.reconcile_seconds:
            await self.reconcile(now)
        self.book = await self.exchange.get_orderbook(self.cfg.symbol)
        if not self.fresh_book(int(time.time())):
            raise ExchangeError("Stale public order book; no execution allowed")
        if self.stopping():
            return
        p = self.manager.position()
        if self.protection.hit(self.book.bid):
            self.emit("Software stop hit; executing only at currently available prices.")
            await self.order(Side.SELL, "software ATR stop", now)
        elif not p.quantity:
            # Discard a stale protective exit trigger when flat.
            self.store.set("exit_pending", False)
        if self.store.get("exit_pending", False) and self.manager.position().quantity:
            await self.order(Side.SELL, "pending strategy exit", now)
        expected = boundary(
            now - self.app.close_grace_seconds, self.cfg.seconds, self.history.offset
        )
        if not self.last_sync or not self.data_ready or expected > self.last_sync:
            synced = await self.history.sync(now, self.app.close_grace_seconds)
            self.data_ready = (
                not synced.missing
                and len(synced.rows) >= self.cfg.warmup
                and bool(synced.rows)
                and fresh(synced.rows[-1], int(time.time()), self.cfg.seconds)
            )
            if not self.data_ready:
                if self.primed:
                    self.emit(
                        "Entry pause: incomplete or stale candle window; backfill will retry."
                    )
                self.primed = False
                return
            self.last_sync = synced.end
            signal = self.strategy.decide(synced.rows)
            self.latest_signal = signal.action.value
            # First sync on every startup/wake primes state but never replays an old entry.
            previous_ts = self.store.get("processed_signal", -1)
            primed, self.primed = self.primed, True
            if signal.ts > previous_ts:
                self.store.set("processed_signal", signal.ts)
                if signal.action == Action.SELL and self.manager.position().quantity:
                    self.store.set("exit_pending", True)
                    await self.order(Side.SELL, "closed-candle strategy exit", signal.ts)
                elif (
                    signal.action == Action.BUY
                    and primed
                    and int(time.time()) - signal.ts - self.cfg.seconds
                    <= self.app.entry_delay_seconds
                ):
                    await self.order(
                        Side.BUY, "closed-candle crossover", signal.ts, D(str(signal.distance))
                    )
            # Update trailing stop only after evaluating previously active stop, never backdate it.
            if p.quantity and self.manager.position().quantity:
                self.protection.tighten(D(str(synced.rows[-1].high)), D(str(signal.distance)))
        balances = await self.exchange.get_balances()
        p = self.manager.position()
        equity = balances["USDT"].total + p.quantity * self.book.bid
        blocked = self.risk.observe(self.risk_config, equity, now)
        previous = self.store.get("risk_reason", "")
        with self.store.db:
            self.store.write("risk", self.risk.serialize())
            self.store.write("risk_reason", blocked or "")
        if blocked and blocked != previous:
            self.emit("Risk circuit breaker: " + blocked)
        while not self.commands.empty() and not self.stopping():
            await self.command(self.commands.get_nowait())
        if now - self.last_heartbeat >= self.app.heartbeat_seconds:
            self.last_heartbeat = now
            self.emit(
                f"Heartbeat: simulated equity={equity:.4f} USDT, position={p.quantity}, "
                f"paused={self.manual_pause}, risk={blocked or 'clear'}, fault={self.fault or 'none'}."
            )
        if now // 86400 > self.last_day:
            if self.last_day >= 0:
                baseline = D(self.store.get("summary_equity", str(equity)))
                self.emit(
                    f"Daily UTC summary: equity={equity:.4f}, change={equity - baseline:.4f}, "
                    f"cumulative realized={p.realized:.4f} USDT."
                )
            self.last_day = now // 86400
            with self.store.db:
                self.store.write("summary_day", self.last_day)
                self.store.write("summary_equity", str(equity))
        self.api_errors = 0

    async def shutdown(self) -> bool:
        self.stop.set()
        clean = False
        try:
            await self.manager.reconcile(cancel=True)
            clean = True
        except ExchangeError:
            self.emit(
                "WARNING: Shutdown reconciliation/cancellation NOT confirmed; review state manually."
            )
        self.store.set("clean_stop", clean)
        self.emit(
            f"Bot stopped; clean reconciliation={clean}. "
            f"Remaining BTC={self.manager.position().quantity}. No liquidation was requested. "
            "Software protection is now offline."
        )
        return clean
