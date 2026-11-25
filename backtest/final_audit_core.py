"""Frozen final-audit accounting and deterministic statistical diagnostics, no network."""

import math
from datetime import UTC, datetime
from functools import lru_cache
from statistics import NormalDist

import numpy as np

from strategy.timing import targets_for

DAY = 86400
SEED = 20261125
BTC, ETH = "BTC/USDT", "ETH/USDT"


def month(ts):
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m")


def metrics(rows):
    if not rows:
        return {"status": "unavailable", "days": 0}
    r = np.array([x["return"] for x in rows], dtype=float)
    eq = 100 * np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(np.r_[100, eq])[1:] - 1
    mean, vol = float(r.mean()), float(r.std(ddof=1)) if len(r) > 1 else 0
    cagr = float((eq[-1] / 100) ** (365 / len(r)) - 1)
    downside = float(np.sqrt(np.mean(np.minimum(r, 0) ** 2)))
    cost_known = all(x.get("cost") is not None for x in rows)
    costs = sum(x["cost"] for x in rows) if cost_known else None
    gross = float(eq[-1] - 100) + costs if costs is not None else None
    longest = current = 0
    for d in dd:
        current = current + 1 if d < -1e-12 else 0
        longest = max(current, longest)
    result = {
        "days": len(r),
        "total_return": float(eq[-1] / 100 - 1),
        "cagr": cagr,
        "volatility": vol * math.sqrt(365),
        "max_drawdown": float(dd.min()),
        "calmar": cagr / -float(dd.min()) if dd.min() < 0 else None,
        "sharpe": mean / vol * math.sqrt(365) if vol else None,
        "sortino": mean / downside * math.sqrt(365) if downside else None,
        "ulcer_index": float(np.sqrt(np.mean(dd**2))),
        "cvar_5": float(np.sort(r)[: max(1, math.ceil(0.05 * len(r)))].mean()),
        "longest_drawdown_days": longest,
        "time_under_water": float(np.mean(dd < -1e-12)),
        "time_invested": float(
            np.mean([x.get("invested", (x.get("exposure") or 0) > 1e-12) for x in rows])
        ),
        "average_exposure": float(np.mean([x["exposure"] for x in rows]))
        if all(x.get("exposure") is not None for x in rows)
        else None,
        "round_trips": sum(x.get("trips", 0) for x in rows)
        if all(x.get("trips", 0) is not None for x in rows)
        else None,
        "trade_legs": sum(x.get("legs", 0) for x in rows)
        if all(x.get("legs", 0) is not None for x in rows)
        else None,
        "turnover": sum(x.get("notional", 0) for x in rows) / float(eq.mean())
        if cost_known
        else None,
        "total_costs": costs,
        "costs_pct_gross_profit": costs / gross if gross and gross > 0 else None,
        "gross_profit": gross,
        "final_equity": float(eq[-1]),
    }
    for length, label in [(21, "1m"), (63, "3m"), (126, "6m"), (365, "12m")]:
        values = []
        for seg in dict.fromkeys(x["segment"] for x in rows):
            local = np.array([x["return"] for x in rows if x["segment"] == seg])
            if len(local) >= length:
                sums = np.r_[0.0, np.cumsum(np.log1p(local))]
                values.extend(np.expm1(sums[length:] - sums[:-length]))
        result["worst_" + label] = float(min(values)) if values else None
    return result


def rolling(rows, length=365):
    out = []
    for end in range(length - 1, len(rows)):
        chosen = rows[end - length + 1 : end + 1]
        if chosen[0]["segment"] != chosen[-1]["segment"]:
            continue
        r = np.array([x["return"] for x in chosen])
        eq = np.r_[1.0, np.cumprod(1 + r)]
        out.append(
            {
                "start": chosen[0]["timestamp"],
                "end": chosen[-1]["timestamp"],
                "segment": chosen[0]["segment"],
                "return": float(eq[-1] - 1),
                "max_drawdown": float(np.min(eq / np.maximum.accumulate(eq) - 1)),
            }
        )
    return out


