"""Causal daily features, precedence and position rules shared by both runners."""

from dataclasses import dataclass
from decimal import Decimal as D
from enum import StrEnum

import pandas as pd
from pydantic import Field, model_validator

from app.config import Strict
from indicators import atr, ema, rsi

DAY = 86400


class Layer(StrEnum):
    TREND = "DailyDonchianTrend"
    PULLBACK = "TrendPullback"


class LayeredConfig(Strict):
    enabled: bool = False
    trend_enabled: bool = True
    pullback_enabled: bool = True
    btc_filter: bool = True
    breadth_enabled: bool = False
    breadth_min: float = Field(default=0.5, gt=0, le=1)
    ema_period: int = Field(default=200, ge=50, le=300)
    atr_period: int = Field(default=20, ge=2, le=60)
    donchian_entry: int = Field(default=55, ge=2, le=150)
    donchian_exit: int = Field(default=20, ge=2, le=100)
    trend_atr: float = Field(default=3, gt=0, le=10)
    pullback_atr: float = Field(default=2, gt=0, le=10)
    rsi_period: int = Field(default=3, ge=2, le=30)
    rsi_entry: float = Field(default=15, gt=0, lt=100)
    rsi_exit: float = Field(default=60, gt=0, lt=100)
    freshness_low: int = Field(default=20, ge=2, le=50)
    pullback_high: int = Field(default=5, ge=2, le=30)
    max_hold_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def valid(self):
        if self.rsi_entry >= self.rsi_exit or self.donchian_exit >= self.donchian_entry:
            raise ValueError("Require RSI entry < exit and Donchian exit < entry")
        if not (self.trend_enabled or self.pullback_enabled):
            raise ValueError("Enable at least one trading layer")
        return self

    @property
    def warmup(self):
        # Extra history is retained for recursive initialization, even when the EMA is shorter.
        return max(300, self.ema_period + 1, self.donchian_entry + 1)


@dataclass(frozen=True, slots=True)
class Features:
    ts: int
    above: bool
    below: bool
    trend_entry: bool
    pullback_entry: bool
    pullback_exit: bool
    trail: D
    atr: D


@dataclass(frozen=True, slots=True)
class Entry:
    symbol: str
    layer: Layer
    distance: D


@dataclass(frozen=True, slots=True)
class Lot:
    symbol: str
    layer: Layer
    qty: D
    cost: D
    stop: D
    entry_ts: int


class LayeredPortfolio:
    def __init__(self, cfg: LayeredConfig):
        self.cfg = cfg

    def prepare(self, rows):
        cfg = self.cfg
        table = pd.DataFrame((r.ts, r.high, r.low, r.close) for r in rows)
        table.columns = ["ts", "high", "low", "close"]
        c, h, low = table.close, table.high, table.low
        # The same bounded-window EMA is obtained in PAPER by retaining the continuous segment.
        e = ema(c, cfg.ema_period)
        a = atr(h, low, c, cfg.atr_period)
        r = rsi(c, cfg.rsi_period)
        prev_high = h.shift().rolling(cfg.donchian_entry).max()
        prev_low = low.shift().rolling(cfg.freshness_low).min()
        trail = low.shift().rolling(cfg.donchian_exit).min().fillna(0)
        pull_high = h.shift().rolling(cfg.pullback_high).max()
        return [
            Features(int(ts), above, below, trend, pull, exit_, D(str(t)), D(str(v)))
            for ts, above, below, trend, pull, exit_, t, v in zip(
                table.ts,
                c > e,
                c < e,
                c > prev_high,
                (r < cfg.rsi_entry) & (low >= prev_low),
                (r > cfg.rsi_exit) | (c > pull_high),
                trail,
                a.fillna(0),
                strict=True,
            )
        ]

    def entries(self, features: dict[str, Features], held) -> list[Entry]:
        cfg = self.cfg
        if cfg.btc_filter and not features["BTC/USDT"].above:
            return []
        if (
            cfg.breadth_enabled
            and sum(f.above for f in features.values()) / len(features) < cfg.breadth_min
        ):
            return []
        trend, pull = [], []
        for symbol, f in sorted(features.items()):
            if symbol in held or not f.above or f.atr <= 0:
                continue
            if cfg.trend_enabled and f.trend_entry:
                trend.append(Entry(symbol, Layer.TREND, f.atr * D(str(cfg.trend_atr))))
            elif cfg.pullback_enabled and f.pullback_entry:
                pull.append(Entry(symbol, Layer.PULLBACK, f.atr * D(str(cfg.pullback_atr))))
        return trend + pull

    def exit(self, lot, feature, execution_ts):
        if lot.layer == Layer.TREND:
            return "EMA regime exit" if feature.below else None
        if feature.pullback_exit:
            return "RSI/5-day high exit"
        if execution_ts - lot.entry_ts >= self.cfg.max_hold_days * DAY:
            return "time stop"
        return None

    @staticmethod
    def next_stop(lot, feature):
        return max(lot.stop, feature.trail) if lot.layer == Layer.TREND else lot.stop
