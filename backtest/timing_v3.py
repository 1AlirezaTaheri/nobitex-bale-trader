"""Event-driven, price-only research simulator for the frozen Timing V3 protocol."""

import argparse
import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal as D
from hashlib import sha256
from math import ceil, sqrt
from pathlib import Path

import numpy as np

from app.config import ROOT, ConfigError, load
from app.universe import utc
from backtest.portfolio_run import legacy_comparator
from data.history import read_csv
from exchange.base import Candle, Rules
from strategy.timing import EMA_LENGTHS, Candidate, prepare, targets_for

DAY = 86400
CAPITAL = 100.0
SYMBOLS = ("BTC/USDT", "ETH/USDT")


@dataclass(frozen=True)
class Fill:
    ts: int
    symbol: str
    side: str
    quantity: float
    reference: float
    execution: float
    fee: float
    cost: float
    reason: str


@dataclass
class Run:
    rows: list[dict]
    fills: list[Fill]
    stats: dict
    segments: list[dict]
    accepted_targets: list[dict[str, float]]


def aligned_segments(data: dict[str, list]):
    lookup = {symbol: {row.ts: row for row in values} for symbol, values in data.items()}
    shared = sorted(set.intersection(*(set(rows) for rows in lookup.values())))
    result, current = [], []
    for ts in shared:
        if current and ts - current[-1] != DAY:
            if current:
                result.append({s: [lookup[s][x] for x in current] for s in data})
            current = []
        current.append(ts)
    if current:
        result.append({s: [lookup[s][x] for x in current] for s in data})
    return result


def evaluate_segments(segments, holdout_start=None, min_warmup=300):
    items, total = [], 0
    for number, data in enumerate(segments):
        timeline = tuple(row.ts for row in data["BTC/USDT"])
        if len(timeline) <= min_warmup:
            continue
        if any(tuple(row.ts for row in data[s]) != timeline for s in data):
            raise ValueError("BTC/ETH common segment alignment mismatch")
        start = min_warmup
        if holdout_start is not None:
            start = max(
                start,
                next((i for i, ts in enumerate(timeline) if ts >= holdout_start), len(timeline)),
            )
        if start >= len(timeline):
            continue
        features = {s: prepare(rows, lengths=ALL_EMA_PERIODS) for s, rows in data.items()}
        items.append({"number": number, "data": data, "features": features, "start": start})
        total += len(timeline) - start
    return items, total


def period(length, factor):
    return int(length * factor + 0.5)


ALL_EMA_PERIODS = tuple(
    sorted(
        {
            *(
                period(length, factor)
                for length in EMA_LENGTHS
                for factor in (0.8, 0.9, 1, 1.1, 1.2)
            ),
            200,
        }
    )
)


def _metrics(daily, starting, fills, round_trips, average_exposure, exposure_days, regimes):
    returns = np.asarray([item["return"] for item in daily], dtype=float)
    equity = np.asarray([item["equity"] for item in daily], dtype=float)
    if not len(equity):
        raise ValueError("No evaluated daily observations")
    peak = np.maximum.accumulate(np.r_[starting, equity])[1:]
    dd = equity / peak - 1
    total_return = float(equity[-1] / starting - 1)
    years = len(equity) / 365
    cagr = float((equity[-1] / starting) ** (1 / years) - 1) if equity[-1] > 0 and years else None
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    downside = float(np.sqrt(np.mean(np.minimum(returns, 0) ** 2))) if len(returns) else 0.0
    maxdd = float(dd.min())
    calmar = cagr / -maxdd if cagr is not None and maxdd < 0 else None
    sharpe = float(np.mean(returns) / std * sqrt(365)) if std > 0 else None
    sortino = float(np.mean(returns) / downside * sqrt(365)) if downside > 0 else None
    longest, current = 0, 0
    for value in dd:
        current = current + 1 if value < -1e-12 else 0
        longest = max(longest, current)
    rolling = []
    segment_ids = [item["segment"] for item in daily]
    cursor = 0
    while cursor < len(returns):
        end = cursor + 1
        while end < len(returns) and segment_ids[end] == segment_ids[cursor]:
            end += 1
        local = returns[cursor:end]
        rolling.extend(
            float(np.prod(1 + local[i - 364 : i + 1]) - 1) for i in range(364, len(local))
        )
        cursor = end
    gross_pnl = (float(equity[-1]) - starting) + sum(fill.cost for fill in fills)
    total_cost = sum(fill.cost for fill in fills)
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": maxdd,
        "calmar": calmar,
        "sharpe": sharpe,
        "sortino": sortino,
        "worst_12m_return": min(rolling) if rolling else None,
        "longest_drawdown_days": longest,
        "time_invested": exposure_days / len(daily),
        "average_exposure": average_exposure / len(daily),
        "round_trips": round_trips,
        "trade_legs": len(fills),
        "turnover": sum(fill.quantity * fill.reference for fill in fills)
        / (sum(x["equity"] for x in daily) / len(daily)),
        "total_costs": total_cost,
        "gross_profit": gross_pnl,
        "fees_paid": sum(fill.fee for fill in fills),
        "slippage_paid": total_cost - sum(fill.fee for fill in fills),
        "daily_observations": len(daily),
        "regimes": regimes,
    }


