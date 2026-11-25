"""Synthetic/offline causal feature, precedence and backtest execution checks."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from backtest.portfolio import common_segments, historical_book, simulate
from exchange.base import Candle, Rules
from risk.portfolio import PortfolioLimits
from strategy.layered import DAY, Features, Layer, LayeredConfig, LayeredPortfolio, Lot

SYMBOLS = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT")


def bars(count=310):
    return [
        Candle(73800 + i * DAY, 100 + i * 0.1, 102 + i * 0.1, 98 + i * 0.1, 100 + i * 0.1, 10000)
        for i in range(count)
    ]


def feature(ts=73800, **values):
    return replace(Features(ts, True, False, False, False, False, D(90), D(2)), **values)


@pytest.mark.parametrize("index", [200, 250, 300])
def test_features_causal_for_both_layers_and_regime(index):
    model = LayeredPortfolio(LayeredConfig())
    rows = bars(310)
    full = model.prepare(rows)
    assert model.prepare(rows[: index + 1])[-1] == full[index]
    changed = rows[: index + 1] + [Candle(r.ts, 900, 1000, 800, 950, 1) for r in rows[index + 1 :]]
    assert model.prepare(changed)[: index + 1] == full[: index + 1]


def test_previous_channel_excludes_signal_candle_and_fresh_low():
    rows = bars()
    ts = rows[-1].ts
    # New signal closes through yesterday's high although today's high is even higher.
    rows[-1] = Candle(ts, 131, 150, 128, 145, 10000)
    f = LayeredPortfolio(LayeredConfig()).prepare(rows)[-1]
    assert f.trend_entry and f.above
    assert f.trail == D(str(min(r.low for r in rows[-21:-1])))


def test_precedence_is_trend_then_pullback_then_alphabetical_and_no_overlap():
    m = LayeredPortfolio(LayeredConfig())
    data = {s: feature(trend_entry=True, pullback_entry=True) for s in reversed(SYMBOLS)}
    entries = m.entries(data, {"ETH/USDT"})
    assert [e.symbol for e in entries] == ["BTC/USDT", "SOL/USDT", "XRP/USDT"]
    assert all(e.layer == Layer.TREND for e in entries)
    data["BTC/USDT"] = feature(pullback_entry=True)
    assert [e.layer for e in m.entries(data, {})] == [Layer.TREND] * 3 + [Layer.PULLBACK]


def test_regime_and_breadth_block_entries_not_position_exits():
    data = {s: feature(trend_entry=True) for s in SYMBOLS}
    data["BTC/USDT"] = feature(above=False, below=True)
    m = LayeredPortfolio(LayeredConfig())
    assert m.entries(data, {}) == []
    lot = Lot("BTC/USDT", Layer.TREND, D(1), D(100), D(90), 0)
    assert m.exit(lot, data["BTC/USDT"], DAY) == "EMA regime exit"
    m = LayeredPortfolio(LayeredConfig(btc_filter=False, breadth_enabled=True, breadth_min=0.9))
    assert m.entries(data, {}) == []
    assert LayeredConfig().breadth_enabled is False


def test_pullback_exit_time_and_monotone_trail():
    m = LayeredPortfolio(LayeredConfig())
    pull = Lot("ETH/USDT", Layer.PULLBACK, D(1), D(100), D(90), DAY)
    assert m.exit(pull, feature(), 7 * DAY) is None
    assert m.exit(pull, feature(), 8 * DAY) == "time stop"
    assert m.exit(pull, feature(pullback_exit=True), 2 * DAY) == "RSI/5-day high exit"
    assert m.next_stop(pull, feature(trail=D(95))) == 90
    trend = replace(pull, layer=Layer.TREND)
    assert m.next_stop(trend, feature(trail=D(80))) == 90
    assert m.next_stop(trend, feature(trail=D(95))) == 95


def setup_sim(count=305):
    rows = [Candle(73800 + i * DAY, 100, 101, 99, 100, 10000) for i in range(count)]
    data = {s: list(rows) for s in SYMBOLS}
    feats = {s: [feature(r.ts, above=s == "BTC/USDT", trail=D(80)) for r in rows] for s in SYMBOLS}
    feats["BTC/USDT"][299] = feature(rows[299].ts, trend_entry=True, trail=D(80))
    rules = {s: Rules(D(".000001"), D(".01"), D(".5")) for s in SYMBOLS}
    return data, feats, rules


def run_sim(data, features, rules):
    return simulate(
        data,
        LayeredConfig(),
        PortfolioLimits(),
        rules,
        D(".0025"),
        D(".0015"),
        D(100),
        prepared=features,
    )


def test_next_open_not_signal_close_and_gap_stop_uses_open():
    data, f, rules = setup_sim()
    data["BTC/USDT"][301] = Candle(data["BTC/USDT"][301].ts, 85, 87, 80, 86, 10000)
    result = run_sim(data, f, rules)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_ts == data["BTC/USDT"][300].ts
    assert trade.exit_ts == data["BTC/USDT"][301].ts
    assert trade.reason == "gap through stop" and trade.pnl < -1


def test_new_trail_does_not_retroactively_hit_prior_low():
    data, f, rules = setup_sim()
    f["BTC/USDT"][300] = feature(data["BTC/USDT"][300].ts, trail=D("100.5"))
    # The newly raised stop above close becomes active next bar, not inside bar 300.
    result = run_sim(data, f, rules)
    assert result.trades[0].exit_ts == data["BTC/USDT"][301].ts
    assert result.trades[0].reason == "gap through stop"


def test_zero_volume_is_zero_depth_and_no_fill_not_invented_liquidity():
    data, f, rules = setup_sim()
    data["BTC/USDT"][299] = replace(data["BTC/USDT"][299], volume=0)
    result = run_sim(data, f, rules)
    assert not result.trades and result.stats["total_return"] == 0
    assert result.rejected["entry modeled depth"] == 1
    assert historical_book(D(100), 0, 0, PortfolioLimits()).asks[0][1] == 0


def test_rejected_strategy_exit_stays_pending_after_signal_disappears():
    data, f, rules = setup_sim(306)
    # An EMA exit at open 301 fails its zero-depth IOC. The next close recovers above EMA.
    f["BTC/USDT"][300] = feature(data["BTC/USDT"][300].ts, below=True, trail=D(80))
    data["BTC/USDT"][300] = replace(data["BTC/USDT"][300], volume=0)
    result = run_sim(data, f, rules)
    assert result.rejected["exit modeled depth"] == 1
    assert result.trades[0].exit_ts == data["BTC/USDT"][302].ts
    assert result.trades[0].reason == "EMA regime exit"


def test_gap_and_misaligned_feature_rejected():
    data, f, rules = setup_sim()
    f["BTC/USDT"][299] = replace(f["BTC/USDT"][299], ts=0)
    with pytest.raises(ValueError, match="preceding"):
        run_sim(data, f, rules)
    data["ETH/USDT"].pop(100)
    with pytest.raises(ValueError, match="Aligned"):
        run_sim(data, f, rules)


def test_common_segments_do_not_bridge_or_relabel():
    data = {s: bars(10) for s in SYMBOLS}
    data["ETH/USDT"].pop(5)
    result = common_segments(data, 73800)
    assert [len(x["BTC/USDT"]) for x in result] == [5, 4]
    assert result[1]["BTC/USDT"][0].ts == data["BTC/USDT"][6].ts