def quick(r):
    """Vectorized Sharpe, Calmar and negative maximum drawdown per path."""
    r = np.atleast_2d(r)
    eq = np.cumprod(1 + r, axis=1)
    peak = np.maximum.accumulate(np.maximum(1, eq), axis=1)
    dd = (eq / peak - 1).min(axis=1)
    sd = r.std(axis=1, ddof=1)
    sh = np.divide(r.mean(axis=1) * np.sqrt(365), sd, out=np.full(len(r), np.nan), where=sd > 0)
    growth = eq[:, -1] ** (365 / r.shape[1]) - 1
    ca = np.divide(growth, -dd, out=np.full(len(r), np.nan), where=dd < 0)
    return np.column_stack([sh, ca, dd])


def block_indices(segments, count, length, seed=SEED, trials=999):
    """Sample noncircular blocks within segments; no block crosses a missing input interval."""
    if not segments or count < 1 or length < 1 or trials < 1:
        raise ValueError("Bootstrap requires positive dimensions and nonempty segments")
    return _block_indices(tuple(segments), count, length, seed, trials)


@lru_cache(maxsize=24)
def _block_indices(segments, count, length, seed, trials):
    groups = [np.flatnonzero(np.asarray(segments) == s) for s in dict.fromkeys(segments)]
    rng = np.random.default_rng(seed)
    output = np.empty((trials, count), dtype=int)
    weights = np.array([len(g) for g in groups], dtype=float)
    weights /= weights.sum()
    for trial in range(trials):
        indices = []
        while len(indices) < count:
            group = groups[int(rng.choice(len(groups), p=weights))]
            size = min(length, len(group))
            start = int(rng.integers(0, len(group) - size + 1))
            indices.extend(group[start : start + size])
        output[trial] = indices[:count]
    output.flags.writeable = False
    return output


def bootstrap(rows, controls, multiplicity, *, trials=999):
    r = np.array([x["return"] for x in rows])
    seg = [x["segment"] for x in rows]
    result = {"trials": trials, "seed": SEED, "multiple_testing_count": multiplicity, "blocks": {}}
    arrays = {}
    for length in (10, 20, 40):
        idx = block_indices(seg, len(r), length, trials=trials)
        observed = quick(r)[0]
        sampled = quick(r[idx])
        block = {}
        for col, label in enumerate(("sharpe", "calmar", "max_drawdown")):
            values = sampled[:, col]
            finite = values[np.isfinite(values)]
            block[label] = {
                "observed": finite_or_none(observed[col]),
                "finite_draws": len(finite),
                "ci95": quantile(finite, [0.025, 0.975]),
                "ci_adjusted": quantile(finite, [0.025 / multiplicity, 1 - 0.025 / multiplicity]),
            }
        block["differences"] = {}
        for name, other in controls.items():
            paired = np.array([x["return"] for x in other])
            if len(paired) != len(r) or [x["timestamp"] for x in rows] != [
                x["timestamp"] for x in other
            ]:
                raise ValueError("Paired bootstrap requires exact shared timestamps")
            diffs = sampled - quick(paired[idx])
            block["differences"][name] = {}
            for col, label in enumerate(("sharpe", "calmar", "max_drawdown")):
                finite = diffs[:, col][np.isfinite(diffs[:, col])]
                p = (1 + int(np.sum(finite <= 0))) / (len(finite) + 1) if len(finite) else None
                block["differences"][name][label] = {
                    "ci95": quantile(finite, [0.025, 0.975]),
                    "ci_adjusted": quantile(
                        finite, [0.025 / multiplicity, 1 - 0.025 / multiplicity]
                    ),
                    "p_unadjusted": p,
                    "p_bonferroni": min(1, p * multiplicity) if p is not None else None,
                    "direction": "positive favors strategy for all three metrics (DD is negative)",
                }
            if length == 20:
                arrays[name] = diffs[:, :2]
        result["blocks"][str(length)] = block
    idx = block_indices(seg, 365, 20, trials=trials)
    dd = -quick(r[idx])[:, 2]
    result["mc_12m_drawdown_probability"] = {
        str(x): float(np.mean(dd > x)) for x in (0.15, 0.25, 0.40)
    }
    return result, arrays


