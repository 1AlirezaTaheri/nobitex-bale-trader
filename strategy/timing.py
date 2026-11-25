"""Pre-registered low-turnover close-based timing rules, shared by research and PAPER."""

from dataclasses import dataclass
from enum import StrEnum
from math import sqrt

import numpy as np
import pandas as pd

from exchange.base import Candle

EMA_LENGTHS = (100, 150, 200, 250)
DEFAULT_HYSTERESIS = 0.02
DEFAULT_VOL_TARGET = 0.40
DEFAULT_REBALANCE = 0.25
VOL_WINDOW = 30
ANNUAL_DAYS = 365


class Candidate(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True, slots=True)
class TimingFeatures:
    timestamps: tuple[int, ...]
    closes: tuple[float, ...]
    opens: tuple[float, ...]
    emas: dict[int, tuple[float | None, ...]]
    votes: dict[int, tuple[bool, ...]]
    annual_volatility: tuple[float | None, ...]


def hysteresis_vote(close: float, average: float, previous: bool, band: float = DEFAULT_HYSTERESIS):
    """Strictly cross outside the band; equality and the interior retain prior state."""
    if not 0 <= band < 1:
        raise ValueError("Hysteresis must be in [0, 1)")
    if not previous and close > average * (1 + band):
        return True
    if previous and close < average * (1 - band):
        return False
    return previous


def prepare(rows: list[Candle], *, lengths=EMA_LENGTHS, hysteresis=DEFAULT_HYSTERESIS):
    if not rows or any(b.ts - a.ts != 86400 for a, b in zip(rows, rows[1:])):
        raise ValueError("Timing features require a nonempty contiguous raw daily segment")
    closes = pd.Series([row.close for row in rows], dtype="float64")
    emas = {
        period: closes.ewm(span=period, adjust=False, min_periods=period).mean().to_numpy()
        for period in lengths
    }
    votes = {}
    for period, series in emas.items():
        active = False
        decisions = []
        for close, average in zip(closes.to_numpy(), series, strict=True):
            if np.isfinite(average):
                active = hysteresis_vote(float(close), float(average), active, hysteresis)
            decisions.append(active)
        votes[period] = tuple(decisions)
    returns = closes.pct_change(fill_method=None)
    vol = returns.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std(ddof=1) * sqrt(ANNUAL_DAYS)
    return TimingFeatures(
        tuple(row.ts for row in rows),
        tuple(row.close for row in rows),
        tuple(row.open for row in rows),
        {k: tuple(float(x) if np.isfinite(x) else None for x in v) for k, v in emas.items()},
        votes,
        tuple(float(x) if np.isfinite(x) else None for x in vol),
    )


def vote_paths(features: TimingFeatures, lengths=EMA_LENGTHS, hysteresis=DEFAULT_HYSTERESIS):
    result = {}
    for period in lengths:
        active, decisions = False, []
        for close, average in zip(features.closes, features.emas[period], strict=True):
            if average is not None:
                active = hysteresis_vote(close, average, active, hysteresis)
            decisions.append(active)
        result[period] = tuple(decisions)
    return result


def raw_targets(
    features: dict[str, TimingFeatures],
    candidate: Candidate | str,
    *,
    hysteresis=DEFAULT_HYSTERESIS,
    vol_target=DEFAULT_VOL_TARGET,
    lengths=EMA_LENGTHS,
):
    """Close-time targets before the rebalance trigger; one row per common close."""
    candidate = Candidate(candidate)
    symbols = ("BTC/USDT", "ETH/USDT") if candidate == Candidate.D else ("BTC/USDT",)
    if any(symbol not in features for symbol in symbols):
        raise ValueError("Candidate data missing required BTC/ETH close series")
    timeline = features[symbols[0]].timestamps
    if any(features[s].timestamps != timeline for s in symbols):
        raise ValueError("Candidate features must share exact timestamps")
    vote_lengths = (200,) if candidate == Candidate.A and 200 in lengths else lengths
    if candidate == Candidate.A and 200 not in lengths:
        vote_lengths = (tuple(lengths)[0],)
    paths = {symbol: vote_paths(features[symbol], vote_lengths, hysteresis) for symbol in symbols}
    result = []
    for i in range(len(timeline)):
        row = {}
        for symbol in symbols:
            f = features[symbol]
            votes = paths[symbol]
            if candidate == Candidate.A:
                row[symbol] = float(votes[vote_lengths[0]][i])
                continue
            fraction = sum(votes[p][i] for p in lengths) / len(lengths)
            volatility = f.annual_volatility[i]
            scale = (
                1.0
                if candidate == Candidate.B or volatility == 0
                else 0.0
                if volatility is None
                else min(1.0, vol_target / volatility)
            )
            weight = fraction * scale
            row[symbol] = 0.5 * weight if candidate == Candidate.D else weight
        result.append(row)
    return result


def triggered_targets(
    targets: list[dict[str, float]], candidate: Candidate | str, *, threshold=DEFAULT_REBALANCE
):
    """Accepted target vector at each close; threshold compares targets, never drift."""
    candidate = Candidate(candidate)
    if not 0 <= threshold <= 1:
        raise ValueError("Rebalance threshold must be in [0, 1]")
    symbols = tuple(sorted(targets[0])) if targets else ()
    accepted = {s: 0.0 for s in symbols}
    result = []
    for target in targets:
        if candidate == Candidate.A:
            accepted = dict(target)
        elif sum(abs(target[s] - accepted[s]) for s in symbols) + 1e-12 >= threshold:
            accepted = dict(target)
        result.append(dict(accepted))
    return result


def targets_for(
    features,
    candidate,
    *,
    hysteresis=DEFAULT_HYSTERESIS,
    vol_target=DEFAULT_VOL_TARGET,
    threshold=DEFAULT_REBALANCE,
    lengths=EMA_LENGTHS,
    start_index=0,
):
    raw = raw_targets(
        features, candidate, hysteresis=hysteresis, vol_target=vol_target, lengths=lengths
    )
    prefix = [{s: 0.0 for s in row} for row in raw[:start_index]]
    return prefix + triggered_targets(raw[start_index:], candidate, threshold=threshold)
