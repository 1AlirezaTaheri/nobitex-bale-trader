from dataclasses import replace
from decimal import Decimal

import numpy as np
import pytest

from backtest import final_audit_core as core
from backtest.timing_v3 import evaluate_segments
from backtest.timing_v3 import simulate as frozen_simulate
from exchange.base import Candle


def fixture_item(count=370, start=300, fn=None, number=0):
    values = []
    for i in range(count):
        price = fn(i) if fn else 100.0
        values.append(
            Candle(1704067200 + i * core.DAY, price, price * 1.01, price * 0.99, price, 10)
        )
    items, _ = evaluate_segments([{core.BTC: values, core.ETH: list(values)}])
    return {**items[0], "start": start, "number": number}


def test_flat_roundtrip_has_no_gross_profit_and_includes_costs():
    rows, fills = core.simulate([fixture_item()], "hold", fee=Decimal(".0025"))
    m = core.metrics(rows)
    assert len(fills) == 2
    assert m["gross_profit"] == pytest.approx(0, abs=1e-10)
    assert m["total_costs"] == pytest.approx(sum(f["cost"] for f in fills))
    assert m["final_equity"] == pytest.approx(
        100 * (1 - 0.0015) * (1 - 0.0025) / (1 + 0.0015) / (1 + 0.0025)
    )


def test_prefunded_dca_equal_monthly_outlay_no_external_cash():
    item = fixture_item(count=390)
    rows, fills = core.simulate([item], "dca")
    buys = [f for f in fills if f["side"] == "buy"]
    months = {core.month(r["timestamp"]) for r in rows}
    assert len(buys) == len(months)
    payments = [b["qty"] * 100 + b["cost"] for b in buys]
    assert payments == pytest.approx([100 / len(months)] * len(months))
    assert sum(payments) == pytest.approx(100)
    assert rows[-1]["equity"] < 100


def test_drift_band_prevents_small_monthly_rebalances():
    item = fixture_item(count=390, fn=lambda i: 100 + 0.01 * i)
    _, banded = core.simulate([item], "mix", weight=0.25, band=0.05)
    _, unbanded = core.simulate([item], "mix", weight=0.25, band=0)
    assert len(banded) == 2
    assert len(unbanded) > 2


def test_monthly_rebalances_large_drift_only_on_month_boundaries():
    item = fixture_item(count=390, fn=lambda i: 100 * 1.03 ** (i - 300) if i >= 300 else 100)
    rows, fills = core.simulate([item], "mix", weight=0.25, band=0.05)
    allowed = {rows[0]["timestamp"], rows[-1]["timestamp"] + core.DAY}
    allowed.update(
        b["timestamp"]
        for a, b in zip(rows, rows[1:])
        if core.month(a["timestamp"]) != core.month(b["timestamp"])
    )
    assert len(fills) > 2
    assert all(f["timestamp"] in allowed for f in fills)


@pytest.mark.parametrize("candidate", list("ABCD"))
def test_new_adapter_matches_unchanged_v3(candidate):
    item = fixture_item(count=430, fn=lambda i: 100 * np.exp(0.001 * i + 0.1 * np.sin(i / 11)))
    paths = {0: core.target_path(item, candidate)}
    rows, fills = core.simulate(
        [item],
        "targets",
        paths=paths,
        symbols=(core.BTC, core.ETH) if candidate == "D" else (core.BTC,),
    )
    frozen = frozen_simulate([item], candidate, 0.0025, 0.0015)
    assert [r["return"] for r in rows] == pytest.approx(
        [r["return"] for r in frozen.rows], abs=1e-12
    )
    assert sum(f["cost"] for f in fills) == pytest.approx(frozen.stats["total_costs"])


def test_simulation_refuses_gap_and_misaligned_asset():
    item = fixture_item()
    item["data"][core.BTC][310] = replace(item["data"][core.BTC][310], ts=1)
    with pytest.raises(ValueError, match="contiguous"):
        core.simulate([item], "hold")


def test_segment_reset_carries_equity_but_not_holdings():
    one = fixture_item(number=0)
    two = fixture_item(number=1)
    a, _ = core.simulate([one], "hold")
    both, _ = core.simulate([one, two], "hold")
    assert both[-1]["equity"] == pytest.approx(a[-1]["equity"] ** 2 / 100)
    assert both[len(a)]["cost"] == pytest.approx(a[0]["cost"] * a[-1]["equity"] / 100)