def simulate(
    items,
    candidate,
    fee,
    slippage,
    *,
    capital=CAPITAL,
    override=None,
    force_initial=True,
    target_paths=None,
    open_to_next_open=False,
):
    """Use signal at close t, transact at t+1 open; gap segments begin independently in cash."""
    fee, slippage = float(fee), float(slippage)
    candidate = Candidate(candidate)
    params = {
        "hysteresis": 0.02,
        "vol_target": 0.40,
        "threshold": 0.25,
        "lengths": EMA_LENGTHS,
        **(override or {}),
    }
    symbols = ("BTC/USDT", "ETH/USDT") if candidate == Candidate.D else ("BTC/USDT",)
    daily, fills, segment_reports, all_targets = [], [], [], []
    equity = float(capital)
    trips, exposure_sum, exposure_days = 0, 0.0, 0
    regime_rows: dict[str, dict] = {
        "up": {"days": 0, "invested_days": 0, "pnl": 0.0},
        "down": {"days": 0, "invested_days": 0, "pnl": 0.0},
    }

    for item in items:
        rows = item["data"]
        features = item["features"]
        start = item["start"]
        raw = None
        if target_paths is None:
            raw = targets_for(
                features,
                candidate,
                hysteresis=params["hysteresis"],
                vol_target=params["vol_target"],
                threshold=params["threshold"],
                lengths=params["lengths"],
                start_index=start - 1,
            )
            all_targets.extend(raw[start - 1 : -1])
        else:
            segment_targets = target_paths[item["number"]]
            if len(segment_targets) != len(rows["BTC/USDT"]) - start:
                raise ValueError("Cyclic target path length does not match evaluation segment")
            all_targets.extend(segment_targets)
        holdings, cash = {s: 0.0 for s in symbols}, equity
        opened = {s: False for s in symbols}
        segment_start = equity
        segment_daily_start, segment_fill_start, segment_trips_start = len(daily), len(fills), trips
        prev_close_equity = equity

        def transact(index, weights, ts, reason):
            nonlocal cash, trips
            prices = {s: rows[s][index].open for s in symbols}
            pretrade_equity = cash + sum(holdings[s] * prices[s] for s in symbols)
            desired = {
                s: max(0.0, weights.get(s, 0.0)) * pretrade_equity / prices[s] for s in symbols
            }
            # Sell reductions first so an ETH buy can use BTC reduction proceeds on the same open.
            for symbol in symbols:
                reduction = max(0.0, holdings[symbol] - desired[symbol])
                if reduction <= 1e-14:
                    continue
                reference = prices[symbol]
                execution = reference * (1 - slippage)
                proceeds = reduction * execution
                fee_paid = proceeds * fee
                cost = reduction * reference - proceeds + fee_paid
                cash += proceeds - fee_paid
                holdings[symbol] -= reduction
                fills.append(
                    Fill(
                        ts, symbol, "sell", reduction, reference, execution, fee_paid, cost, reason
                    )
                )
                if holdings[symbol] <= 1e-12 and opened[symbol]:
                    holdings[symbol] = 0.0
                    opened[symbol] = False
                    trips += 1
            increases = {}
            cash_per_unit = {}
            for symbol in symbols:
                increase = max(0.0, desired[symbol] - holdings[symbol])
                if increase > 1e-14:
                    increases[symbol] = increase
                    cash_per_unit[symbol] = prices[symbol] * (1 + slippage) * (1 + fee)
            requested_cash = sum(increases[s] * cash_per_unit[s] for s in increases)
            scale = min(1.0, cash / requested_cash) if requested_cash else 1.0
            for symbol, increase in increases.items():
                quantity = increase * scale
                if quantity <= 1e-14:
                    continue
                reference = prices[symbol]
                execution = reference * (1 + slippage)
                notional = quantity * execution
                fee_paid = notional * fee
                cost = notional - quantity * reference + fee_paid
                cash -= notional + fee_paid
                holdings[symbol] += quantity
                opened[symbol] = True
                fills.append(
                    Fill(ts, symbol, "buy", quantity, reference, execution, fee_paid, cost, reason)
                )

        for i in range(start, len(rows["BTC/USDT"])):
            signal_index = i - 1
            signal_ts = rows["BTC/USDT"][signal_index].ts
            execution_ts = rows["BTC/USDT"][i].ts
            pre_open_equity = cash + sum(holdings[s] * rows[s][i].open for s in symbols)
            if target_paths is None:
                weights = raw[signal_index]
                previous_target = raw[signal_index - 1]
            else:
                weights = segment_targets[i - start]
                previous_target = segment_targets[i - start - 1] if i > start else None
            is_new = i == start or weights != previous_target
            if is_new or (force_initial and i == start):
                transact(
                    i,
                    weights,
                    execution_ts,
                    "initial target" if i == start else "accepted signal target",
                )
            open_equity = cash + sum(holdings[s] * rows[s][i].open for s in symbols)
            exposure_open = sum(holdings[s] * rows[s][i].open for s in symbols) / max(
                open_equity, 1e-15
            )
            post_open_weights = {s: holdings[s] * rows[s][i].open / open_equity for s in symbols}
            open_cost_fraction = 1 - open_equity / pre_open_equity
            final_bar = i == len(rows["BTC/USDT"]) - 1
            mark_prices = (
                {s: rows[s][i + 1].open for s in symbols}
                if open_to_next_open and not final_bar
                else {s: rows[s][i].close for s in symbols}
            )
            close_equity = cash + sum(holdings[s] * mark_prices[s] for s in symbols)
            terminal_cost_fraction = 0.0
            if final_bar:
                before_liquidation = close_equity
                # Explicit terminal close liquidation; costs belong to the final evaluated return.
                prices = {s: rows[s][i].close for s in symbols}
                for symbol in symbols:
                    quantity = holdings[symbol]
                    if quantity <= 1e-14:
                        continue
                    reference = prices[symbol]
                    execution = reference * (1 - slippage)
                    proceeds = quantity * execution
                    fee_paid = proceeds * fee
                    cost = quantity * reference - proceeds + fee_paid
                    cash += proceeds - fee_paid
                    fills.append(
                        Fill(
                            execution_ts + DAY,
                            symbol,
                            "sell",
                            quantity,
                            reference,
                            execution,
                            fee_paid,
                            cost,
                            "segment-end liquidation",
                        )
                    )
                    if opened[symbol]:
                        trips += 1
                    holdings[symbol] = 0.0
                    opened[symbol] = False
                close_equity = cash
                terminal_cost_fraction = 1 - cash / before_liquidation
            daily_return = close_equity / prev_close_equity - 1 if prev_close_equity else 0.0
            current_regime = "up" if features["BTC/USDT"].votes[200][signal_index] else "down"
            invested = exposure_open > 1e-14
            pnl = close_equity - prev_close_equity
            regime_rows[current_regime]["days"] += 1
            regime_rows[current_regime]["invested_days"] += int(invested)
            regime_rows[current_regime]["pnl"] += pnl
            daily.append(
                {
                    "timestamp": execution_ts,
                    "close_timestamp": execution_ts + DAY,
                    "equity": close_equity,
                    "return": daily_return,
                    "pnl": pnl,
                    "exposure": exposure_open,
                    "invested": invested,
                    "regime": current_regime,
                    "segment": item["number"],
                    "signal_timestamp": signal_ts,
                }
            )
            daily[-1].update(
                post_open_weights=post_open_weights,
                open_cost_fraction=open_cost_fraction,
                terminal_cost_fraction=terminal_cost_fraction,
            )
            exposure_sum += exposure_open
            exposure_days += int(invested)
            prev_close_equity = close_equity
        equity = cash
        segment_rows = daily[segment_daily_start:]
        segment_fills = fills[segment_fill_start:]
        segment_stats = _metrics(
            segment_rows,
            segment_start,
            segment_fills,
            trips - segment_trips_start,
            sum(row["exposure"] for row in segment_rows),
            sum(row["invested"] for row in segment_rows),
            {},
        )
        segment_reports.append(
            {
                "segment": item["number"],
                "first": segment_rows[0]["timestamp"],
                "last": segment_rows[-1]["timestamp"],
                "observations": len(segment_rows),
                "return": equity / segment_start - 1,
                "trades": len(segment_fills),
                "round_trips": trips - segment_trips_start,
                "metrics": segment_stats,
            }
        )

    stats = _metrics(daily, capital, fills, trips, exposure_sum, exposure_days, regime_rows)
    stats["segments"] = len(segment_reports)
    return Run(daily, fills, stats, segment_reports, all_targets)


def matched_exposure(items, candidate, fee, slippage, exposure, *, holdout=False):
    candidate = Candidate(candidate)
    symbols = ("BTC/USDT", "ETH/USDT") if candidate == Candidate.D else ("BTC/USDT",)
    low, high = 0.0, 1.0
    best = None
    for _ in range(32):
        weight = (low + high) / 2
        weights = {s: weight / len(symbols) for s in symbols}
        base = simulate_constant(items, symbols, weights, fee, slippage, monthly=True)
        observed = base.stats["average_exposure"]
        best = (weight, base)
        if observed < exposure:
            low = weight
        else:
            high = weight
    residual = best[1].stats["average_exposure"] - exposure
    return best[0], best[1], residual


