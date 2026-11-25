"""Explicit research-only, multi-symbol PAPER runner with durable control state."""

import json
import time
from dataclasses import replace
from decimal import Decimal as D
from hashlib import sha256

from app.config import ConfigError
from app.engine import Engine
from data.history import boundary, fresh
from exchange.base import ExchangeError, Request, Side
from execution import ReconcileError, order_key
from execution.portfolio import PortfolioLedger, limit_price
from notify import PORTFOLIO_COMMANDS, RESUME_CONFIRMATION
from risk import down
from risk.portfolio import PortfolioRisk, held_correlation, open_risk, quantity
from strategy.layered import DAY, Layer, LayeredPortfolio


def aligned_recent(store, symbols, end, offset):
    """Use one common, continuous raw-grid origin for every asset's recursive indicators."""
    data = {
        s: {r.ts: r for r in store.candles(s, "1d", end=end) if r.ts % DAY == offset}
        for s in symbols
    }
    shared = sorted(set.intersection(*(set(rows) for rows in data.values())))
    if not shared:
        return {s: [] for s in symbols}
    start = len(shared) - 1
    while start > 0 and shared[start] - shared[start - 1] == DAY:
        start -= 1
    return {s: [rows[t] for t in shared[start:]] for s, rows in data.items()}


class PortfolioEngine(Engine):
    def __init__(
        self, settings, cfg, limits, costs, app, exchange, histories, store, outbox, kill, logger
    ):
        # Deliberately do not initialize the legacy BTC-only manager or its database keys.
        import asyncio

        self.settings, self.cfg, self.limits, self.risk_config, self.app = (
            settings,
            cfg,
            limits,
            costs,
            app,
        )
        self.exchange, self.histories, self.store, self.outbox = exchange, histories, store, outbox
        self.kill, self.logger = kill, logger
        self.stop = asyncio.Event()
        self.commands = asyncio.Queue(maxsize=16)
        self.ledger = PortfolioLedger(exchange, store, tuple(histories), app.order_timeout_seconds)
        self.strategy = LayeredPortfolio(cfg)
        self.risk = PortfolioRisk.restore(store.get("portfolio_risk", {}))
        self.manual_pause = bool(store.get("manual_pause", False))
        self.fault = store.get("fault", "")
        self.api_errors = 0
        self.data_ready = self.primed = self.reconciled = False
        self.last_tick = self.last_sync = self.last_reconcile = self.last_heartbeat = 0
        self.books, self.features, self.returns = {}, {}, {}

    def bind_configuration(self):
        values = [
            self.cfg.model_dump(mode="json"),
            self.limits.model_dump(mode="json"),
            self.risk_config.model_dump(mode="json"),
            self.app.model_dump(mode="json"),
            list(self.histories),
            str(self.settings.max_capital_quote),
        ]
        fingerprint = sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
        previous = self.store.get("configuration_fingerprint")
        if previous and previous != fingerprint:
            raise ConfigError(
                "Portfolio configuration changed; preserve state and use a new reviewed experiment database"
            )
        self.store.set("configuration_fingerprint", fingerprint)
        self.store.set("portfolio_limits", self.limits.model_dump(mode="json"))

    async def startup(self, now):
        self.bind_configuration()
        last = self.store.get("last_tick")
        if last is not None:
            if now < last - 10:
                raise ConfigError("System clock moved backwards")
            self.emit(
                f"Portfolio downtime={now - last}s; no entry replay; software stops were offline."
            )
        self.store.set("clean_stop", False)
        await self.reconcile(now)
        self.emit(
            "LayeredPortfolio research PAPER started (NOT VALIDATED). Separate wallet; LIVE writes blocked."
        )

    async def enqueue(self, command):
        if command in PORTFOLIO_COMMANDS and not self.commands.full():
            self.commands.put_nowait(command)
        else:
            await super().enqueue(command)

    async def reconcile(self, now):
        self.reconciled = False
        await self.ledger.reconcile()
        self.ledger.update_closures(self.limits, self.risk)
        for symbol, manager in self.ledger.managers.items():
            if not manager.position().quantity:
                self.store.set(f"exit_pending:{symbol}", False)
        self.reconciled, self.last_reconcile = True, now

    def fresh_books(self, now):
        return set(self.books) == set(self.histories) and all(
            -10 <= now - book.ts <= self.app.book_max_age_seconds for book in self.books.values()
        )

    async def observe(self, now):
        if not self.fresh_books(now):
            self.data_ready = False
            raise ExchangeError("Portfolio risk marks stale or incomplete")
        balances = await self.exchange.get_balances()
        self.ledger.check(balances)
        lots = self.ledger.lots()
        marks = {s: b.bid for s, b in self.books.items()}
        self.ledger.update_closures(self.limits, self.risk)
        equity = balances["USDT"].total + sum((p.qty * marks[s] for s, p in lots.items()), D(0))
        self.risk.observe(self.limits, equity, now)
        reason = self.risk.blocks(self.limits, now)
        old = self.store.get("risk_reason", "")
        with self.store.db:
            self.store.write("portfolio_risk", self.risk.dump())
            self.store.write("risk_reason", reason or "")
        if reason and reason != old:
            self.emit(
                "Portfolio circuit breaker: "
                + reason
                + ". Protective exits remain active; halt requires typed /resume."
            )
        elif old and not reason:
            self.emit(
                f"Portfolio risk block ended by its documented recovery/day/cooldown rule: {old}. "
                "Manual pause, operational faults and KILL are unchanged; consumed signals are not replayed."
            )
        return balances, lots, marks

    async def order(self, symbol, side, reason, ts, entry=None):
        # The state machine owns all uncertain outcomes. Never place a replacement blindly.
        if self.stopping() or not self.reconciled:
            return
        manager = self.ledger.managers[symbol]
        if any(m.active() for m in self.ledger.managers.values()):
            self.reconciled = False
            raise ReconcileError("Unresolved portfolio order; reconcile before another submission")
        rules = await self.exchange.get_symbol_rules(symbol)
        self.books[symbol] = await self.exchange.get_orderbook(symbol)
        balances, lots, marks = await self.observe(int(time.time()))
        if self.stopping() or not self.fresh_books(int(time.time())):
            return
        book = self.books[symbol]
        price = limit_price(book, side, rules, self.risk_config.slippage)
        metadata = None
        if side == Side.BUY:
            if self.manual_pause or self.fault or not self.data_ready or entry is None:
                return
            now = int(time.time())
            if not 0 <= now - ts - DAY <= self.app.entry_delay_seconds:
                return
            if (book.ask - book.bid) / book.bid > self.risk_config.max_spread:
                return
            if entry.distance >= book.ask * (1 - self.risk_config.slippage):
                return
            qty = quantity(
                self.limits,
                self.risk,
                now,
                entry,
                lots,
                marks,
                balances["USDT"].free,
                self.settings.max_capital_quote,
                price,
                rules,
                self.exchange.fee,
                self.risk_config.slippage,
                self.returns,
            )
            key = f"entry_consumed:{symbol}"
            if self.store.get(key) == ts:
                return
            self.store.set(key, ts)
            metadata = (f"lot:{symbol}", {"layer": str(entry.layer), "entry_ts": ts + DAY})
        else:
            base = symbol.split("/")[0]
            qty = down(min(manager.position().quantity, balances[base].free), rules.quantity_step)
        if qty <= 0 or price <= 0 or qty < rules.min_quantity or qty * price < rules.min_quote:
            if side == Side.SELL and manager.position().quantity:
                self.latch(
                    "Portfolio residual cannot satisfy current venue minimum; manual review required"
                )
            return
        count = self.store.db.execute("SELECT count(*) FROM intent").fetchone()[0]
        cid = order_key(symbol, "1d", ts, reason, count)
        if self.stopping():
            return
        distance = entry.distance if entry else D(0)
        order = await manager.submit(
            Request(cid, side, qty, price, distance), reason, metadata=metadata
        )
        if order:
            self.emit(
                f"{symbol} {side} {order.state}: qty={order.filled}, reason={reason}; SOFTWARE stop only."
            )
        await self.observe(int(time.time()))

    async def tick(self, now):
        if self.last_tick and now < self.last_tick - 5:
            self.latch("Clock moved backwards; restart after diagnosis")
        if self.last_tick and now - self.last_tick > 2 * self.app.poll_seconds:
            self.primed, self.last_sync = False, 0
            self.emit("Portfolio wake gap; re-prime without stale entries.")
        self.last_tick = now
        self.store.set("last_tick", now)
        if self.stopping():
            self.stop.set()
            return
        if not self.reconciled or now - self.last_reconcile >= self.app.reconcile_seconds:
            await self.reconcile(now)
        # A missing asset feed must not suppress a fresh-book protective exit in another asset.
        errors = []
        for symbol in self.histories:
            try:
                self.books[symbol] = await self.exchange.get_orderbook(symbol)
            except ExchangeError as error:
                self.books.pop(symbol, None)
                errors.append(error)
        for symbol, lot in sorted(self.ledger.lots().items()):
            book = self.books.get(symbol)
            if book and -10 <= int(time.time()) - book.ts <= self.app.book_max_age_seconds:
                if book.bid <= lot.stop:
                    self.store.set(f"exit_pending:{symbol}", "software stop")
                if self.store.get(f"exit_pending:{symbol}"):
                    await self.protective_order(symbol, now)
        if errors:
            self.data_ready = False
            self.primed = False
            raise errors[0]
        await self.observe(int(time.time()))
        history = next(iter(self.histories.values()))
        expected = boundary(now - self.app.close_grace_seconds, DAY, history.offset)
        if not self.last_sync or not self.data_ready or expected > self.last_sync:
            self.data_ready = False
            for h in self.histories.values():
                synced = await h.sync(now, self.app.close_grace_seconds)
                if (
                    synced.missing
                    or len(synced.rows) < self.cfg.warmup
                    or not fresh(synced.rows[-1], int(time.time()), DAY)
                ):
                    self.primed = False
                    return
            data = aligned_recent(history.store, tuple(self.histories), expected, history.offset)
            if any(
                len(rows) < self.cfg.warmup or rows[-1].ts != expected - DAY
                for rows in data.values()
            ):
                self.primed = False
                return
            self.features = {s: self.strategy.prepare(rows)[-1] for s, rows in data.items()}
            self.returns = {
                s: [b.close / a.close - 1 for a, b in zip(rows, rows[1:])][
                    -self.limits.correlation_days :
                ]
                for s, rows in data.items()
            }
            self.data_ready, self.last_sync = True, expected
            primed, self.primed = self.primed, True
            ts = expected - DAY
            previous = self.store.get("processed_signal", -1)
            held_at_decision = set(self.ledger.lots()) | {
                symbol
                for symbol in self.histories
                if self.store.get(f"exit_bar:{symbol}") == expected
            }
            # Activate the just-closed candle's trailing low for pre-existing positions.
            # Never backdate it, and never tighten a newly filled open with yesterday's trail.
            for symbol, lot in self.ledger.lots().items():
                if lot.entry_ts >= expected:
                    continue
                manager = self.ledger.managers[symbol]
                stop = self.strategy.next_stop(lot, self.features[symbol])
                if stop > lot.stop:
                    with self.store.db:
                        manager.save_position(replace(manager.position(), stop=stop))
                if self.books[symbol].bid <= stop:
                    self.store.set(f"exit_pending:{symbol}", "new daily trailing stop")
                    await self.protective_order(symbol, expected)
            if ts > previous:
                # Consume the entire close before any side effect; a crash can skip but never replay it.
                self.store.set("processed_signal", ts)
                for symbol, lot in sorted(self.ledger.lots().items()):
                    reason = self.strategy.exit(lot, self.features[symbol], expected)
                    if reason:
                        self.store.set(f"exit_pending:{symbol}", reason)
                        await self.protective_order(symbol, expected)
                if primed and 0 <= int(time.time()) - expected <= self.app.entry_delay_seconds:
                    for entry in self.strategy.entries(self.features, held_at_decision):
                        await self.order(
                            entry.symbol, Side.BUY, "closed daily " + str(entry.layer), ts, entry
                        )
            if self.store.get("summary_close", -1) < ts:
                await self.observe(int(time.time()))
                self.store.set("summary_close", ts)
                await self.command("/portfolio")
                self.emit(
                    f"Daily close summary (raw open timestamp {ts}); regime risk-on={self.features['BTC/USDT'].above}."
                )
        self.api_errors = 0

    async def protective_order(self, symbol, ts):
        """Exit with its own fresh book, even when another symbol's feed has failed."""
        if self.stopping() or not self.reconciled:
            return
        manager = self.ledger.managers[symbol]
        if any(m.active() for m in self.ledger.managers.values()):
            raise ReconcileError("Unresolved portfolio intent before protective exit")
        book = await self.exchange.get_orderbook(symbol)
        self.books[symbol] = book
        rules = await self.exchange.get_symbol_rules(symbol)
        balances = await self.exchange.get_balances()
        self.ledger.check(balances)
        if (
            self.stopping()
            or not -10 <= int(time.time()) - book.ts <= self.app.book_max_age_seconds
        ):
            return
        qty = down(
            min(manager.position().quantity, balances[symbol.split("/")[0]].free),
            rules.quantity_step,
        )
        price = limit_price(book, Side.SELL, rules, self.risk_config.slippage)
        if qty <= 0:
            self.store.set(f"exit_pending:{symbol}", False)
            return
        if qty < rules.min_quantity or qty * price < rules.min_quote or price <= 0:
            self.latch("Portfolio stop residual below exchange minimum; manual review required")
            return
        reason = self.store.get(f"exit_pending:{symbol}") or "protective exit"
        count = self.store.db.execute("SELECT count(*) FROM intent").fetchone()[0]
        result = await manager.submit(
            Request(order_key(symbol, "1d", ts, reason, count), Side.SELL, qty, price), reason
        )
        self.ledger.update_closures(self.limits, self.risk)
        if not manager.position().quantity:
            with self.store.db:
                self.store.write(f"exit_pending:{symbol}", False)
                history = self.histories[symbol]
                self.store.write(
                    f"exit_bar:{symbol}", boundary(int(time.time()), DAY, history.offset)
                )
        if result:
            self.emit(f"{symbol} protective {result.state}: filled={result.filled}; {reason}.")

    async def command(self, command):
        now = int(time.time())
        if command in {"/portfolio", "/positions", "/status", "/pnl"}:
            lots = self.ledger.lots()
            positions = (
                "; ".join(f"{s} {p.layer}: qty={p.qty}, stop={p.stop}" for s, p in lots.items())
                or "cash only"
            )
            used = (
                open_risk(
                    lots,
                    {s: self.books[s].bid for s in lots},
                    self.exchange.fee,
                    self.risk_config.slippage,
                )
                if self.fresh_books(now)
                else None
            )
            self.emit(
                f"Portfolio: {positions}; last equity={self.risk.equity:.4f}; peak={self.risk.peak:.4f}; DD=-{self.risk.drawdown:.2%}; open risk={used}; marks fresh={self.fresh_books(now)}; breaker={self.risk.blocks(self.limits, now) or 'clear'}; pause={self.manual_pause}; fault={self.fault or 'none'}."
            )
        elif command == "/layers":
            self.emit(
                f"Research mode; configured default enabled={self.cfg.enabled}; {Layer.TREND}={self.cfg.trend_enabled}; {Layer.PULLBACK}={self.cfg.pullback_enabled}; BTC filter={self.cfg.btc_filter}; breadth={self.cfg.breadth_enabled}. No remote parameter changes."
            )
        elif command == "/risk":
            corr = held_correlation(self.ledger.lots(), self.returns, self.limits.correlation_days)
            self.emit(
                f"Risk: {self.risk.blocks(self.limits, now) or 'clear'}; halted={self.risk.halted}; daily latch={self.risk.daily_latched}; cooldown until={self.risk.cooldown_until}; correlation={corr}; caps open={self.limits.open_risk:.2%}, asset={self.limits.asset_cap:.2%}, positions={self.limits.max_positions}; {RESUME_CONFIRMATION} required for halt, recovery required, peak never reset."
            )
        elif command in {"/resume", RESUME_CONFIRMATION}:
            if (
                self.fault
                or not self.data_ready
                or not self.reconciled
                or not self.fresh_books(now)
            ):
                self.emit("Resume refused: fault, stale data or unresolved reconciliation.")
                return
            await self.observe(now)
            if self.risk.halted:
                if command != RESUME_CONFIRMATION or not self.risk.resume(
                    self.limits, "I UNDERSTAND THE RISK"
                ):
                    self.emit(
                        "Halt remains latched. Exact typed confirmation AND DD recovery below 15% required; no peak reset."
                    )
                    return
                self.store.set("portfolio_risk", self.risk.dump())
            if self.risk.blocks(self.limits, now):
                self.emit("Resume refused: another risk breaker remains active.")
                return
            self.manual_pause = False
            self.store.set("manual_pause", False)
            self.emit("Manual pause cleared; stale signals still cannot replay.")
        elif command == "/help":
            self.emit(
                "Commands: /portfolio /layers /risk /status /balance /positions /pnl /pause /resume /stop /mode. Halt: "
                + RESUME_CONFIRMATION
                + ". /stop is not liquidation."
            )
        elif command == "/mode":
            self.emit("Research PAPER only. LIVE writes are blocked, no remote mode change.")
        elif command == "/balance":
            balances = await self.exchange.get_balances()
            self.emit(
                "Simulated wallet: " + "; ".join(f"{s}={b.total}" for s, b in balances.items())
            )
        elif command == "/pause":
            self.manual_pause = True
            self.store.set("manual_pause", True)
            self.emit("Portfolio entries paused; protective exits remain active.")

    async def shutdown(self):
        self.stop.set()
        clean = False
        try:
            await self.ledger.reconcile(cancel=True)
            self.ledger.update_closures(self.limits, self.risk)
            clean = True
        except ExchangeError:
            self.emit(
                "WARNING: Portfolio shutdown reconciliation unconfirmed; manual review required."
            )
        self.store.set("clean_stop", clean)
        self.emit(
            f"Portfolio stopped; clean reconciliation={clean}; held={list(self.ledger.lots())}. No liquidation. Software stops now offline."
        )
        return clean
