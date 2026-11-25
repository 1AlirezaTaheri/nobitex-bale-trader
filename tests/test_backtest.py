from decimal import Decimal

import pandas as pd
import pytest

from backtest import metrics, run
from exchange.base import Candle
from strategy import Action, Signal, Strategy, build
from tests.conftest import candles

D = Decimal


class Scripted(Strategy):
    def __init__(self, cfg, entries=(), exits=(), distance=10):
        super().__init__(cfg)
        self.entries, self.exits, self.distance = set(entries), set(exits), distance

    def prepare(self, rows):
        return pd.DataFrame({"ts": [c.ts for c in rows]})

    def evaluate(self, table, index):
        action = (
            Action.BUY
            if index in self.entries
            else Action.SELL
            if index in self.exits
            else Action.HOLD
        )
        return Signal(action, int(table.iloc[index].ts), self.distance, "test script")


def test_closed_signal_executes_next_open_not_its_own_close(cfg, risk):
    rows = candles(cfg.warmup + 6)
    result = run(rows, cfg, risk, D(100), strategy=Scripted(cfg, [cfg.warmup]))
    assert result.trades
    trade = result.trades[0]
    assert trade.entry_ts == rows[cfg.warmup + 1].ts
    assert trade.entry == pytest.approx(rows[cfg.warmup + 1].open * float(1 + risk.slippage))


def test_future_prices_do_not_change_earlier_signals(cfg):
    rows = candles(cfg.warmup + 20)
    strategy = build(cfg)
    full = strategy.prepare(rows)
    for length in (cfg.warmup, cfg.warmup + 3, cfg.warmup + 10):
        prefix = strategy.prepare(rows[:length])
        assert strategy.evaluate(full, length - 1) == strategy.evaluate(prefix, length - 1)


def test_entry_bar_stop_is_not_ignored(cfg, risk):
    rows = candles(cfg.warmup + 5)
    i = cfg.warmup + 1
    rows[i] = Candle(rows[i].ts, 100, 102, 80, 100, 10)
    result = run(rows, cfg, risk, D(100), strategy=Scripted(cfg, [i - 1], distance=5))
    assert result.trades[0].entry_ts == result.trades[0].exit_ts == rows[i].ts
    assert result.trades[0].reason == "intrabar ATR stop"


def test_open_exit_precedes_a_future_intrabar_low(cfg, risk):
    rows = candles(cfg.warmup + 6)
    entry, exit_ = cfg.warmup + 1, cfg.warmup + 2
    rows[exit_] = Candle(rows[exit_].ts, 110, 112, 50, 100, 10)
    result = run(rows, cfg, risk, D(100), strategy=Scripted(cfg, [entry - 1], [exit_ - 1]))
    trade = result.trades[0]
    assert trade.reason == "closed-candle strategy exit"
    assert trade.exit == pytest.approx(110 * float(1 - risk.slippage))


def test_gap_stop_is_filled_at_bad_open_not_optimistic_stop(cfg, risk):
    rows = candles(cfg.warmup + 6)
    i = cfg.warmup + 2
    rows[i] = Candle(rows[i].ts, 60, 62, 55, 59, 10)
    result = run(rows, cfg, risk, D(100), strategy=Scripted(cfg, [i - 2]))
    assert result.trades[0].reason == "gap through ATR stop"
    assert result.trades[0].exit == pytest.approx(60 * float(1 - risk.slippage))


def test_trailing_stop_not_applied_retroactively_to_same_bar(cfg, risk):
    rows = candles(cfg.warmup + 6)
    i = cfg.warmup + 1
    rows[i] = Candle(rows[i].ts, 100, 150, 99, 130, 10)
    rows[i + 1] = Candle(rows[i + 1].ts, 130, 140, 129, 135, 10)
    result = run(rows, cfg, risk, D(100), strategy=Scripted(cfg, [i - 1], distance=10))
    assert result.trades[0].exit_ts == rows[i + 1].ts


def test_fee_slippage_and_benchmark_are_two_sided(cfg, risk):
    rows = [Candle(1800 + i * cfg.seconds, 100, 100, 100, 100, 10) for i in range(cfg.warmup + 5)]
    result = run(rows, cfg, risk, D(100), strategy=Scripted(cfg, [cfg.warmup - 1], distance=5))
    assert result.metrics["total_return"] < 0
    assert result.buy_hold_return < 0
    assert result.trades[0].pnl < 0
    assert result.equity.equity.iloc[-1] - 100 == pytest.approx(sum(t.pnl for t in result.trades))


def test_daily_and_drawdown_breakers_actually_block_new_entries(cfg, risk):
    altered = type(risk).model_validate(
        {**risk.model_dump(), "max_daily_loss": "0.0001", "max_drawdown": "0.0001"}
    )
    rows = candles(cfg.warmup + 20)
    result = run(
        rows,
        cfg,
        altered,
        D(100),
        strategy=Scripted(
            cfg, range(cfg.warmup - 1, len(rows)), range(cfg.warmup, len(rows), 2), distance=2
        ),
    )
    assert len(result.trades) == 1
    assert result.blocked_bars > 0


def test_holdout_equity_excludes_training_period(cfg, risk):
    rows = candles(cfg.warmup + 100)
    start = cfg.warmup + 40
    result = run(rows, cfg, risk, D(100), start_index=start)
    assert result.bars == 60
    assert result.equity.timestamp.iloc[0] == rows[start].ts
    assert len(result.equity) == 61


def test_backtest_refuses_missing_candles_and_short_history(cfg, risk):
    rows = candles(cfg.warmup + 4)
    with pytest.raises(ValueError):
        run(rows[:10], cfg, risk, D(100))
    with pytest.raises(ValueError):
        run(rows[:5] + rows[6:], cfg, risk, D(100))


def test_undefined_ratios_are_not_fake_zeroes():
    result = metrics(pd.Series([100.0, 100.0, 100.0]), [], 14400)
    assert (
        result["sharpe"] is None and result["sortino"] is None and result["profit_factor"] is None
    )
