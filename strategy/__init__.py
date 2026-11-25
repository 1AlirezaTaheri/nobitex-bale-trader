from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import pandas as pd

from app.config import StrategyConfig
from exchange.base import Candle
from indicators import atr, ema, rsi


class Action(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class Signal:
    action: Action
    ts: int
    distance: float
    reason: str


class Strategy(ABC):
    def __init__(self, config: StrategyConfig):
        self.config = config

    def common(self, candles: list[Candle]) -> pd.DataFrame:
        table = pd.DataFrame(
            [(x.ts, x.high, x.low, x.close) for x in candles],
            columns=["ts", "high", "low", "close"],
        )
        table["atr"] = atr(table.high, table.low, table.close, self.config.atr_period)
        return table

    @abstractmethod
    def prepare(self, candles: list[Candle]) -> pd.DataFrame: ...

    @abstractmethod
    def evaluate(self, table: pd.DataFrame, index: int) -> Signal: ...

    def decide(self, candles: list[Candle]) -> Signal:
        return self.evaluate(self.prepare(candles), len(candles) - 1)

    def metadata(self, row: pd.Series) -> tuple[int, float, bool]:
        distance = float(row.atr) * self.config.atr_multiplier
        if not isfinite(distance) or distance <= 0:
            return int(row.ts), 0.0, False
        return int(row.ts), distance, row.atr / row.close >= self.config.min_atr_pct


class TrendFollowing(Strategy):
    def prepare(self, candles: list[Candle]) -> pd.DataFrame:
        result = self.common(candles)
        for name in ("fast", "slow", "trend"):
            result[name] = ema(result.close, getattr(self.config, name))
        return result

    def evaluate(self, table: pd.DataFrame, index: int) -> Signal:
        row = table.iloc[index]
        ts, distance, liquid = self.metadata(row)
        if index < self.config.trend or not distance:
            return Signal(Action.HOLD, ts, distance, "warmup or zero ATR")
        previous = table.iloc[index - 1]
        if (
            liquid
            and row.close > row.trend
            and previous.fast <= previous.slow
            and row.fast > row.slow
        ):
            return Signal(Action.BUY, ts, distance, "bullish EMA crossover")
        if row.close < row.trend or (previous.fast >= previous.slow and row.fast < row.slow):
            return Signal(Action.SELL, ts, distance, "trend exit")
        return Signal(Action.HOLD, ts, distance, "no trend trigger")


class RSIMeanReversion(Strategy):
    def prepare(self, candles: list[Candle]) -> pd.DataFrame:
        result = self.common(candles)
        result["rsi"] = rsi(result.close, self.config.rsi_period)
        return result

    def evaluate(self, table: pd.DataFrame, index: int) -> Signal:
        row = table.iloc[index]
        ts, distance, liquid = self.metadata(row)
        if liquid and row.rsi <= self.config.rsi_entry:
            return Signal(Action.BUY, ts, distance, "oversold RSI")
        if row.rsi >= self.config.rsi_exit:
            return Signal(Action.SELL, ts, distance, "mean reversion exit")
        return Signal(Action.HOLD, ts, distance, "no RSI trigger")


def build(config: StrategyConfig) -> Strategy:
    return (TrendFollowing if config.name == "trend" else RSIMeanReversion)(config)
