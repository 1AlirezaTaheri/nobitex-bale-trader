import json
from decimal import Decimal as D

import pytest

from app.config import StrategyConfig, legacy_section
from backtest.portfolio_run import checks, load_inputs, save_inputs
from exchange.base import Rules
from tests.test_layered import SYMBOLS, bars


def metrics(**values):
    return {
        "total_return": 0.2,
        "trades": 100,
        "profit_factor": 1.4,
        "max_drawdown": -0.1,
        "calmar": 2.0,
        **values,
    }


def test_eight_acceptance_criteria_and_fragility_are_not_relaxed():
    base = metrics()
    verdict = checks(
        base,
        base,
        base,
        metrics(calmar=1),
        [metrics(total_return=0.11)],
        metrics(),
        metrics(max_drawdown=-0.2),
    )
    assert len(verdict) == 8 and all(verdict.values())
    assert not all(
        checks(metrics(trades=99), base, base, metrics(calmar=1), [base], base, base).values()
    )
    verdict = checks(base, base, base, metrics(calmar=1), [metrics(total_return=0.09)], base, base)
    assert not verdict["Robust to +/-20% perturbations"]
    verdict = checks(
        base,
        metrics(total_return=-0.01),
        metrics(total_return=0),
        metrics(calmar=1),
        [base],
        base,
        base,
    )
    assert sum(not x for x in verdict.values()) == 2


def test_snapshot_hash_and_raw_timestamps_replay_then_tamper_refused(tmp_path):
    data = {s: bars(4) for s in SYMBOLS}
    rules = {s: Rules(D(".001"), D(".01"), D(".5")) for s in SYMBOLS}
    save_inputs(tmp_path, data, [], rules, {}, {"policy": "test"})
    folder = tmp_path / "inputs"
    legacy_cfg = StrategyConfig(**legacy_section("config/strategy.yaml"))
    loaded, _, _, _, _ = load_inputs(folder, SYMBOLS, "longest", legacy_cfg, 10**9)
    assert loaded == data
    manifest = json.loads((folder / "manifest.json").read_text())
    file = folder / manifest["files"]["BTC/USDT"]["file"]
    file.write_text(file.read_text() + "\n")
    with pytest.raises(ValueError, match="checksum"):
        load_inputs(folder, SYMBOLS, "longest", legacy_cfg, 10**9)