def simulate_constant(
    items,
    symbols,
    weights,
    fee,
    slippage,
    *,
    monthly=False,
    buy_hold=False,
    open_to_next_open=False,
):
    fee, slippage = float(fee), float(slippage)
    daily, fills, segment_reports = [], [], []
    equity = CAPITAL
    total_exposure = 0.0
    invested_days = trips = 0
    regimes = {
        "up": {"days": 0, "invested_days": 0, "pnl": 0.0},
        "down": {"days": 0, "invested_days": 0, "pnl": 0.0},
    }
    for item in items:
        rows, start = item["data"], item["start"]
        holdings, cash = {s: 0.0 for s in symbols}, equity
        prev_equity, segment_begin = equity, equity
        segment_daily_start, fill_start, trip_start = len(daily), len(fills), trips
        last_month = None
        opened = set()
        for i in range(start, len(rows["BTC/USDT"])):
            ts = rows["BTC/USDT"][i].ts
            month = datetime.fromtimestamp(ts, UTC).strftime("%Y-%m")
            do_rebalance = i == start or (monthly and month != last_month)
            if do_rebalance:
                prices = {s: rows[s][i].open for s in symbols}
                base_equity = cash + sum(holdings[s] * prices[s] for s in symbols)
                desired = {s: weights[s] * base_equity / prices[s] for s in symbols}
                for s in symbols:
                    sale = max(0.0, holdings[s] - desired[s])
                    if sale:
                        ref = prices[s]
                        px = ref * (1 - slippage)
                        proceeds = sale * px
                        f = proceeds * fee
                        cash += proceeds - f
                        holdings[s] -= sale
                        cost = sale * ref - proceeds + f
                        fills.append(
                            Fill(
                                ts,
                                s,
                                "sell",
                                sale,
                                ref,
                                px,
                                f,
                                cost,
                                "monthly rebalance" if monthly else "benchmark rebalance",
                            )
                        )
                        if holdings[s] <= 1e-12 and s in opened:
                            holdings[s] = 0.0
                            opened.remove(s)
                            trips += 1
                increases, per_unit = {}, {}
                for s in symbols:
                    buy = max(0.0, desired[s] - holdings[s])
                    if buy:
                        increases[s] = buy
                        per_unit[s] = prices[s] * (1 + slippage) * (1 + fee)
                total = sum(increases[s] * per_unit[s] for s in increases)
                scale = min(1.0, cash / total) if total else 1.0
                for s, qty in increases.items():
                    qty *= scale
                    if qty:
                        ref = prices[s]
                        px = ref * (1 + slippage)
                        notional = qty * px
                        f = notional * fee
                        cash -= notional + f
                        holdings[s] += qty
                        opened.add(s)
                        fills.append(
                            Fill(
                                ts,
                                s,
                                "buy",
                                qty,
                                ref,
                                px,
                                f,
                                notional - qty * ref + f,
                                "monthly rebalance" if monthly else "benchmark rebalance",
                            )
                        )
                last_month = month
            open_equity = cash + sum(holdings[s] * rows[s][i].open for s in symbols)
            exposure = sum(holdings[s] * rows[s][i].open for s in symbols) / max(open_equity, 1e-15)
            final_bar = i == len(rows["BTC/USDT"]) - 1
            mark_prices = (
                {s: rows[s][i + 1].open for s in symbols}
                if open_to_next_open and not final_bar
                else {s: rows[s][i].close for s in symbols}
            )
            close_equity = cash + sum(holdings[s] * mark_prices[s] for s in symbols)
            if final_bar:
                for s in symbols:
                    qty = holdings[s]
                    if qty <= 0:
                        continue
                    ref = rows[s][i].close
                    px = ref * (1 - slippage)
                    proceeds = qty * px
                    f = proceeds * fee
                    cash += proceeds - f
                    fills.append(
                        Fill(
                            ts + DAY,
                            s,
                            "sell",
                            qty,
                            ref,
                            px,
                            f,
                            qty * ref - proceeds + f,
                            "segment-end liquidation",
                        )
                    )
                    if s in opened:
                        trips += 1
                    holdings[s] = 0.0
                close_equity = cash
            ret = close_equity / prev_equity - 1 if prev_equity else 0
            regime = "up" if item["features"]["BTC/USDT"].votes[200][i - 1] else "down"
            invested = exposure > 1e-14
            regimes[regime]["days"] += 1
            regimes[regime]["invested_days"] += int(invested)
            regimes[regime]["pnl"] += close_equity - prev_equity
            daily.append(
                {
                    "timestamp": ts,
                    "close_timestamp": ts + DAY,
                    "equity": close_equity,
                    "return": ret,
                    "pnl": close_equity - prev_equity,
                    "exposure": exposure,
                    "invested": invested,
                    "regime": regime,
                    "segment": item["number"],
                    "signal_timestamp": rows["BTC/USDT"][i - 1].ts,
                }
            )
            total_exposure += exposure
            invested_days += int(invested)
            prev_equity = close_equity
        equity = cash
        sr = daily[segment_daily_start:]
        segment_stats = _metrics(
            sr,
            segment_begin,
            fills[fill_start:],
            trips - trip_start,
            sum(row["exposure"] for row in sr),
            sum(row["invested"] for row in sr),
            {},
        )
        segment_reports.append(
            {
                "segment": item["number"],
                "first": sr[0]["timestamp"],
                "last": sr[-1]["timestamp"],
                "observations": len(sr),
                "return": equity / segment_begin - 1,
                "trades": len(fills) - fill_start,
                "round_trips": trips - trip_start,
                "metrics": segment_stats,
            }
        )
    stats = _metrics(daily, CAPITAL, fills, trips, total_exposure, invested_days, regimes)
    stats["segments"] = len(segment_reports)
    return Run(daily, fills, stats, segment_reports, [])


def buy_hold(items, symbols, fee, slippage):
    weights = {s: 1 / len(symbols) for s in symbols}
    return simulate_constant(items, symbols, weights, fee, slippage)


def matched(items, symbols, exposure, fee, slippage):
    desired = {s: exposure / len(symbols) for s in symbols}
    return simulate_constant(items, symbols, desired, fee, slippage, monthly=True)


def holdout_items(full_items, fraction=0.25):
    total = sum(len(item["data"]["BTC/USDT"]) - item["start"] for item in full_items)
    holdout_count = ceil(total * fraction)
    cutoff_count = total - holdout_count
    seen, output = 0, []
    for item in full_items:
        n = len(item["data"]["BTC/USDT"]) - item["start"]
        if seen + n > cutoff_count:
            take = item["start"] + max(0, cutoff_count - seen)
            output.append({**item, "start": take})
        seen += n
    return output