def finite_or_none(value):
    return float(value) if np.isfinite(value) else None


def quantile(values, probs):
    return [float(x) for x in np.quantile(values, probs)] if len(values) else [None] * len(probs)


def record_length(rows, other, multiplicity):
    delta = np.array([x["return"] for x in rows])
    if other is not None:
        delta -= np.array([x["return"] for x in other])
    mean = float(delta.mean())
    if mean <= 0 or len(delta) < 40:
        return {
            "minimum_days_unadjusted": None,
            "minimum_days_adjusted": None,
            "reason": "Nonpositive daily-return edge or insufficient observations",
        }
    centered = delta - mean
    var = float(np.mean(centered**2))
    # Sum only same-segment lag products; nonnegative conservative variance floor.
    seg = np.array([x["segment"] for x in rows])
    lrv = var
    for lag in range(1, 20):
        mask = seg[lag:] == seg[:-lag]
        cov = float(np.mean(centered[lag:][mask] * centered[:-lag][mask])) if mask.any() else 0
        lrv += 2 * (1 - lag / 20) * cov
    lrv = max(var, lrv)
    return {
        "minimum_days_unadjusted": float(1.645**2 * lrv / mean**2),
        "minimum_days_adjusted": float(
            NormalDist().inv_cdf(1 - 0.05 / multiplicity) ** 2 * lrv / mean**2
        ),
        "note": "Approximate mean-return test with HAC inflation; not a full Sharpe power calculation",
    }


def regimes(data):
    closes = np.array([r.close for r in data])
    ma = np.convolve(closes, np.ones(200) / 200, mode="valid") if len(closes) >= 200 else []
    peak = np.maximum.accumulate(closes)
    labels = ["unknown"] * len(data)
    for i in range(219, len(data)):
        slope = ma[i - 199] / ma[i - 219] - 1
        drawdown = closes[i] / peak[i] - 1
        labels[i] = (
            "bull"
            if drawdown > -0.20 and slope > 0
            else "bear"
            if drawdown <= -0.20 and slope < 0
            else "range"
        )
    return labels


def target_path(item, candidate, delay=0, omit=None):
    raw = targets_for(item["features"], candidate, start_index=item["start"] - 1)
    symbols = (BTC, ETH) if candidate == "D" else (BTC,)
    out = []
    for i in range(item["start"], len(item["data"][BTC])):
        at = i - 1 - delay
        weights = {s: raw[at].get(s, 0) if at >= item["start"] - 1 else 0 for s in symbols}
        if omit:
            weights[omit] = 0
        out.append(weights)
    return out


