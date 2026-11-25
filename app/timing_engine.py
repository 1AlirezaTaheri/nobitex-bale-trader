"""Isolated opt-in daily timing PAPER engine; never submits to live transport."""

import asyncio
import json
import logging
import time
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path

from app.config import ConfigError
from app.engine import Engine
from app.timing_config import TimingConfig
from app.universe import utc
from data.history import boundary, fresh
from data.store import Store
from exchange.base import ExchangeError, Request, Side
from exchange.paper import PaperExchange
from execution import OrderManager, ReconcileError, order_key
from execution.portfolio import limit_price
from notify import COMMANDS, RESUME_CONFIRMATION
from risk import down
from risk.portfolio import PortfolioLimits, PortfolioRisk
from strategy.timing import Candidate, prepare, raw_targets

DAY = 86400


def risk_overlay_targets(accepted, current, scale):
    """Apply the DD scale to increases only; preserve target reductions exactly."""
    if not D(0) <= scale <= D(1):
        raise ValueError("Risk overlay scale must be in [0, 1]")
    return {
        symbol: max(current[symbol], accepted[symbol] * scale)
        if accepted[symbol] > current[symbol]
        else accepted[symbol]
        for symbol in accepted
    }


def aligned_recent(store, symbols, end, offset):
    data = {
        symbol: {
            row.ts: row for row in store.candles(symbol, "1d", end=end) if row.ts % DAY == offset
        }
        for symbol in symbols
    }
    shared = sorted(set.intersection(*(set(rows) for rows in data.values())))
    if not shared:
        return {symbol: [] for symbol in symbols}
    first = len(shared) - 1
    while first > 0 and shared[first] - shared[first - 1] == DAY:
        first -= 1
    return {symbol: [rows[ts] for ts in shared[first:]] for symbol, rows in data.items()}


def protocol_hash():
    manifest_path = Path(__file__).resolve().parents[1] / "reports/v3_preregistration_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    source = manifest_path.parents[1] / manifest["file"]
    actual = sha256(source.read_bytes()).hexdigest()
    if actual != manifest["sha256"]:
        raise ConfigError("Frozen V3 protocol checksum mismatch; PAPER start refused")
    return actual


class TimingLedger:
    """Reuse per-symbol intent managers while omitting unsupported stop metadata."""

    def __init__(self, exchange, store, symbols, timeout):
        self.exchange, self.store = exchange, store
        self.managers = {
            symbol: OrderManager(
                exchange,
                store,
                symbol,
                timeout,
                shared_check=self.check,
                allow_additions=True,
            )
            for symbol in symbols
        }

    def check(self, balances):
        positions = {
            symbol.split("/")[0]: manager.position() for symbol, manager in self.managers.items()
        }
        if set(balances) != set(positions) | {"USDT"} or any(
            balances[asset].total != position.quantity for asset, position in positions.items()
        ):
            raise ReconcileError("Timing PAPER balances do not match the separate position ledger")
        baseline = self.store.get("initial_quote")
        if baseline is None:
            if self.store.db.execute("SELECT count(*) FROM intent").fetchone()[0] or any(
                position.quantity for position in positions.values()
            ):
                raise ReconcileError("Missing timing PAPER starting cash; preserve state")
            baseline = str(balances["USDT"].total)
            self.store.set("initial_quote", baseline)
        expected = D(baseline) + sum(
            (position.realized - position.cost for position in positions.values()), D(0)
        )
        if abs(balances["USDT"].total - expected) > D("0.000000000000000001"):
            raise ReconcileError("Timing PAPER quote balance does not reconcile")

    async def reconcile(self):
        if any(
            row[0] not in self.managers
            for row in self.store.db.execute(
                "SELECT s.symbol FROM intent i LEFT JOIN intent_scope s USING (cid)"
            )
        ):
            raise ReconcileError("Unscoped or unexpected timing PAPER intent; preserve state")
        for manager in self.managers.values():
            await manager.reconcile_orders()
        balances = await self.exchange.get_balances()
        self.check(balances)
        return balances

    def update_closures(self, limits, risk):
        cursor = self.store.get("portfolio_closure_cursor", 0)
        rows = list(
            self.store.db.execute(
                "SELECT seq,pnl,ts FROM portfolio_closure WHERE seq>? ORDER BY seq", (cursor,)
            )
        )
        if rows:
            for _, pnl, ts in rows:
                risk.closed(limits, D(pnl), ts)
            with self.store.db:
                self.store.write("portfolio_risk", risk.dump())
                self.store.write("portfolio_closure_cursor", rows[-1][0])


