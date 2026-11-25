from dataclasses import replace
from decimal import Decimal as D

import pytest

from backtest.timing_v3 import (
    aligned_segments,
    evaluate_segments,
    matched_exposure,
    save_inputs,
    simulate,
    simulate_constant,
    timing_null,
)
from exchange.base import Candle
from strategy.timing import (
    EMA_LENGTHS,
    Candidate,
    TimingFeatures,
    hysteresis_vote,
    prepare,
    raw_targets,
    triggered_targets,
)

DAY = 86400
BTC = "BTC/USDT"
ETH = "ETH/USDT"


def candles(count, *, start=1_700_000_000, offset=0, price_fn=None):
    rows = []
    for index in range(count):
        close = price_fn(index) if price_fn else 100 + index * 0.1
        rows.append(Candle(start + offset + index * DAY, close, close + 1, close - 1, close, 0))
    return rows


def feature(ts, close=100, averages=None, volatility=0.8):
    averages = averages or {length: 80 for length in EMA_LENGTHS}
    return TimingFeatures(
        timestamps=(ts,),
        closes=(close,),
        opens=(close,),
        emas={length: (averages[length],) for length in averages},
        votes={length: (False,) for length in averages},
        annual_volatility=(volatility,),
    )


def test_hysteresis_enters_exits_and_holds_equality_and_band():
    assert hysteresis_vote(102, 100, False) is False
    assert hysteresis_vote(102.01, 100, False) is True
    assert hysteresis_vote(98, 100, True) is True
    assert hysteresis_vote(97.99, 100, True) is False
    assert hysteresis_vote(100, 100, False) is False


def test_ensemble_uses_independent_votes_and_volatility_scaling():
    averages = {100: 80, 150: 110, 200: 110, 250: 110}
    f = feature(1_700_000_000, averages=averages, volatility=0.8)
    result = raw_targets({BTC: f}, Candidate.B)
    assert result == [{BTC: 0.25}]
    scaled = raw_targets({BTC: f}, Candidate.C)
    assert scaled == [{BTC: 0.125}]


def test_volatility_scaling_caps_at_one_and_d_candidate_total_exposure_at_one():
    btc, eth = feature(1_700_000_000, volatility=0.8), feature(1_700_000_000, volatility=0.8)
    result = raw_targets({BTC: btc, ETH: eth}, Candidate.D)
    assert result == [{BTC: 0.25, ETH: 0.25}]
    assert sum(result[0].values()) <= 1
    low_vol = feature(1_700_000_000, volatility=0.2)
    assert raw_targets({BTC: low_vol}, Candidate.C)[0][BTC] == 1


def test_rebalance_threshold_uses_accepted_reference_target_not_daily_drift():
    values = [{BTC: x} for x in (0, 0.20, 0.25, 0.40, 0.50)]
    assert triggered_targets(values, Candidate.B) == [
        {BTC: 0},
        {BTC: 0},
        {BTC: 0.25},
        {BTC: 0.25},
        {BTC: 0.5},
    ]


def test_features_are_causal_and_ema_prefix_is_unchanged_by_future_rows():
    rows = candles(360, price_fn=lambda i: 100 + i + (i % 7) * 0.2)
    prefix = prepare(rows[:330])
    complete = prepare(rows)
    assert prefix.emas[200] == complete.emas[200][:330]
    assert prefix.annual_volatility == complete.annual_volatility[:330]
    assert complete.timestamps[329] == rows[329].ts


def test_alignment_splits_gaps_without_filtering_historical_grid_offsets():
    btc = candles(6)
    btc[3:] = [replace(row, ts=row.ts + 3600) for row in btc[3:]]
    eth = list(btc)
    segments = aligned_segments({BTC: btc, ETH: eth})
    assert [len(segment[BTC]) for segment in segments] == [3, 3]
    assert segments[0][BTC][-1].ts + DAY != segments[1][BTC][0].ts


def test_evaluator_accepts_every_segment_with_more_than_300_rows():
    first = {BTC: candles(301), ETH: candles(301)}
    second = {
        BTC: candles(302, start=1_800_000_000),
        ETH: candles(302, start=1_800_000_000),
    }
    items, observations = evaluate_segments([first, second])
    assert [item["number"] for item in items] == [0, 1]
    assert observations == 3


def test_matched_exposure_baseline_monthly_simulation_matches_requested_mean():
    rows = candles(370, start=1_704_067_200, price_fn=lambda _: 100)
    features = prepare(rows)
    item = {"number": 0, "data": {BTC: rows}, "features": {BTC: features}, "start": 300}
    weight, run, residual = matched_exposure([item], Candidate.A, 0, 0, 0.5)
    assert 0 <= weight <= 1
    assert abs(run.stats["average_exposure"] - 0.5) <= 0.0001
    assert abs(residual) <= 0.0001
    assert run.fills


def test_price_only_cost_accounting_includes_fee_and_adverse_slippage():
    rows = candles(302, price_fn=lambda _: 100)
    features = prepare(rows)
    item = {"number": 0, "data": {BTC: rows}, "features": {BTC: features}, "start": 300}
    run = simulate_constant([item], (BTC,), {BTC: 1}, 0.0025, 0.0015)
    assert len(run.fills) == 2
    assert run.stats["total_costs"] == pytest.approx(
        sum(fill.fee for fill in run.fills) + sum(fill.cost - fill.fee for fill in run.fills)
    )
    assert run.stats["total_costs"] > 0
    assert run.stats["gross_profit"] == pytest.approx(0, abs=1e-8)


def test_price_only_simulators_accept_decimal_configured_costs():
    rows = candles(302, price_fn=lambda _: 100)
    features = prepare(rows)
    item = {"number": 0, "data": {BTC: rows}, "features": {BTC: features}, "start": 300}
    result = simulate_constant([item], (BTC,), {BTC: 1}, D("0.0025"), D("0.0015"))
    assert result.stats["total_costs"] > 0


def test_unshifted_timing_null_reconstructs_open_returns_without_inventing_trades():
    rows = candles(303, price_fn=lambda _: 100)
    items, _ = evaluate_segments([{BTC: rows, ETH: list(rows)}])
    actual = simulate(items, Candidate.A, 0.0025, 0.0015)
    null = timing_null(items, Candidate.A, actual, 0.0025, 0.0015, trials=9)
    assert null["trials"] == 9
    assert null["unshifted_reconstruction"]["total_return"] == pytest.approx(0)
    assert null["reconstruction_return_error"] == pytest.approx(0)
    assert "share_net_return_ge_actual" in null
    assert null["share_net_return_ge_actual"] == pytest.approx(1)
    assert "share_net_return_ge_unshifted_reconstruction" not in null
    actual.stats["total_return"] = 0.01
    actual.stats["calmar"] = 1.0
    compared_to_actual = timing_null(items, Candidate.A, actual, 0.0025, 0.0015, trials=9)
    assert compared_to_actual["share_net_return_ge_actual"] == 0
    assert compared_to_actual["share_calmar_ge_actual"] == 0


def test_existing_timing_input_snapshot_is_never_overwritten(tmp_path):
    snapshot = tmp_path / "inputs"
    snapshot.mkdir()
    sentinel = snapshot / "preserve.txt"
    sentinel.write_text("frozen", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        save_inputs(snapshot, {}, [], {}, "test")
    assert sentinel.read_text(encoding="utf-8") == "frozen"