def simulate_item(
    item,
    kind,
    *,
    fee=0.0025,
    slip=0.0015,
    weight=1.0,
    symbols=(BTC,),
    paths=None,
    band=0.0,
    crash=False,
    execution_delay=0,
):
    """Next-open, fee-inclusive fractional-unit accounting. No market-data mutation."""
    data, start = item["data"], item["start"]
    end = len(data[BTC])
    fee, slip = float(fee), float(slip)
    if not 0 <= fee < 0.1 or not 0 <= slip < 0.1 or not 0 <= weight <= 1:
        raise ValueError("Invalid audit cost or weight")
    timeline = [r.ts for r in data[BTC]]
    if (
        not 200 <= start < end
        or any(b - a != DAY for a, b in zip(timeline, timeline[1:]))
        or any([r.ts for r in data[s]] != timeline for s in symbols)
    ):
        raise ValueError("Exact contiguous daily timestamps and causal warmup required")
    if kind == "targets" and (paths is None or len(paths) != end - start):
        raise ValueError("Target path length mismatch")
    cash, holdings = 100.0, dict.fromkeys(symbols, 0.0)
    rows, fills = [], []
    prior_eq, previous = 100.0, None
    months = {month(data[BTC][i].ts) for i in range(start, end)}
    dca_budget = 100 / len(months)
    labels = regimes(data[BTC])
    last_month = None
    sma = np.convolve([r.close for r in data[BTC]], np.ones(200) / 200, mode="valid")
    for i in range(start, end):
        ts, bar = data[BTC][i].ts, data[BTC][i]
        prices = {s: data[s][i].open for s in symbols}
        pre = cash + sum(holdings[s] * prices[s] for s in symbols)
        exposure = sum(holdings[s] * prices[s] for s in symbols) / pre
        m = month(data[BTC][max(start, i - execution_delay)].ts)
        day_slip = slip * (3 if crash and bar.close / bar.open - 1 < -0.08 else 1)
        cost, notional, legs, trips = 0.0, 0.0, 0, 0
        target = {s: weight / len(symbols) for s in symbols}
        trade = i == start + execution_delay
        if kind == "cash":
            target = dict.fromkeys(symbols, 0.0)
        elif kind == "dca":
            trade = m != last_month
            target = {
                symbols[0]: (
                    holdings[symbols[0]] * prices[symbols[0]]
                    + min(cash, dca_budget) / (1 + day_slip) / (1 + fee)
                )
                / pre
            }
        elif kind == "mix":
            trade = trade or (m != last_month and abs(exposure - weight) >= band - 1e-14)
        elif kind == "sma":
            target = {
                BTC: float(
                    data[BTC][i - 1 - execution_delay].close > sma[i - 200 - execution_delay]
                )
            }
            trade = target != previous
        elif kind == "targets":
            target = paths[i - start]
            trade = target != previous
        if i < start + execution_delay:
            target = dict.fromkeys(symbols, 0.0)
            trade = False
        if (
            any(not np.isfinite(v) or v < 0 for v in target.values())
            or sum(target.values()) > 1 + 1e-10
        ):
            raise ValueError("Only finite, long-only unlevered target weights allowed")
        if trade:
            desired = {s: pre * target.get(s, 0) / prices[s] for s in symbols}
            for s in symbols:
                qty = max(0, holdings[s] - desired[s])
                if qty > 1e-14:
                    proceeds = qty * prices[s] * (1 - day_slip)
                    drag = qty * prices[s] - proceeds * (1 - fee)
                    cash += proceeds * (1 - fee)
                    holdings[s] -= qty
                    cost += drag
                    notional += qty * prices[s]
                    legs += 1
                    if holdings[s] <= 1e-12:
                        holdings[s] = 0.0
                        trips += 1
                    fills.append(
                        {"timestamp": ts, "symbol": s, "side": "sell", "qty": qty, "cost": drag}
                    )
            buys = {s: max(0.0, desired[s] - holdings[s]) for s in symbols}
            required = sum(buys[s] * prices[s] * (1 + day_slip) * (1 + fee) for s in symbols)
            scale = min(1.0, max(0.0, cash) / required) if required else 1.0
            for s in symbols:
                qty = buys[s] * scale
                if qty > 1e-14:
                    paid = qty * prices[s] * (1 + day_slip) * (1 + fee)
                    drag = paid - qty * prices[s]
                    cash -= paid
                    holdings[s] += qty
                    cost += drag
                    notional += qty * prices[s]
                    legs += 1
                    fills.append(
                        {"timestamp": ts, "symbol": s, "side": "buy", "qty": qty, "cost": drag}
                    )
        post = cash + sum(holdings[s] * prices[s] for s in symbols)
        weights = {s: holdings[s] * prices[s] / post for s in symbols}
        opening_drag = 1 - post / pre
        close_eq = cash + sum(holdings[s] * data[s][i].close for s in symbols)
        terminal = 0.0
        if i == end - 1:
            before = close_eq
            for s in symbols:
                if holdings[s] > 1e-14:
                    ref = holdings[s] * data[s][i].close
                    proceeds = ref * (1 - day_slip) * (1 - fee)
                    cost += ref - proceeds
                    notional += ref
                    legs += 1
                    trips += 1
                    cash += proceeds
                    fills.append(
                        {
                            "timestamp": ts + DAY,
                            "symbol": s,
                            "side": "sell",
                            "qty": holdings[s],
                            "cost": ref - proceeds,
                        }
                    )
                    holdings[s] = 0.0
            close_eq = cash
            terminal = 1 - close_eq / before
        rows.append(
            {
                "timestamp": ts,
                "segment": item["number"],
                "return": close_eq / prior_eq - 1,
                "equity": close_eq,
                "exposure": sum(weights.values()),
                "cost": cost,
                "notional": notional,
                "legs": legs,
                "trips": trips,
                "regime": labels[i - 1],
                "weights": weights,
                "open_drag": opening_drag,
                "terminal_drag": terminal,
            }
        )
        prior_eq, previous = close_eq, dict(target)
        if i >= start + execution_delay:
            last_month = m
    return rows, fills