def phase_report(run):
    rows = run.rows
    phases = []
    cursor = 0
    while cursor < len(rows):
        end = cursor + 1
        while (
            end < len(rows)
            and rows[end]["segment"] == rows[cursor]["segment"]
            and rows[end]["regime"] == rows[cursor]["regime"]
        ):
            end += 1
        group = rows[cursor:end]
        returns = np.asarray([x["return"] for x in group])
        curve = np.cumprod(1 + returns)
        dd = curve / np.maximum.accumulate(np.r_[1.0, curve])[1:] - 1
        phases.append(
            {
                "segment": group[0]["segment"],
                "direction": group[0]["regime"],
                "start": group[0]["timestamp"],
                "end": group[-1]["timestamp"],
                "days": len(group),
                "return": float(curve[-1] - 1),
                "max_drawdown": float(dd.min()),
                "average_exposure": float(np.mean([x["exposure"] for x in group])),
                "time_invested": float(np.mean([x["invested"] for x in group])),
            }
        )
        cursor = end
    major = [phase for phase in phases if phase["days"] >= 90]
    grouped = {}
    for direction in ("up", "down"):
        subset = [row for row in rows if row["regime"] == direction]
        grouped[direction] = {
            "days": len(subset),
            "net_pnl": float(sum(x["pnl"] for x in subset)) if subset else None,
            "pnl_on_initial_capital": float(sum(x["pnl"] for x in subset) / CAPITAL)
            if subset
            else None,
            "mean_daily_return": float(np.mean([x["return"] for x in subset])) if subset else None,
            "average_exposure": float(np.mean([x["exposure"] for x in subset])) if subset else None,
            "time_invested": float(np.mean([x["invested"] for x in subset])) if subset else None,
        }
    last_ts = rows[-1]["close_timestamp"] if rows else None
    recent = [row for row in rows if row["close_timestamp"] > last_ts - 365 * DAY] if rows else []
    episodes = 0
    previous = None
    for row in rows:
        key = (row["segment"], row["invested"])
        if row["invested"] and key != previous:
            episodes += 1
        previous = key
    last_12m = {
        "days": len(recent),
        "start": recent[0]["timestamp"] if recent else None,
        "end": last_ts,
        "return": float(np.prod([1 + x["return"] for x in recent]) - 1) if recent else None,
        "average_exposure": float(np.mean([x["exposure"] for x in recent])) if recent else None,
        "time_invested": float(np.mean([x["invested"] for x in recent])) if recent else None,
    }
    return {
        "by_vote": grouped,
        "all_phases": phases,
        "major_phases_90d_plus": major,
        "major_phase_count": len(major),
        "candidate_invested_episodes": episodes,
        "last_12_calendar_months": last_12m,
    }


def timing_null(items, candidate, actual, fee, slippage, *, trials=999, seed=20261120):
    """Shift observed post-fill weights and proportional opening drag, never re-execute targets."""
    rng = np.random.default_rng(seed)
    exceed_return = exceed_calmar = 0
    symbols = ("BTC/USDT", "ETH/USDT") if Candidate(candidate) == Candidate.D else ("BTC/USDT",)
    blocks = []
    for item in items:
        observed = [row for row in actual.rows if row["segment"] == item["number"]]
        risky_returns = np.asarray(
            [
                [
                    (
                        item["data"][s][i + 1].open
                        if i + 1 < len(item["data"][s])
                        else item["data"][s][i].close
                    )
                    / item["data"][s][i].open
                    - 1
                    for s in symbols
                ]
                for i in range(item["start"], len(item["data"]["BTC/USDT"]))
            ]
        )
        blocks.append(
            (
                observed,
                risky_returns,
                np.asarray([[row["post_open_weights"][s] for s in symbols] for row in observed]),
                np.asarray([row["open_cost_fraction"] for row in observed]),
            )
        )

    def reconstruction(shifts):
        daily, equity = [], CAPITAL
        for (observed, risky_returns, weights, drag), shift in zip(blocks, shifts, strict=True):
            moved_weights, moved_drag = np.roll(weights, shift, axis=0), np.roll(drag, shift)
            factors = (1 - moved_drag) * (1 + np.sum(moved_weights * risky_returns, axis=1))
            factors[-1] *= 1 - observed[-1]["terminal_cost_fraction"]
            for row, factor, weight in zip(observed, factors, moved_weights, strict=True):
                equity *= float(factor)
                daily.append(
                    {
                        **row,
                        "return": float(factor - 1),
                        "equity": equity,
                        "exposure": float(weight.sum()),
                        "invested": bool(weight.sum() > 1e-14),
                    }
                )
        return _metrics(
            daily,
            CAPITAL,
            [],
            0,
            sum(x["exposure"] for x in daily),
            sum(x["invested"] for x in daily),
            {},
        )

    reconstructed = reconstruction([0] * len(blocks))
    for _ in range(trials):
        randomized = reconstruction([int(rng.integers(0, len(block[0]))) for block in blocks])
        ret = randomized["total_return"]
        calmar = randomized["calmar"]
        exceed_return += int(ret >= actual.stats["total_return"])
        exceed_calmar += int(
            calmar is not None
            and actual.stats["calmar"] is not None
            and calmar >= actual.stats["calmar"]
        )
    return {
        "trials": trials,
        "seed": seed,
        "share_net_return_ge_actual": exceed_return / trials if trials else None,
        "share_calmar_ge_actual": exceed_calmar / trials if trials else None,
        "unshifted_reconstruction": reconstructed,
        "reconstruction_return_error": reconstructed["total_return"] - actual.stats["total_return"],
        "close_to_close_backtest_reference": actual.stats,
        "interpretation": "Joint cyclic shifts of observed post-open weights and opening cost drag; terminal liquidation drag fixed. Shifted open-return net returns and Calmar are compared to the actual strategy's reported net return and Calmar. The unshifted reconstruction error is separately disclosed; this is not an executable strategy or significance test.",
    }


def split_contiguous(rows, seconds):
    segments, current = [], []
    for row in rows:
        if current and row.ts - current[-1].ts != seconds:
            segments.append(current)
            current = []
        current.append(row)
    if current:
        segments.append(current)
    return segments


