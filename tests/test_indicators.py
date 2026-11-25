import numpy as np
import pandas as pd
import pytest

from indicators import atr, bollinger, ema, macd, rsi, sma, wilder


def test_sma_warmup_and_values():
    result = sma(pd.Series([1.0, 2.0, 3.0, 4.0]), 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2:].tolist() == [2.0, 3.0]


def test_ema_recursive_seed():
    result = ema(pd.Series([1.0, 2.0, 3.0, 4.0]), 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(2.25)
    assert result.iloc[3] == pytest.approx(3.125)


def test_wilder_sma_seed_and_recursion():
    value = wilder(pd.Series([np.nan, 1.0, 2.0, 6.0, 4.0]), 3)
    assert value.iloc[:3].isna().all()
    assert value.iloc[3] == 3
    assert value.iloc[4] == pytest.approx(10 / 3)


def test_wilder_restarts_after_gap():
    value = wilder(pd.Series([1.0, 1.0, np.nan, 5.0, 5.0]), 2)
    assert np.isnan(value.iloc[3])
    assert value.iloc[4] == 5


@pytest.mark.parametrize(
    ("values", "expected"), [(range(30), 100), (range(30, 0, -1), 0), ([5.0] * 30, 50)]
)
def test_rsi_edges(values, expected):
    assert rsi(pd.Series(values, dtype=float)).iloc[-1] == expected


def test_rsi_known_wilder_example():
    prices = [
        44.34,
        44.09,
        44.15,
        43.61,
        44.33,
        44.83,
        45.10,
        45.42,
        45.84,
        46.08,
        45.89,
        46.03,
        45.61,
        46.28,
        46.28,
    ]
    value = rsi(pd.Series(prices))
    assert value.iloc[:14].isna().all()
    assert value.iloc[14] == pytest.approx(70.464135, rel=1e-6)


def test_atr_includes_gaps():
    result = atr(
        pd.Series([11.0, 16.0, 15.0]),
        pd.Series([9.0, 14.0, 13.0]),
        pd.Series([10.0, 15.0, 14.0]),
        2,
    )
    assert np.isnan(result.iloc[0])
    assert result.iloc[1] == 4
    assert result.iloc[2] == 3


def test_bollinger_uses_population_deviation():
    low, middle, high = bollinger(pd.Series([1.0, 2.0, 3.0]), 3)
    assert middle.iloc[-1] == 2
    assert high.iloc[-1] == pytest.approx(2 + 2 * np.sqrt(2 / 3))
    assert low.iloc[-1] == pytest.approx(2 - 2 * np.sqrt(2 / 3))


def test_macd_constant_and_warmup():
    line, signal, histogram = macd(pd.Series([7.0] * 100))
    assert line.iloc[:25].isna().all()
    assert signal.iloc[:33].isna().all()
    assert (line.iloc[33:] == 0).all()
    assert (histogram.iloc[33:] == 0).all()


@pytest.mark.parametrize("function", [sma, ema, rsi])
def test_indicator_prefix_is_causal(function):
    values = pd.Series(np.random.default_rng(17).normal(size=120).cumsum() + 100)
    pd.testing.assert_series_equal(function(values, 14).iloc[:80], function(values.iloc[:80], 14))


def test_atr_macd_bollinger_are_causal():
    values = pd.Series(np.random.default_rng(19).uniform(80, 120, 120))
    pd.testing.assert_series_equal(
        atr(values + 2, values - 2, values).iloc[:80],
        atr(values.iloc[:80] + 2, values.iloc[:80] - 2, values.iloc[:80]),
    )
    for function in (macd, bollinger):
        for full, prefix in zip(function(values), function(values.iloc[:80]), strict=True):
            pd.testing.assert_series_equal(full.iloc[:80], prefix)