def test_rolling_never_bridges_segments_and_matches_known_return():
    rows = [{"timestamp": i, "return": 0.001, "segment": i // 5} for i in range(10)]
    windows = core.rolling(rows, 4)
    assert len(windows) == 4
    assert all(w["return"] == pytest.approx(1.001**4 - 1) for w in windows)
    assert core.rolling(rows, 6) == []


def test_bootstrap_deterministic_paired_and_resolution_limited():
    rows, _ = core.simulate([fixture_item()], "hold")
    a, _ = core.bootstrap(rows, {"same": rows}, 250, trials=19)
    b, _ = core.bootstrap(rows, {"same": rows}, 250, trials=19)
    assert a == b
    assert a["blocks"]["20"]["differences"]["same"]["sharpe"]["ci95"] == [0.0, 0.0]
    assert a["blocks"]["20"]["differences"]["same"]["sharpe"]["p_bonferroni"] == 1
    idx = core.block_indices([0] * 5 + [1] * 5, 10, 3, trials=3)
    assert np.array_equal(idx, core.block_indices([0] * 5 + [1] * 5, 10, 3, trials=3))
    assert not idx.flags.writeable


def test_cash_undefined_ratios_remain_null():
    rows, _ = core.simulate([fixture_item()], "cash")
    stats = core.metrics(rows)
    assert stats["total_return"] == 0
    assert stats["sharpe"] is None
    assert stats["calmar"] is None
    assert stats["costs_pct_gross_profit"] is None


def test_regimes_no_future_leakage():
    item = fixture_item(count=410, fn=lambda i: 100 + i)
    bars = item["data"][core.BTC]
    assert core.regimes(bars[:370]) == core.regimes(bars)[:370]
    assert core.regimes(bars)[300] == "bull"


def test_sma_uses_prior_close_and_does_not_see_current_close():
    item = fixture_item(count=310, fn=lambda i: 100 if i < 300 else 200)
    rows, _ = core.simulate([item], "sma")
    assert rows[0]["exposure"] == 0
    assert rows[1]["exposure"] > 0


def test_null_reconstruction_discloses_and_preserves_total_return():
    item = fixture_item(count=330, fn=lambda i: 100 + i * 0.1)
    rows, _ = core.simulate([item], "mix", weight=0.5)
    result = core.timing_null([item], rows, trials=9)
    assert result["unshifted_return_error"] == pytest.approx(0, abs=1e-10)
    assert "surrogate" in result["warning"]


def test_baseline_delay_defers_first_purchase_without_inventing_rows():
    item = fixture_item(count=310, fn=lambda i: 100 if i < 301 else 120)
    immediate, _ = core.simulate([item], "hold")
    delayed, fills = core.simulate([item], "hold", execution_delay=1)
    assert delayed[0]["exposure"] == 0
    assert delayed[1]["exposure"] > 0
    assert fills[0]["timestamp"] == delayed[1]["timestamp"]
    assert len(immediate) == len(delayed)


def test_exposure_fit_and_omitted_sleeve_stays_cash():
    from backtest.final_audit import fit_match, run_spec

    item = fixture_item()
    weight, rows, residual = fit_match([item], 0.4, (core.BTC,), 0.0025, 0.0015)
    assert abs(residual) < 1e-8
    assert 0 < weight < 1
    omitted = run_spec(
        [item],
        ("mix", {"weight": 0.5, "symbols": (core.BTC, core.ETH), "band": 0.05}),
        0.0025,
        0.0015,
        omit=core.ETH,
    )
    assert omitted[0]["exposure"] == pytest.approx(0.25, abs=0.001)
    assert core.ETH not in omitted[0]["weights"]


def test_snapshot_checksum_refusal_and_output_confinement(tmp_path):
    from backtest.final_audit import confined, read_snapshot, write_json

    write_json(tmp_path / "manifest.json", {"files": {"fake.csv": "bad"}})
    (tmp_path / "fake.csv").write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        read_snapshot(tmp_path)
    with pytest.raises(ValueError, match="under"):
        confined(tmp_path)


def test_start_sensitivity_fresh_cash_each_date_and_all_dates():
    from backtest.final_audit import start_sensitivity

    item = fixture_item(count=306, fn=lambda i: 100 + i)
    rows = start_sensitivity([item], ("hold", {}), 0.0025, 0.0015)
    assert len(rows) == 6
    assert [r["days"] for r in rows] == [6, 5, 4, 3, 2, 1]
    assert all(r["return"] < 0.1 for r in rows)


def test_chart_series_color_is_stable_across_unconnected_segments(tmp_path, monkeypatch):
    from matplotlib.axes import Axes

    from backtest.final_audit import figures

    colors = []
    original = Axes.plot

    def capture(self, *args, **kwargs):
        colors.append(kwargs.get("color"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", capture)
    series = {
        "S2_A": [
            {"segment": i // 2, "timestamp": 1704067200 + i * core.DAY, "equity": 100 + i}
            for i in range(4)
        ]
    }
    rolling = {
        "S2_A": [{"segment": i, "end": 1704067200 + i * core.DAY, "return": 0.01} for i in range(2)]
    }
    figures(tmp_path / "charts", series, rolling, {}, [])
    assert len(colors) == 6
    assert all(color == colors[0] and color is not None for color in colors)
