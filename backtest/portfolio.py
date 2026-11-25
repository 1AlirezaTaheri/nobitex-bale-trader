"""Event-driven daily portfolio simulation using the common risk and execution rules."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from decimal import Decimal as D

import pandas as pd

from backtest import metrics as base_metrics
from exchange.base import Book, Side
from exchange.paper import executable_quote
from execution.portfolio import limit_price
from risk.portfolio import PortfolioRisk, quantity
from strategy.layered import DAY, Layer, LayeredPortfolio, Lot

ZERO = D(0)


@dataclass(frozen=True)
class PortfolioTrade:
    symbol: str
    layer: Layer
    entry_ts: int
    exit_ts: int
    reason: str
    quantity: float
    pnl: float


@dataclass
class Simulation:
    curve: pd.DataFrame
    trades: list[PortfolioTrade]
    stats: dict
    rejected: Counter
    blocked: Counter


def consecutive(values):
    best = current = 0
    for value in values:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def monthly_returns(curve):
    values = pd.Series(
        curve.equity.to_numpy(), index=pd.to_datetime(curve.timestamp, unit="s", utc=True)
    )
    # Include sample-edge calendar months, with baseline equity for the first partial month.
    monthly = values.resample("ME").last()
    result = monthly.pct_change()
    result.iloc[0] = monthly.iloc[0] / values.iloc[0] - 1
    return result


def statistics(curve, trades, exposed):
    # The legacy statistics helper only requires `pnl` on trade objects.
    m = base_metrics(curve.equity, trades, DAY)
    dd = curve.equity / curve.equity.cummax() - 1
    m["calmar"] = m["cagr"] / -m["max_drawdown"] if m["max_drawdown"] < 0 else None
    m["exposure_fraction"] = float(sum(exposed) / len(exposed)) if exposed else 0.0
    m["longest_flat_days"] = consecutive(not x for x in exposed)
    m["worst_month"] = float(monthly_returns(curve).min())
    m["max_consecutive_losses"] = consecutive(t.pnl < 0 for t in trades)
    m["drawdown_duration_days"] = consecutive(dd < 0)
    m["by_layer"] = {
        str(layer): {
            "trades": len(ts),
            "win_rate": sum(t.pnl > 0 for t in ts) / len(ts) if ts else None,
        }
        for layer in Layer
        if (ts := [t for t in trades if t.layer == layer])
    }
    m["by_asset"] = dict(Counter(t.symbol for t in trades))
    return m


def common_segments(data, offset):
    lookup = {s: {r.ts: r for r in rows if r.ts % DAY == offset} for s, rows in data.items()}
    shared = sorted(set.intersection(*(set(rows) for rows in lookup.values())))
    segments = []
    for ts in shared:
        if not segments or ts - segments[-1][-1] != DAY:
            segments.append([])
        segments[-1].append(ts)
    return [{s: [rows[t] for t in segment] for s, rows in lookup.items()} for segment in segments]


def historical_book(price, prior_volume, ts, limits):
    """Explicit execution assumption, NOT reconstructed historical L2 or fabricated candles."""
    half = limits.historical_half_spread
    depth = D(str(prior_volume)) * limits.historical_volume_fraction
    return Book(ts, ((price * (1 - half), depth),), ((price * (1 + half), depth),))


def daily_returns(rows):
    return [b.close / a.close - 1 for a, b in zip(rows, rows[1:])]


def simulate(
    data, config, limits, rules, fee, slip, capital, *, start=None, end=None, prepared=None
):
    model = LayeredPortfolio(config)
    symbols = sorted(data)
    timeline = [row.ts for row in data[symbols[0]]]
    if any([row.ts for row in data[s]] != timeline for s in symbols) or any(
        b - a != DAY for a, b in zip(timeline, timeline[1:])
    ):
        raise ValueError("Aligned consecutive raw daily candles required")
    start = config.warmup if start is None else start
    end = len(timeline) if end is None else end
    if not config.warmup <= start < end <= len(timeline) or end - start < 2:
        raise ValueError("Insufficient contiguous candles for the requested portfolio window")
    features = (
        prepared if prepared is not None else {s: model.prepare(data[s][:end]) for s in symbols}
    )
    returns = {s: daily_returns(data[s][:end]) for s in symbols}
    state, cash = PortfolioRisk(), capital
    lots, trades, exposed = {}, [], []
    realized = dict.fromkeys(Layer, ZERO)
    points = [(timeline[start], float(capital), 0.0, 0.0, 0)]
    rejected, blocked = Counter(), Counter()
    pending_exits = {}

    def observation(marks, ts):
        state.observe(limits, cash + sum((p.qty * marks[s] for s, p in lots.items()), ZERO), ts)

    def close(symbol, reference, ts, i, cause):
        nonlocal cash
        lot = lots[symbol]
        book = historical_book(reference, data[symbol][i - 1].volume, ts, limits)
        limit = limit_price(book, Side.SELL, rules[symbol], slip)
        if limit <= 0 or lot.qty * limit < rules[symbol].min_quote:
            rejected["exit minimum/price"] += 1
            pending_exits[symbol] = cause
            return False
        quote = executable_quote(book, Side.SELL, lot.qty, limit, slip, rules[symbol].min_quote)
        if quote is None:
            rejected["exit modeled depth"] += 1
            pending_exits[symbol] = cause
            return False
        proceeds = quote * (1 - fee)
        pnl = proceeds - lot.cost
        realized[lot.layer] += pnl
        cash += proceeds
        del lots[symbol]
        pending_exits.pop(symbol, None)
        state.closed(limits, pnl, ts)
        trades.append(
            PortfolioTrade(symbol, lot.layer, lot.entry_ts, ts, cause, float(lot.qty), float(pnl))
        )
        return True

    def point(ts, marks):
        pnl = dict(realized)
        for symbol, lot in lots.items():
            pnl[lot.layer] += lot.qty * marks[symbol] - lot.cost
        return (
            ts,
            float(cash + sum((lot.qty * marks[s] for s, lot in lots.items()), ZERO)),
            float(pnl[Layer.TREND]),
            float(pnl[Layer.PULLBACK]),
            len(lots),
        )

    for i in range(start, end):
        ts = timeline[i]
        rows = {s: data[s][i] for s in symbols}
        marks = {s: D(str(row.open)) for s, row in rows.items()}
        f = {s: features[s][i - 1] for s in symbols}
        if any(feature.ts != timeline[i - 1] for feature in f.values()):
            raise ValueError("Signal must belong to the immediately preceding closed candle")
        held_at_decision = set(lots)
        had_exposure = bool(lots)
        observation(marks, ts)
        attempted_exits = set()
        for s, lot in sorted(lots.items()):
            reason = (
                "gap through stop"
                if marks[s] <= lot.stop
                else pending_exits.get(s) or model.exit(lot, f[s], ts)
            )
            if reason:
                attempted_exits.add(s)
                close(s, marks[s], ts, i, reason)
        observation(marks, ts)
        if reason := state.blocks(limits, ts):
            blocked[reason] += 1
        past_returns = {
            s: returns[s][max(0, i - 1 - limits.correlation_days) : i - 1] for s in symbols
        }
        for entry in model.entries(f, held_at_decision):
            s = entry.symbol
            book = historical_book(marks[s], data[s][i - 1].volume, ts, limits)
            limit = limit_price(book, Side.BUY, rules[s], slip)
            qty = quantity(
                limits,
                state,
                ts,
                entry,
                lots,
                marks,
                cash,
                capital,
                limit,
                rules[s],
                fee,
                slip,
                past_returns,
            )
            if not qty or entry.distance >= book.ask * (1 + slip):
                rejected["entry risk/minimum"] += 1
                continue
            quote = executable_quote(book, Side.BUY, qty, limit, slip, rules[s].min_quote)
            if quote is None:
                rejected["entry modeled depth"] += 1
                continue
            cost = quote * (1 + fee)
            lots[s] = Lot(s, entry.layer, qty, cost, quote / qty - entry.distance, ts)
            cash -= cost
            had_exposure = True
            observation(marks, ts)
        for s, lot in sorted(lots.items()):
            if s not in attempted_exits and D(str(rows[s].low)) <= lot.stop:
                # Time has only daily resolution; bar-end seconds are a bookkeeping convention.
                close(s, min(marks[s], lot.stop), ts + DAY - 1, i, "intrabar stop")
        close_marks = {s: D(str(row.close)) for s, row in rows.items()}
        observation(close_marks, ts + DAY - 1)
        for s, lot in list(lots.items()):
            # Activated only AFTER this candle's low was evaluated. Never loosens or backdates.
            lots[s] = replace(lot, stop=model.next_stop(lot, features[s][i]))
        exposed.append(had_exposure)
        points.append(point(ts + DAY, close_marks))
    # Terminal liquidation uses the same liquidity model. Rejections leave disclosed marked positions.
    for s in sorted(lots):
        close(s, close_marks[s], timeline[end - 1] + DAY, end - 1, "sample end")
    points[-1] = point(timeline[end - 1] + DAY, close_marks)
    curve = pd.DataFrame(
        points, columns=["timestamp", "equity", "trend_pnl", "pullback_pnl", "positions"]
    )
    stats = statistics(curve, trades, exposed)
    stats["unliquidated_at_end"] = list(lots)
    stats["halt_latched"] = state.halted
    stats["by_asset"] = {s: stats["by_asset"].get(s, 0) for s in symbols}
    for layer in Layer:
        stats["by_layer"].setdefault(str(layer), {"trades": 0, "win_rate": None})
    return Simulation(curve, trades, stats, rejected, blocked)


def buy_hold(data, which, start, end, fee, slip, capital, limits):
    first = data[which[0]][start].ts
    half = limits.historical_half_spread
    qty = {
        s: capital
        / len(which)
        / (D(str(data[s][start].open)) * (1 + half) * (1 + slip) * (1 + fee))
        for s in which
    }
    points = [(first, float(capital))]
    for i in range(start, end):
        value = sum(q * D(str(data[s][i].close)) for s, q in qty.items())
        if i == end - 1:
            value *= (1 - half) * (1 - slip) * (1 - fee)
        points.append((data[which[0]][i].ts + DAY, float(value)))
    curve = pd.DataFrame(points, columns=["timestamp", "equity"])
    return curve, statistics(curve, [], [True] * (end - start))


def trade_records(simulation):
    return [asdict(t) for t in simulation.trades]