def simulate(items, kind, **kwargs):
    result, fills, capital = [], [], 100.0
    for item in items:
        options = dict(kwargs)
        if kind == "targets":
            options["paths"] = kwargs["paths"][item["number"]]
        rows, events = simulate_item(item, kind, **options)
        scale = capital / 100
        for row in rows:
            row = dict(row)
            for key in ("equity", "cost", "notional"):
                row[key] *= scale
            result.append(row)
        fills.extend({**e, "cost": e["cost"] * scale, "qty": e["qty"] * scale} for e in events)
        capital = result[-1]["equity"]
    return result, fills


def timing_null(items, rows, trials=999):
    if any("weights" not in row for row in rows):
        return {
            "status": "unavailable",
            "reason": "Native engine does not expose exact post-open weights",
        }
    rng = np.random.default_rng(SEED)
    observed = quick([r["return"] for r in rows])[0]
    paths = np.empty((trials, len(rows)))
    cursor = 0
    reconstruction = []
    for item in items:
        chunk = [r for r in rows if r["segment"] == item["number"]]
        symbols = tuple(chunk[0]["weights"])
        returns = np.array(
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
                for i in range(item["start"], len(item["data"][BTC]))
            ]
        )
        weights = np.array([[r["weights"][s] for s in symbols] for r in chunk])
        drag = np.array([r["open_drag"] for r in chunk])
        for trial in range(trials + 1):
            shift = 0 if trial == trials else int(rng.integers(len(chunk)))
            r = (1 - np.roll(drag, shift)) * (
                1 + (np.roll(weights, shift, axis=0) * returns).sum(axis=1)
            ) - 1
            r[-1] = (1 + r[-1]) * (1 - chunk[-1]["terminal_drag"]) - 1
            if trial == trials:
                reconstruction.extend(r)
            else:
                paths[trial, cursor : cursor + len(chunk)] = r
        cursor += len(chunk)
    stats = quick(paths)
    total = np.prod(1 + paths, axis=1) - 1
    actual = np.prod([1 + r["return"] for r in rows]) - 1
    return {
        "trials": trials,
        "return_percentile": float(np.mean(total < actual)),
        "calmar_percentile": float(np.mean(stats[:, 1] < observed[1]))
        if np.isfinite(observed[1])
        else None,
        "unshifted_return_error": float(np.prod(1 + np.array(reconstruction)) - 1 - actual),
        "warning": "Circular observed-weight surrogate, not executable same-turnover orders; seam and terminal convention matter",
    }