class TimingEngine(Engine):
    def __init__(
        self,
        settings,
        cfg: TimingConfig,
        candidate: Candidate,
        symbols,
        limits: PortfolioLimits,
        risk_config,
        app,
        exchange,
        histories,
        store: Store,
        outbox,
        kill: Path,
        logger: logging.Logger,
    ):
        if settings.mode != "paper" or not isinstance(exchange, PaperExchange):
            raise ConfigError("TimingEngine requires the isolated simulated PAPER exchange")
        self.settings, self.cfg, self.candidate, self.symbols = (
            settings,
            cfg,
            candidate,
            tuple(symbols),
        )
        self.limits, self.risk_config, self.app = limits, risk_config, app
        self.exchange, self.histories, self.store, self.outbox = exchange, histories, store, outbox
        self.kill, self.logger = kill, logger
        self.stop = asyncio.Event()
        self.commands: asyncio.Queue[str] = asyncio.Queue(maxsize=16)
        self.ledger = TimingLedger(exchange, store, self.symbols, app.order_timeout_seconds)
        self.risk = PortfolioRisk.restore(store.get("portfolio_risk", {}))
        self.manual_pause = bool(store.get("manual_pause", False))
        self.fault = store.get("fault", "")
        self.books = {}
        self.data_ready = self.reconciled = False
        self.last_tick = self.last_reconcile = self.last_sync = self.last_heartbeat = 0
        self.api_errors = 0
        self.stale_signal_to_skip = None
        self._bind_configuration()

    def emit(self, message):
        self.logger.info(message)
        self.outbox.emit(f"[PAPER Timing {self.candidate}] {message}")

    def _bind_configuration(self):
        fingerprint = sha256(
            json.dumps(
                {
                    "candidate": self.candidate.value,
                    "symbols": self.symbols,
                    "timing": self.cfg.model_dump(mode="json"),
                    "risk": self.limits.model_dump(mode="json"),
                    "risk_config": self.risk_config.model_dump(mode="json"),
                    "capital": str(self.settings.max_capital_quote),
                    "protocol_sha256": protocol_hash(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        prior = self.store.get("configuration_fingerprint")
        if prior and prior != fingerprint:
            raise ConfigError(
                "Timing PAPER configuration changed; use a new candidate-specific database"
            )
        self.store.set("configuration_fingerprint", fingerprint)
        self.store.set("protocol_sha256", protocol_hash())
        if self.store.get("paper_start_utc") is None:
            self.store.set("paper_start_utc", utc(int(time.time())))

    def stopping(self):
        return self.stop.is_set() or self.kill.exists()

    async def enqueue(self, command):
        if command == "/stop":
            self.kill.touch(exist_ok=True)
            self.stop.set()
            return
        if command == "/pause":
            self.manual_pause = True
            self.store.set("manual_pause", True)
        if command in COMMANDS or command == RESUME_CONFIRMATION:
            if not self.commands.full():
                self.commands.put_nowait(command)

    async def startup(self, now):
        self.last_tick = int(self.store.get("last_tick", 0))
        if not self.last_tick:
            self.stale_signal_to_skip = (
                boundary(now - self.app.close_grace_seconds, DAY, 73800) - DAY
            )
        else:
            gap = now - self.last_tick
            if gap < -10:
                raise ConfigError("System clock moved backwards; daily timing PAPER refused")
            if gap > 2 * self.app.poll_seconds or self.last_tick < boundary(now, DAY, 73800):
                self.stale_signal_to_skip = (
                    boundary(now - self.app.close_grace_seconds, DAY, 73800) - DAY
                )
            self.emit(
                f"Restart detected; downtime={gap}s. Any missed close signal will not be replayed."
            )
        self.store.set("clean_stop", False)
        await self.reconcile(now)
        self.last_tick = now
        self.store.set("last_tick", now)
        self.emit(
            f"Daily timing PAPER started; candidate={self.candidate.value}; symbols={self.symbols}; "
            f"protocol={self.store.get('protocol_sha256')}; start={self.store.get('paper_start_utc')}; LIVE blocked."
        )

    async def reconcile(self, now):
        self.reconciled = False
        await self.ledger.reconcile()
        self.ledger.update_closures(self.limits, self.risk)
        self.reconciled, self.last_reconcile = True, now

    async def observe(self, now):
        if set(self.books) != set(self.symbols) or any(
            not -10 <= now - self.books[symbol].ts <= self.app.book_max_age_seconds
            for symbol in self.symbols
        ):
            self.data_ready = False
            raise ExchangeError(
                "Timing PAPER requires a fresh public order book for every selected asset"
            )
        balances = await self.exchange.get_balances()
        self.ledger.check(balances)
        equity = balances["USDT"].total + sum(
            (
                self.ledger.managers[symbol].position().quantity * self.books[symbol].bid
                for symbol in self.symbols
            ),
            D(0),
        )
        self.risk.observe(self.limits, equity, now)
        with self.store.db:
            self.store.write("portfolio_risk", self.risk.dump())
        return balances, equity

    def _targets(self, expected):
        offset = 73800
        aligned = aligned_recent(
            self.histories[self.symbols[0]].store, self.symbols, expected, offset
        )
        if any(
            len(aligned[symbol]) < 300 or aligned[symbol][-1].ts != expected - DAY
            for symbol in self.symbols
        ):
            raise ExchangeError(
                "Timing PAPER feeds are not jointly aligned on the current raw daily grid"
            )
        features = {symbol: prepare(aligned[symbol]) for symbol in self.symbols}
        targets = raw_targets(features, self.candidate)
        return {symbol: D(str(targets[-1].get(symbol, 0.0))) for symbol in self.symbols}, aligned

    async def _place_delta(
        self, symbol, target_weight, target_equity, signal_ts, reason, *, side_only
    ):
        if self.stopping() or not self.reconciled or not self.data_ready:
            return
        manager = self.ledger.managers[symbol]
        if any(item.active() for item in self.ledger.managers.values()):
            self.reconciled = False
            raise ReconcileError(
                "Unresolved timing PAPER order; reconcile before another submission"
            )
        rules = await self.exchange.get_symbol_rules(symbol)
        book = self.books[symbol] = await self.exchange.get_orderbook(symbol)
        now = int(time.time())
        if not 0 <= now - (signal_ts + DAY) <= self.app.entry_delay_seconds:
            return
        if not -10 <= now - book.ts <= self.app.book_max_age_seconds:
            raise ExchangeError("Timing PAPER refused a stale execution book")
        balances, _ = await self.observe(now)
        position = manager.position()
        target_quote = target_weight * target_equity
        current_quote = position.quantity * book.bid
        quote_delta = target_quote - current_quote
        if (side_only == Side.SELL and quote_delta >= 0) or (
            side_only == Side.BUY and quote_delta <= 0
        ):
            return
        if quote_delta.copy_abs() < rules.min_quote:
            return
        if quote_delta < 0:
            side = Side.SELL
            price = limit_price(book, side, rules, self.risk_config.slippage)
            qty = down(min(position.quantity, -quote_delta / book.bid), rules.quantity_step)
        else:
            if self.manual_pause or self.fault or self.risk.blocks(self.limits, now):
                return
            side = Side.BUY
            price = limit_price(book, side, rules, self.risk_config.slippage)
            ask_cost = price * (1 + self.exchange.fee)
            available = min(
                balances["USDT"].free,
                max(D(0), D(str(self.settings.max_capital_quote)) - current_quote),
            )
            qty = down(min(quote_delta / price, available / ask_cost), rules.quantity_step)
        if qty <= 0 or qty < rules.min_quantity or qty * price < rules.min_quote:
            return
        if self.stopping():
            return
        attempts = self.store.db.execute("SELECT count(*) FROM intent").fetchone()[0]
        request = Request(order_key(symbol, "1d", signal_ts, reason, attempts), side, qty, price)
        order = await manager.submit(request, reason)
        if order:
            self.emit(
                f"{symbol} {side}: simulated {order.state}; quantity={order.filled}; reason={reason}."
            )
        self.ledger.update_closures(self.limits, self.risk)
        await self.observe(int(time.time()))

    async def _process_close(self, expected, now):
        signal_ts = expected - DAY
        if signal_ts <= self.store.get("processed_signal", -1):
            return
        weights, aligned = self._targets(expected)
        prior = self.store.get("accepted_target", {symbol: "0" for symbol in self.symbols})
        previous = {symbol: D(prior.get(symbol, "0")) for symbol in self.symbols}
        change = sum(abs(weights[symbol] - previous[symbol]) for symbol in self.symbols)
        threshold = D(0) if self.candidate == Candidate.A else D("0.25")
        accepted = weights if change + D("1e-12") >= threshold else previous
        skip = self.stale_signal_to_skip == signal_ts or not (
            0 <= now - expected <= self.app.entry_delay_seconds
        )
        with self.store.db:
            self.store.write("processed_signal", signal_ts)
            self.store.write("last_close_ts", signal_ts)
            if accepted != previous:
                self.store.write("accepted_target", {s: str(w) for s, w in accepted.items()})
        if self.stale_signal_to_skip == signal_ts:
            self.stale_signal_to_skip = None
        if skip:
            self.emit(
                f"Skipped daily signal {utc(signal_ts)}: stale after downtime or outside the fresh entry window."
            )
            return
        if accepted == previous:
            return
        _, equity = await self.observe(now)
        target_equity = min(equity, D(str(self.settings.max_capital_quote)))
        risk_scale = D("0.5") if self.risk.drawdown >= self.limits.half_dd else D(1)
        current_weights = {
            s: self.ledger.managers[s].position().quantity * self.books[s].bid / target_equity
            if target_equity > 0
            else D(0)
            for s in self.symbols
        }
        # Scale increases only; never turn an increase into a sale or deepen a reduction.
        execution_target = risk_overlay_targets(accepted, current_weights, risk_scale)
        # Reductions first; only then can additions use the released quote balance.
        for symbol in self.symbols:
            position = self.ledger.managers[symbol].position()
            target_value = execution_target[symbol] * target_equity
            if position.quantity * self.books[symbol].bid > target_value:
                await self._place_delta(
                    symbol,
                    execution_target[symbol],
                    target_equity,
                    signal_ts,
                    "daily target reduction",
                    side_only=Side.SELL,
                )
        for symbol in self.symbols:
            position = self.ledger.managers[symbol].position()
            target_value = execution_target[symbol] * target_equity
            if position.quantity * self.books[symbol].bid < target_value:
                await self._place_delta(
                    symbol,
                    execution_target[symbol],
                    target_equity,
                    signal_ts,
                    "fresh daily timing target",
                    side_only=Side.BUY,
                )
        self.store.set("last_target_close_utc", utc(signal_ts))
        self.emit(
            f"Daily close {utc(signal_ts)} accepted; target={{{', '.join(f'{s}:{accepted[s]:.2%}' for s in self.symbols)}}}; "
            f"risk overlay scale={risk_scale}; aligned candles={len(aligned[self.symbols[0]])}."
        )

    async def tick(self, now):
        now = int(now)
        if self.last_tick and now < self.last_tick - 5:
            self.fault = "clock moved backwards"
            self.store.set("fault", self.fault)
        if self.last_tick and now - self.last_tick > 2 * self.app.poll_seconds:
            self.stale_signal_to_skip = (
                boundary(now - self.app.close_grace_seconds, DAY, 73800) - DAY
            )
            self.last_sync = 0
            self.emit(
                "Wake gap detected; the latest missed close will be consumed without a delayed rebalance."
            )
        self.last_tick = now
        self.store.set("last_tick", now)
        if self.stopping():
            self.stop.set()
            return
        if not self.reconciled or now - self.last_reconcile >= self.app.reconcile_seconds:
            await self.reconcile(now)
        for symbol in self.symbols:
            self.books[symbol] = await self.exchange.get_orderbook(symbol)
        await self.observe(int(time.time()))
        expected = boundary(now - self.app.close_grace_seconds, DAY, 73800)
        if self.last_sync and expected <= self.last_sync:
            self.data_ready = True
            return
        for history in self.histories.values():
            synced = await history.sync(now, self.app.close_grace_seconds)
            if (
                synced.missing
                or len(synced.rows) < self.cfg.warmup
                or synced.rows[-1].ts != expected - DAY
                or not fresh(synced.rows[-1], int(time.time()), DAY)
            ):
                self.data_ready = False
                return
        aligned = aligned_recent(
            self.histories[self.symbols[0]].store, self.symbols, expected, 73800
        )
        if any(not values or values[-1].ts != expected - DAY for values in aligned.values()):
            self.data_ready = False
            return
        self.data_ready, self.last_sync = True, expected
        await self._process_close(expected, int(time.time()))
        self.api_errors = 0

    async def command(self, command):
        now = int(time.time())
        if command in {"/status", "/positions", "/pnl"}:
            balances = await self.exchange.get_balances()
            holdings = []
            for symbol, manager in self.ledger.managers.items():
                position = manager.position()
                holdings.append(
                    f"{symbol} qty={position.quantity} value~{position.quantity * self.books[symbol].bid if symbol in self.books else 'unmarked'}"
                )
            self.emit(
                f"Timing PAPER {self.candidate}; {', '.join(holdings)}; USDT={balances['USDT'].total}; "
                f"equity={self.risk.equity}; DD={self.risk.drawdown:.2%}; "
                f"risk={self.risk.blocks(self.limits, now) or 'clear'}; data_ready={self.data_ready}; "
                f"processed_signal={self.store.get('processed_signal')}; start={self.store.get('paper_start_utc')}."
            )
        elif command == "/stop":
            self.stop.set()
            self.emit("Timing PAPER stopped by command; no liquidation.")
        elif command == "/balance":
            balances = await self.exchange.get_balances()
            self.emit(
                "Separate simulated wallet: "
                + "; ".join(f"{s}={b.total}" for s, b in balances.items())
            )
        elif command == "/pause":
            self.manual_pause = True
            self.store.set("manual_pause", True)
            self.emit("Timing PAPER additions paused; target reductions remain allowed.")
        elif command in {"/resume", RESUME_CONFIRMATION}:
            await self.observe(now)
            if self.fault or not self.data_ready or not self.reconciled:
                self.emit(
                    "Resume refused: operational fault, stale data, or unresolved reconciliation."
                )
                return
            confirmation = "I UNDERSTAND THE RISK" if command == RESUME_CONFIRMATION else ""
            if self.risk.halted and not self.risk.resume(self.limits, confirmation):
                self.emit(
                    "Risk halt remains latched until drawdown recovery and exact typed confirmation."
                )
                return
            if self.risk.blocks(self.limits, now):
                self.emit("Resume refused: another risk block remains active.")
                return
            self.manual_pause = False
            self.store.set("manual_pause", False)
            self.store.set("portfolio_risk", self.risk.dump())
            self.emit("Timing PAPER additions resumed; missed signals will not be replayed.")
        elif command == "/mode":
            self.emit("Daily timing PAPER only. LIVE order transport is blocked.")
        elif command == "/help":
            self.emit(
                "Commands: /status /balance /positions /pnl /pause /resume /stop /mode /help. /stop is not liquidation."
            )

    async def shutdown(self):
        self.stop.set()
        clean = False
        try:
            await self.ledger.reconcile()
            self.ledger.update_closures(self.limits, self.risk)
            clean = True
        except ExchangeError:
            self.emit(
                "WARNING: Timing PAPER reconciliation unconfirmed; inspect its database and wallet."
            )
        self.store.set("clean_stop", clean)
        self.emit(
            f"Daily timing PAPER stopped; reconciliation={clean}; no liquidation. Software controls are offline."
        )
        return clean