def _write_candles(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
        writer.writerows((r.ts, r.open, r.high, r.low, r.close, r.volume) for r in rows)


def load_data(snapshot, now):
    labels = {"BTC/USDT": "BTC-USDT.csv", "ETH/USDT": "ETH-USDT.csv"}
    legacy_name = "BTC-USDT-4h.csv"
    if snapshot:
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        rows = {}
        for symbol, name in labels.items():
            path = snapshot / name
            info = manifest["files"][symbol]
            if sha256(path.read_bytes()).hexdigest() != info["sha256"]:
                raise ValueError(f"Snapshot checksum mismatch for {symbol}")
            rows[symbol] = read_csv(path, DAY, now)
            if len(rows[symbol]) != info["rows"]:
                raise ValueError(f"Snapshot row-count mismatch for {symbol}")
        legacy_path = snapshot / legacy_name
        legacy_info = manifest["files"]["BTC/USDT_4h"]
        if sha256(legacy_path.read_bytes()).hexdigest() != legacy_info["sha256"]:
            raise ValueError("Snapshot checksum mismatch for legacy BTC/USDT 4h")
        legacy = read_csv(legacy_path, 14400, now) if legacy_info["rows"] else []
        if len(legacy) != legacy_info["rows"]:
            raise ValueError("Snapshot legacy row-count mismatch")
        fee_path = snapshot / "fee_observation.json"
        if sha256(fee_path.read_bytes()).hexdigest() != manifest["fee_observation_sha256"]:
            raise ValueError("Snapshot checksum mismatch for public fee schedule")
        fee_observation = json.loads(fee_path.read_text(encoding="utf-8"))
        source = manifest.get("source", "verified immutable V3 snapshot")
        return rows, legacy, fee_observation, source
    with sqlite3.connect((ROOT / "data/candles.db").as_uri() + "?mode=ro", uri=True) as store:
        rows = {
            symbol: [
                Candle(*row)
                for row in store.execute(
                    "SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND frame='1d' AND ts+?<=? ORDER BY ts",
                    (symbol, DAY, now),
                )
            ]
            for symbol in labels
        }
        legacy = [
            Candle(*row)
            for row in store.execute(
                "SELECT ts,o,h,l,c,v FROM candles WHERE symbol='BTC/USDT' AND frame='4h' AND ts+14400<=? ORDER BY ts",
                (now,),
            )
        ]
    fee_observation = {
        "endpoint": "https://apiv2.nobitex.ir/v2/options",
        "observed_date_utc": "2026-11-20",
        "method": "public GET response; no credentials",
        "taker_fees_tether_percent": ["0.13", "0.12", "0.11", "0.1", "0.1", "0.095", "0.09"],
        "maximum_fee": "0.0013",
    }
    return rows, legacy, fee_observation, "local cached public Nobitex candles"


def save_inputs(folder, rows, legacy, fee_observation, source):
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"Refusing to overwrite an existing input snapshot: {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for symbol, values in (*rows.items(), ("BTC/USDT_4h", legacy)):
        name = symbol.replace("/", "-").replace("_4h", "-4h") + ".csv"
        path = folder / name
        _write_candles(path, values)
        files[symbol] = {
            "file": name,
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "rows": len(values),
            "first_timestamp": values[0].ts if values else None,
            "last_timestamp": values[-1].ts if values else None,
        }
    fee_path = folder / "fee_observation.json"
    fee_path.write_text(json.dumps(fee_observation, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "files": files,
        "fee_observation_sha256": sha256(fee_path.read_bytes()).hexdigest(),
        "source": source,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def preregistration_hash():
    manifest_path = ROOT / "reports/v3_preregistration_manifest.json"
    record = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    path = ROOT / record["file"]
    actual = sha256(path.read_bytes()).hexdigest()
    if actual != record["sha256"]:
        raise ValueError("Frozen V3 preregistration checksum mismatch; research run blocked")
    return actual


def metric_row(name, run, *, kind="strategy", exposure_match=None):
    return {
        "name": name,
        "kind": kind,
        **{key: value for key, value in run.stats.items() if key != "regimes"},
        "matched_weight": exposure_match,
    }


def _variant_grid(candidate):
    candidate = Candidate(candidate)
    base_lengths = (200,) if candidate == Candidate.A else EMA_LENGTHS
    base = {"lengths": base_lengths, "hysteresis": 0.02, "vol_target": 0.40, "threshold": 0.25}
    applicable = ["lengths", "hysteresis"]
    if candidate in {Candidate.C, Candidate.D}:
        applicable.append("vol_target")
    if candidate != Candidate.A:
        applicable.append("threshold")
    robust = []
    for key in applicable:
        if key == "lengths":
            for index, value in enumerate(base_lengths):
                for factor in (0.8, 1.2):
                    changed = list(base_lengths)
                    changed[index] = period(value, factor)
                    robust.append(
                        {**base, "lengths": tuple(changed), "variation": f"EMA{value} x {factor}"}
                    )
        else:
            initial = base[key]
            for factor in (0.8, 1.2):
                robust.append({**base, key: initial * factor, "variation": f"{key} x {factor}"})

    grid = []
    for index, value in enumerate(base_lengths):
        for factor in (0.9, 1.1):
            changed = list(base_lengths)
            changed[index] = period(value, factor)
            grid.append(
                {**base, "lengths": tuple(changed), "variation": f"single EMA{value} x {factor}"}
            )
    for factor in (0.8, 0.9, 1.1, 1.2):
        grid.append(
            {
                **base,
                "lengths": tuple(period(x, factor) for x in base_lengths),
                "variation": f"all EMA x {factor}",
            }
        )
    for band in (0.0, 0.01, 0.03, 0.04):
        grid.append({**base, "hysteresis": band, "variation": f"hysteresis {band:.0%}"})
    if candidate in {Candidate.C, Candidate.D}:
        for target in (0.30, 0.35, 0.45, 0.50):
            grid.append({**base, "vol_target": target, "variation": f"vol target {target:.0%}"})
    if candidate != Candidate.A:
        for threshold in (0.10, 0.15, 0.20, 0.30, 0.35, 0.40):
            grid.append({**base, "threshold": threshold, "variation": f"threshold {threshold:.0%}"})
    return base, robust, _unique_variants(grid)


def _unique_variants(variants):
    result, seen = [], set()
    for item in variants:
        key = (item["lengths"], item["hysteresis"], item["vol_target"], item["threshold"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def assess_candidate(candidate, items, holdout, base_fee, slippage, buyhold):
    name = Candidate(candidate).value
    full = simulate(items, candidate, base_fee, slippage)
    held = simulate(holdout, candidate, base_fee, slippage)
    matched_weight, matched_run, full_residual = matched_exposure(
        items, candidate, base_fee, slippage, full.stats["average_exposure"]
    )
    held_weight, matched_holdout, held_residual = matched_exposure(
        holdout, candidate, base_fee, slippage, held.stats["average_exposure"]
    )
    matched_segments = []
    for item in items:
        one_segment = [item]
        strategy_segment = simulate(one_segment, candidate, base_fee, slippage)
        weight, baseline, residual = matched_exposure(
            one_segment,
            candidate,
            base_fee,
            slippage,
            strategy_segment.stats["average_exposure"],
        )
        matched_segments.append(
            {
                "segment": item["number"],
                "candidate": strategy_segment.stats,
                "matched_weight": weight,
                "matched_exposure": baseline.stats,
                "matched_residual": residual,
            }
        )
    stress2 = simulate(items, candidate, 2 * base_fee, 2 * slippage)
    stress3 = simulate(items, candidate, 3 * base_fee, 3 * slippage)
    _, robust_variants, plateau_variants = _variant_grid(candidate)
    robust_rows = []
    for variant in robust_variants:
        x = simulate(items, candidate, base_fee, slippage, override=variant)
        robust_rows.append(
            {
                "candidate": name,
                "variation": variant["variation"],
                "net_return": x.stats["total_return"],
                "max_drawdown": x.stats["max_drawdown"],
                "passes_criterion_5": x.stats["total_return"] > 0
                and abs(x.stats["max_drawdown"]) <= 0.75 * abs(buyhold.stats["max_drawdown"]),
            }
        )
    plateau_rows = []
    for variant in plateau_variants:
        x = simulate(items, candidate, base_fee, slippage, override=variant)
        plateau_rows.append(
            {
                "candidate": name,
                "variation": variant["variation"],
                "parameters": {k: v for k, v in variant.items() if k != "variation"},
                "net_return": x.stats["total_return"],
                "max_drawdown": x.stats["max_drawdown"],
                "plateau_case_pass": x.stats["total_return"] > 0
                and abs(x.stats["max_drawdown"]) <= 0.75 * abs(buyhold.stats["max_drawdown"]),
            }
        )
    plateau_fraction = (
        sum(row["plateau_case_pass"] for row in plateau_rows) / len(plateau_rows)
        if plateau_rows
        else 0.0
    )
    robust_pass = bool(robust_rows) and all(row["passes_criterion_5"] for row in robust_rows)
    checks = {
        "1_positive_net_return_after_2x_costs": stress2.stats["total_return"] > 0,
        "2_drawdown_le_60pct_buy_hold": abs(full.stats["max_drawdown"])
        <= 0.60 * abs(buyhold.stats["max_drawdown"]),
        "3_calmar_and_sharpe_better_than_matched": full.stats["calmar"] is not None
        and matched_run.stats["calmar"] is not None
        and full.stats["sharpe"] is not None
        and matched_run.stats["sharpe"] is not None
        and full.stats["calmar"] > matched_run.stats["calmar"]
        and full.stats["sharpe"] > matched_run.stats["sharpe"],
        "4_holdout_return_and_drawdown_vs_matched": held.stats["total_return"] >= 0
        and abs(held.stats["max_drawdown"]) <= abs(matched_holdout.stats["max_drawdown"]),
        "5_single_parameter_20pct_robustness": robust_pass,
        "6_total_costs_le_25pct_gross_profit": full.stats["gross_profit"] > 0
        and full.stats["total_costs"] <= 0.25 * full.stats["gross_profit"],
        "7_worst_12m_better_than_buy_hold": full.stats["worst_12m_return"] is not None
        and buyhold.stats["worst_12m_return"] is not None
        and full.stats["worst_12m_return"] > buyhold.stats["worst_12m_return"],
    }
    plateau_pass = robust_pass and plateau_fraction >= 0.80
    return {
        "candidate": name,
        "full": full,
        "holdout": held,
        "matched": matched_run,
        "matched_weight": matched_weight,
        "matched_residual": full_residual,
        "matched_holdout": matched_holdout,
        "matched_holdout_weight": held_weight,
        "matched_holdout_residual": held_residual,
        "matched_by_segment": matched_segments,
        "stress_2x": stress2,
        "stress_3x": stress3,
        "acceptance": checks,
        "status": "PASS" if all(checks.values()) else "NOT VALIDATED",
        "enabled": False,
        "robustness": robust_rows,
        "plateau": {
            "pass_fraction": plateau_fraction,
            "cases": len(plateau_rows),
            "passes": sum(row["plateau_case_pass"] for row in plateau_rows),
            "assessment": "smooth plateau" if plateau_pass else "fragile / no demonstrated plateau",
            "return_range": [
                min([full.stats["total_return"], *(x["net_return"] for x in plateau_rows)]),
                max([full.stats["total_return"], *(x["net_return"] for x in plateau_rows)]),
            ],
            "drawdown_range": [
                min([full.stats["max_drawdown"], *(x["max_drawdown"] for x in plateau_rows)]),
                max([full.stats["max_drawdown"], *(x["max_drawdown"] for x in plateau_rows)]),
            ],
        },
        "plateau_rows": plateau_rows,
        "random_timing_null": timing_null(items, candidate, full, base_fee, slippage),
        "phases": phase_report(full),
    }


def _legacy_baseline(candles, cfg, risk, rules, items, fee):
    if cfg.timeframe != "4h" or cfg.symbol != "BTC/USDT":
        return [{"status": "unavailable", "reason": "legacy config is not BTC/USDT 4h"}]
    segments = split_contiguous(candles, cfg.seconds)
    result = []
    compounded_capital = CAPITAL
    for item in items:
        daily = item["data"]["BTC/USDT"]
        first_eval = daily[item["start"]].ts
        final_close = daily[-1].ts + DAY
        found = next(
            (
                (j, segment)
                for j, segment in enumerate(segments)
                if segment[0].ts <= first_eval < segment[-1].ts + cfg.seconds
            ),
            None,
        )
        if found is None:
            result.append(
                {
                    "status": "excluded",
                    "segment": item["number"],
                    "reason": "no continuous 4h data at the daily segment's first evaluation open",
                }
            )
            continue
        _, raw_segment = found
        start = next((i for i, row in enumerate(raw_segment) if row.ts == first_eval), None)
        segment = [row for row in raw_segment if row.ts < final_close]
        if start is None or start < cfg.warmup or len(segment) - start < 2:
            result.append(
                {
                    "status": "excluded",
                    "segment": item["number"],
                    "reason": "legacy 4h warmup, exact daily-open alignment, or continuous coverage unavailable",
                }
            )
            continue
        first, last = raw_segment[start].ts, segment[-1].ts + cfg.seconds
        try:
            comparison = legacy_comparator(
                segment,
                cfg,
                risk.model_copy(update={"fee": fee}),
                rules,
                D(str(compounded_capital)),
                first,
                last,
                daily_comparable=True,
            )
            if comparison is None:
                raise ValueError("legacy comparator could not align its warmup/evaluation slice")
            curve, stats = comparison
        except ValueError as error:
            result.append(
                {
                    "status": "excluded",
                    "segment": item["number"],
                    "reason": str(error),
                    "first": first,
                    "last": last,
                }
            )
            continue
        compounded_capital = float(curve.equity.iloc[-1])
        result.append(
            {
                "status": "evaluated",
                "segment": item["number"],
                "start": int(curve.timestamp.iloc[0]),
                "end": int(curve.timestamp.iloc[-1]),
                "observations": len(curve),
                "metrics": stats,
                "costs_note": "Legacy engine uses configured nominal fees/slippage; explicit aggregate costs not exposed by its result schema.",
            }
        )
    return result or [
        {"status": "unavailable", "reason": "no continuous 4h segment overlaps V3 evaluation dates"}
    ]


def _csv_write(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                    for k, v in row.items()
                }
            )


def _coverage(raw, segments, items):
    shared = {row.ts for row in raw["BTC/USDT"]} & {row.ts for row in raw["ETH/USDT"]}
    timestamps = {symbol: {row.ts for row in values} for symbol, values in raw.items()}
    eligible_ids = {item["number"] for item in items}
    all_common = []
    for index, segment in enumerate(segments):
        left = segment["BTC/USDT"]
        all_common.append(
            {
                "segment": index,
                "start": utc(left[0].ts),
                "end": utc(left[-1].ts),
                "count": len(left),
                "eligible_after_300_warmup": index in eligible_ids,
                "eligible_observations": max(0, len(left) - 300),
                "grid_offset_seconds_mod_86400": left[0].ts % DAY,
            }
        )
    return {
        "assets": {
            symbol: {
                "count": len(values),
                "first": utc(values[0].ts) if values else None,
                "last": utc(values[-1].ts) if values else None,
                "zero_volume_rows": sum(row.volume == 0 for row in values),
                "unmatched_timestamps": len({row.ts for row in values} - shared),
            }
            for symbol, values in raw.items()
        },
        "raw_asset_segments": {
            symbol: [
                {
                    "segment": index,
                    "start": utc(rows[0].ts),
                    "end": utc(rows[-1].ts),
                    "count": len(rows),
                    "grid_offset_seconds_mod_86400": rows[0].ts % DAY,
                    "timestamps_on_other_asset_grid": sum(
                        row.ts in timestamps[other] for row in rows
                    ),
                    "contiguous_common_pairs": sum(
                        right.ts - left.ts == DAY
                        for left, right in zip(rows, rows[1:])
                        if left.ts in timestamps[other] and right.ts in timestamps[other]
                    ),
                    "interpretation": (
                        "Fully aligned with counterpart; see common_segments."
                        if all(row.ts in timestamps[other] for row in rows)
                        else "Partial single-asset coverage; unmatched timestamps are excluded from the common calendar."
                    ),
                }
                for index, rows in enumerate(split_contiguous(values, DAY))
                for other in ("ETH/USDT" if symbol == "BTC/USDT" else "BTC/USDT",)
            ]
            for symbol, values in raw.items()
        },
        "common_timestamp_count": len(shared),
        "common_segments": all_common,
        "eligible_segment_count": len(eligible_ids),
        "excluded_segment_count": len(segments) - len(eligible_ids),
        "excluded_reason": "common segments of 300 candles or fewer cannot supply 300 warmup candles plus an execution candle; no gap is bridged",
        "zero_volume_interpretation": "Raw UDF v=0 matched cache on sampled older BTC/ETH rows; parser regression added; strategy is price-only.",
    }


def _jsonable(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def evaluate(args):
    prereg_hash = preregistration_hash()
    settings, legacy_cfg, risk, app = load()
    now = int(datetime.now(UTC).timestamp())
    raw, legacy, fee_observation, source = load_data(args.snapshot, now)
    output = args.output.resolve()
    input_output = output / "inputs"
    if not args.snapshot or args.snapshot.resolve() != input_output.resolve():
        save_inputs(input_output, raw, legacy, fee_observation, source)
    fee = max(risk.fee, D(str(fee_observation["maximum_fee"])))
    slip = risk.slippage
    all_common_segments = aligned_segments(raw)
    items, _ = evaluate_segments(all_common_segments)
    if not items:
        raise ValueError("No BTC/ETH common raw-grid segment has >300 candles")
    total_observations = sum(len(item["data"]["BTC/USDT"]) - item["start"] for item in items)
    holdout = holdout_items(items)
    if not holdout:
        raise ValueError("Could not construct chronological final-quarter holdout")
    eval_first = min(item["data"]["BTC/USDT"][item["start"]].ts for item in items)
    eval_last = max(item["data"]["BTC/USDT"][-1].ts + DAY for item in items)

    full_buyholds = {
        "BTC buy-and-hold": buy_hold(items, ("BTC/USDT",), fee, slip),
        "BTC+ETH equal-weight buy-and-hold": buy_hold(items, ("BTC/USDT", "ETH/USDT"), fee, slip),
    }
    candidates = {}
    for candidate in Candidate:
        bh = (
            full_buyholds["BTC+ETH equal-weight buy-and-hold"]
            if candidate == Candidate.D
            else full_buyholds["BTC buy-and-hold"]
        )
        candidates[candidate.value] = assess_candidate(candidate, items, holdout, fee, slip, bh)

    universe = json.loads((ROOT / "reports/universe.json").read_text(encoding="utf-8"))
    btc_rules = Rules(
        **{key: D(value) for key, value in universe["coverage"]["BTC/USDT"]["rules"].items()}
    )
    legacy_results = _legacy_baseline(legacy, legacy_cfg, risk, btc_rules, items, fee)

    coverage = _coverage(raw, all_common_segments, items)
    metrics_rows = []
    for candidate, record in candidates.items():
        metrics_rows.append(metric_row(candidate, record["full"]))
        metrics_rows.append(metric_row(f"{candidate} 2x costs", record["stress_2x"], kind="stress"))
        metrics_rows.append(metric_row(f"{candidate} 3x costs", record["stress_3x"], kind="stress"))
        metrics_rows.append(
            metric_row(
                f"{candidate} matched exposure",
                record["matched"],
                kind="matched baseline",
                exposure_match=record["matched_weight"],
            )
        )
        metrics_rows.append(metric_row(f"{candidate} holdout", record["holdout"], kind="holdout"))
        metrics_rows.append(
            metric_row(
                f"{candidate} holdout matched",
                record["matched_holdout"],
                kind="holdout baseline",
                exposure_match=record["matched_holdout_weight"],
            )
        )
        for segment in record["matched_by_segment"]:
            metrics_rows.append(
                {
                    "name": f"{candidate} segment {segment['segment']}",
                    "kind": "strategy segment",
                    **segment["candidate"],
                }
            )
            metrics_rows.append(
                {
                    "name": f"{candidate} segment {segment['segment']} matched",
                    "kind": "segment baseline",
                    **segment["matched_exposure"],
                    "matched_weight": segment["matched_weight"],
                    "matched_residual": segment["matched_residual"],
                }
            )
    metrics_rows.extend(
        metric_row(name, run, kind="buy-and-hold") for name, run in full_buyholds.items()
    )
    for row in legacy_results:
        if row["status"] == "evaluated":
            metrics_rows.append(
                {
                    "name": f"Legacy 4h BTC segment {row['segment']}",
                    "kind": "legacy baseline",
                    **row["metrics"],
                }
            )
    _csv_write(output / "metrics.csv", metrics_rows)
    acceptance_rows = [
        {"candidate": name, "criterion": check, "result": "PASS" if passed else "FAIL"}
        for name, record in candidates.items()
        for check, passed in record["acceptance"].items()
    ]
    _csv_write(output / "acceptance.csv", acceptance_rows)
    robustness_rows = [row for record in candidates.values() for row in record["robustness"]]
    robustness_rows += [row for record in candidates.values() for row in record["plateau_rows"]]
    _csv_write(output / "robustness.csv", robustness_rows)
    phase_rows = [
        phase for record in candidates.values() for phase in record["phases"]["all_phases"]
    ]
    _csv_write(output / "regime_phases.csv", phase_rows)
    for name, record in candidates.items():
        _csv_write(output / f"candidate_{name}_daily.csv", record["full"].rows)
        _csv_write(
            output / f"candidate_{name}_fills.csv", [asdict(fill) for fill in record["full"].fills]
        )

    summary = {
        "protocol_sha256": prereg_hash,
        "input_manifest_sha256": sha256((output / "inputs/manifest.json").read_bytes()).hexdigest(),
        "fee_observation": fee_observation,
        "input_source": source,
        "costs_per_side": {"fee": str(fee), "slippage": str(slip), "stress_multipliers": [2, 3]},
        "initial_equity_usdt": CAPITAL,
        "coverage": coverage,
        "evaluation": {
            "first_trade_open_utc": utc(eval_first),
            "last_close_utc": utc(eval_last),
            "full_observations": total_observations,
            "holdout_observations": sum(
                len(item["data"]["BTC/USDT"]) - item["start"] for item in holdout
            ),
            "holdout_first_open_utc": utc(
                min(item["data"]["BTC/USDT"][item["start"]].ts for item in holdout)
            ),
            "rule": "last ceil(25% of evaluable observations), no parameter selection",
        },
        "candidates": {
            name: {
                **{
                    key: value
                    for key, value in record.items()
                    if key
                    not in {
                        "full",
                        "holdout",
                        "matched",
                        "matched_holdout",
                        "stress_2x",
                        "stress_3x",
                        "plateau_rows",
                        "robustness",
                    }
                },
                "metrics": {
                    "full": record["full"].stats,
                    "holdout": record["holdout"].stats,
                    "matched_exposure": record["matched"].stats,
                    "matched_holdout": record["matched_holdout"].stats,
                    "stress_2x": record["stress_2x"].stats,
                    "stress_3x": record["stress_3x"].stats,
                },
                "segments": record["full"].segments,
                "holdout_segments": record["holdout"].segments,
            }
            for name, record in candidates.items()
        },
        "buy_and_hold": {name: run.stats for name, run in full_buyholds.items()},
        "legacy_4h_btc": legacy_results,
        "statistical_caveat": "Trend episodes are few; the random-entry diagnostic is not a significance test. With approximately 10–20 independent trends, statistical significance cannot be claimed.",
        "paper_state": "disabled by default; all candidates remain disabled; LIVE blocked",
        "reproduction": "python -m backtest.timing_v3 --snapshot reports/timing_v3/inputs --output reports/timing_v3_replay",
    }
    summary = _jsonable(summary)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    report = render_report(summary)
    (output / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def render_report(summary):
    percent = {
        "total_return",
        "cagr",
        "max_drawdown",
        "worst_12m_return",
        "average_exposure",
        "time_invested",
        "turnover",
    }

    def fmt(value, key):
        if value is None:
            return "N/A"
        return f"{value:.2%}" if key in percent else f"{value:.3f}"

    lines = [
        "# Strategy V3 — frozen daily timing research",
        "",
        "## Weaknesses and limits first",
        "",
        "- Only continuous common BTC/ETH segments with more than 300 raw daily candles are evaluable; all shorter DST-phase segments and timestamp gaps are excluded without bridging.",
        "- Price-only execution ignores historical depth, spread, venue precision, minimum order sizes, and latency; fixed 0.15% adverse slippage and 0.25% fee are assumptions, not realized fills.",
        "- The cache's older zero volumes matched sampled raw UDF responses. These strategies ignore volume; the comparison is not evidence of executable liquidity.",
        "- The 25% chronological holdout is small and must not be treated as independent confirmation. A few trend episodes cannot establish statistical significance.",
        "- The random cyclic-shift diagnostic preserves target blocks approximately but is a simulated null, not an executable strategy or statistical significance test.",
        "- Daily closes understate intraday drawdown; outages, stablecoin risk, model error, future fees, and exchange execution remain unmodeled.",
        "- The legacy 4h baseline uses the unchanged engine and may cover different continuous dates; costs are applied by that engine, but its result schema does not expose aggregate costs.",
        "",
        f"Pre-registration SHA256: `{summary['protocol_sha256']}`. No amendment.",
        f"Fee per side `{float(summary['costs_per_side']['fee']):.2%}`, adverse slippage per side `{float(summary['costs_per_side']['slippage']):.2%}`; source: {summary['fee_observation']['endpoint']} public schedule, max tier {summary['fee_observation']['maximum_fee']}.",
        f"Coverage: {summary['coverage']['common_timestamp_count']} exact common timestamps; {summary['coverage']['eligible_segment_count']} eligible segments; {summary['evaluation']['full_observations']} evaluated observations; holdout {summary['evaluation']['holdout_observations']}.",
        "",
        "## Full-sample metrics and baselines",
        "",
        "| Run | Return | CAGR | Max DD | Calmar | Sharpe | Sortino | Worst 12m | Avg exposure | Invested days | Round trips | Legs | Turnover | Costs USDT |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    records = []
    for name, cand in summary["candidates"].items():
        records.append((name, cand["metrics"]["full"]))
        records.append((f"{name} matched", cand["metrics"]["matched_exposure"]))
    records.extend(summary["buy_and_hold"].items())
    for item in summary["legacy_4h_btc"]:
        if item["status"] == "evaluated":
            records.append((f"Legacy 4h BTC seg {item['segment']}", item["metrics"]))
    for name, metrics in records:
        keys = [
            "total_return",
            "cagr",
            "max_drawdown",
            "calmar",
            "sharpe",
            "sortino",
            "worst_12m_return",
            "average_exposure",
            "time_invested",
            "round_trips",
            "trade_legs",
            "turnover",
            "total_costs",
        ]
        values = [fmt(metrics.get(key), key) for key in keys]
        lines.append("| " + " | ".join([name, *values]) + " |")
    lines.extend(
        [
            "",
            "## Acceptance — per candidate",
            "",
            "| Candidate | Status | Criteria | Enabled |",
            "|---|---|---|---|",
        ]
    )
    for name, candidate in summary["candidates"].items():
        checks = "; ".join(
            f"{'PASS' if result else 'FAIL'} {i}"
            for i, result in enumerate(candidate["acceptance"].values(), 1)
        )
        lines.append(f"| {name} | {candidate['status']} | {checks} | No |")
    lines.extend(["", "## Robustness and regimes", ""])
    for name, candidate in summary["candidates"].items():
        plateau = candidate["plateau"]
        null = candidate["random_timing_null"]
        phases = candidate["phases"]
        lines.append(f"### Candidate {name}")
        lines.append("")
        lines.append(
            f"- Plateau: **{plateau['assessment']}**, {plateau['passes']}/{plateau['cases']} grid cases pass ({plateau['pass_fraction']:.1%}); return range {plateau['return_range'][0]:.2%} to {plateau['return_range'][1]:.2%}, drawdown range {plateau['drawdown_range'][0]:.2%} to {plateau['drawdown_range'][1]:.2%}."
        )
        lines.append(
            f"- Timing null: {null['trials']} cyclic shifts; share matching/exceeding actual return "
            f"`{null['share_net_return_ge_actual']}`, actual Calmar `{null['share_calmar_ge_actual']}`; "
            f"unshifted reconstruction error `{null['reconstruction_return_error']}`. No significance claim."
        )
        lines.append(
            f"- Major phases >=90 days: {phases['major_phase_count']}; candidate invested episodes: {phases['candidate_invested_episodes']}; regime metrics: `{json.dumps(phases['by_vote'], sort_keys=True)}`."
        )
        lines.append(
            f"- Last 12 calendar months actually observed: `{json.dumps(phases['last_12_calendar_months'], sort_keys=True)}`."
        )
        lines.append("")
    lines.extend(
        [
            "## Coverage detail",
            "",
            "| Segment | Start UTC | End UTC | Inputs | Evaluable after warmup | Grid offset |",
            "|---:|---|---|---:|---:|---:|",
        ]
    )
    for item in summary["coverage"]["common_segments"]:
        lines.append(
            f"| {item['segment']} | {item['start']} | {item['end']} | {item['count']} | {item['eligible_observations']} | {item['grid_offset_seconds_mod_86400']}s |"
        )
    lines.extend(
        [
            "",
            "Excluded segment policy: " + summary["coverage"]["excluded_reason"] + ".",
            "",
            "## Legacy 4h baseline coverage",
            "",
        ]
    )
    for item in summary["legacy_4h_btc"]:
        lines.append(
            f"- `{item['status']}` segment {item.get('segment')}: {item.get('start', item.get('reason'))} to {item.get('end', '')}; {item.get('observations', '')} daily-sampled observations."
        )
    lines.extend(
        [
            "",
            "No candidate was enabled by this report. All candidates remain disabled; LIVE remains blocked.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Verified input snapshot directory")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/timing_v3")
    try:
        return evaluate(parser.parse_args())
    except (ConfigError, ValueError, KeyError, OSError, ArithmeticError) as error:
        print(f"V3 evaluation refused: {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
