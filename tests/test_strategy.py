import pandas as pd

from strategy import Action, RSIMeanReversion, TrendFollowing, build


def test_trend_requires_both_regime_and_new_bullish_cross(cfg):
    strategy = TrendFollowing(cfg)
    table = pd.DataFrame(
        {
            "ts": range(cfg.trend + 2),
            "close": 110.0,
            "atr": 2.0,
            "fast": 101.0,
            "slow": 100.0,
            "trend": 95.0,
        }
    )
    table.loc[cfg.trend - 1, "fast"] = 99.0
    assert strategy.evaluate(table, cfg.trend).action == Action.BUY
    assert strategy.evaluate(table, cfg.trend + 1).action == Action.HOLD
    table.loc[cfg.trend, "close"] = 90.0
    assert strategy.evaluate(table, cfg.trend).action == Action.SELL


def test_volatility_filter_blocks_new_entry(cfg):
    strategy = TrendFollowing(cfg)
    table = pd.DataFrame(
        {
            "ts": range(cfg.trend + 1),
            "close": 110.0,
            "atr": 0.01,
            "fast": 101.0,
            "slow": 100.0,
            "trend": 95.0,
        }
    )
    table.loc[cfg.trend - 1, "fast"] = 99.0
    assert strategy.evaluate(table, cfg.trend).action == Action.HOLD


def test_rsi_strategy_is_optional_and_long_only(cfg):
    assert isinstance(build(cfg), TrendFollowing)
    altered = type(cfg).model_validate({**cfg.model_dump(), "name": "rsi"})
    strategy = build(altered)
    assert isinstance(strategy, RSIMeanReversion)
    table = pd.DataFrame(
        {"ts": [1, 2, 3], "close": [100.0] * 3, "atr": [2.0] * 3, "rsi": [20.0, 40.0, 70.0]}
    )
    assert [strategy.evaluate(table, i).action for i in range(3)] == [
        Action.BUY,
        Action.HOLD,
        Action.SELL,
    ]
