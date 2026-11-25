"""Causal indicators; warm-up observations are NaN."""

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def wilder(series: pd.Series, period: int) -> pd.Series:
    values = series.to_numpy(dtype=float)
    output = np.full(len(values), np.nan)
    count, total, last = 0, 0.0, np.nan
    for i, value in enumerate(values):
        if not np.isfinite(value):
            count, total, last = 0, 0.0, np.nan
            continue
        if count < period:
            count += 1
            total += value
            if count == period:
                last = total / period
        else:
            last += (value - last) / period
        output[i] = last
    return pd.Series(output, index=series.index)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    diff = close.diff()
    gain, loss = wilder(diff.clip(lower=0), period), wilder(-diff.clip(upper=0), period)
    return (100 * gain / (gain + loss)).mask((gain == 0) & (loss == 0), 50)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    previous = close.shift()
    tr = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(
        axis=1
    )
    return wilder(tr, period)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    line = ema(close, fast) - ema(close, slow)
    average = ema(line, signal)
    return line, average, line - average


def bollinger(close: pd.Series, period: int = 20, width: float = 2) -> tuple:
    middle, deviation = sma(close, period), close.rolling(period).std(ddof=0)
    return middle - width * deviation, middle, middle + width * deviation
