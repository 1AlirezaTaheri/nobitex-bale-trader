import copy
import json
import sqlite3

import pytest

from app import forward_report as report
from app import forward_shadow as f
from exchange.base import Candle


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "BASE", tmp_path)
    monkeypatch.setattr(report, "BASE", tmp_path)
    config = f.config_for({"not_before": 0, "audit_sha256": "test", "v3_sha256": "test"}, 0.0025)
    root = tmp_path / "shadow"
    return root, config


def warmup(ts, count=305):
    return {
        s: [Candle(ts - (count - i) * f.DAY, 100.0, 101.0, 99.0, 100.0, 1.0) for i in range(count)]
        for s in f.SYMBOLS
    }


def append(ledger, ts):
    bars = warmup(ts)
    old = ledger.records[-1] if ledger.records else None
    p = f.observation(ledger.config, old, ts, ts + 2, bars, dict.fromkeys(f.SYMBOLS, 100.0))
    f.cache_warmup(ledger.root, ts, bars)
    return ledger.append(p)


def test_snapshot_hash_chain_idempotency_and_conflicting_overwrite(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    first = append(ledger, 1735689600)
    assert first["hash"] == f.hashed(first["payload"])
    second = append(ledger, 1735689600 + f.DAY)
    assert second["payload"]["previous_hash"] == first["hash"]
    assert len(f.load_chain(root)) == 2
    with pytest.raises(FileExistsError):
        f.exclusive_json(root / "snapshots" / "snapshot_1735689600.json", {})
    ledger.close()
    restored = f.Ledger(root, config)
    assert len(restored.records) == 2
    restored.close()


def test_gap_flagging_never_backfills_trades_and_retains_economic_loss(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    first = append(ledger, 1735689600)
    ts = 1735689600 + 3 * f.DAY
    bars = warmup(ts)
    p = f.observation(config, first, ts, ts + 1, bars, dict.fromkeys(f.SYMBOLS, 50.0))
    assert p["missing_boundaries"] == [1735689600 + f.DAY, 1735689600 + 2 * f.DAY]
    assert p["interrupted"]
    assert p["returns"]["B1"]["clean_observed_return"] is None
    assert p["returns"]["B1"]["economic_mark_return"] < -0.49
    assert p["fills"]["B1"] == []
    ledger.append(p)
    assert len(ledger.records) == 2
    s, _ = report.summarize(root)
    assert s["interrupted"]
    assert s["observed_intervals"] == 0
    ledger.close()


@pytest.mark.parametrize("skew", [-1, 61, 3600])
def test_stale_and_skewed_boundary_refusal(setup, skew):
    _, config = setup
    ts = 1735689600
    with pytest.raises(ValueError, match="Clock skew"):
        f.observation(config, None, ts, ts + skew, warmup(ts), dict.fromkeys(f.SYMBOLS, 100.0))


def test_backwards_duplicate_and_gapped_warmup_refusal(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    old = append(ledger, 1735689600)
    with pytest.raises(ValueError, match="Duplicate"):
        f.observation(
            config, old, 1735689600, 1735689601, warmup(1735689600), dict.fromkeys(f.SYMBOLS, 100.0)
        )
    bars = warmup(1735689600 + f.DAY)
    bars[f.SYMBOLS[0]].pop(200)
    with pytest.raises(ValueError, match="contiguous"):
        f.observation(
            config,
            old,
            1735689600 + f.DAY,
            1735689600 + f.DAY + 1,
            bars,
            dict.fromkeys(f.SYMBOLS, 100.0),
        )
    ledger.close()


def test_db_recovery_after_snapshot_before_db_commit(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    append(ledger, 1735689600)
    with ledger.db:
        ledger.db.execute("DELETE FROM snapshot")
    ledger.close()
    restored = f.Ledger(root, config)
    assert restored.db.execute("SELECT count(*) FROM snapshot").fetchone()[0] == 1
    restored.close()


def test_db_tamper_and_configuration_change_refusal(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    append(ledger, 1735689600)
    with ledger.db:
        ledger.db.execute("UPDATE snapshot SET hash='changed'")
    ledger.close()
    with pytest.raises(ValueError, match="mismatch"):
        f.Ledger(root, config)
    altered = copy.deepcopy(config)
    altered["slippage"] *= 2
    with pytest.raises(ValueError, match="configuration changed"):
        f.Ledger(root, altered)


def test_hash_tamper_and_snapshot_deletion_are_detected(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    append(ledger, 1735689600)
    append(ledger, 1735689600 + f.DAY)
    ledger.close()
    p = root / "snapshots" / "snapshot_1735689600.json"
    value = json.loads(p.read_bytes())
    value["payload"]["accounts"]["A"]["cash"] += 1
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="hash chain"):
        f.load_chain(root)
    p.unlink()
    with pytest.raises(ValueError):
        f.load_chain(root)


def test_corrupted_and_locked_sqlite_refuse(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    ledger.close()
    lock = sqlite3.connect(root / "shadow.db")
    lock.execute("BEGIN EXCLUSIVE")
    # WAL readers can read during a lock; any append must refuse the locked writer.
    second = f.Ledger(root, config)
    with pytest.raises(sqlite3.OperationalError):
        append(second, 1735689600)
    second.close()
    lock.rollback()
    lock.close()
    # The file written before the failed DB commit is intentionally recoverable.
    recovered = f.Ledger(root, config)
    assert len(recovered.records) == 1
    recovered.close()
    (root / "shadow.db").write_bytes(b"not a database")
    with pytest.raises(sqlite3.DatabaseError):
        f.Ledger(root, config)


def test_forward_dca_budget_and_causal_B7(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    first = append(ledger, 1735689600)
    assert first["payload"]["accounts"]["B3"]["cash"] == pytest.approx(100 - 100 / 12)
    assert first["payload"]["accounts"]["B7_A"]["exposure"] == 0
    assert first["payload"]["accounts"]["B4_25"]["exposure"] == pytest.approx(0.25, abs=0.001)
    second = append(ledger, 1735689600 + f.DAY)
    assert second["payload"]["fills"]["B3"] == []
    ledger.close()


def test_cached_closed_candle_revision_refusal(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    prior = append(ledger, 1735689600)
    bars = warmup(1735689600 + f.DAY)
    retained = f.retained_warmup(root, prior, bars)
    assert len(retained[f.SYMBOLS[0]]) == 306
    bars[f.SYMBOLS[0]][100] = Candle(bars[f.SYMBOLS[0]][100].ts, 90, 101, 89, 100, 1)
    with pytest.raises(ValueError, match="revised"):
        f.retained_warmup(root, prior, bars)
    ledger.close()


def test_weekly_generation_empty_and_existing_output_refusal(setup):
    root, config = setup
    out = root.parent / "weekly"
    s = report.generate(root, out)
    assert s["snapshots"] == 0
    assert "Weaknesses FIRST" in (out / "weekly.md").read_text()
    assert s["checkpoints"]["3"]["candidates"]["A"]["status"] == "PENDING"
    with pytest.raises(ValueError):
        report.generate(root, out)


def test_fixed_checkpoint_cannot_pass_flat_zero_gross_or_interrupted(setup):
    root, config = setup
    ledger = f.Ledger(root, config)
    for i in range(92):
        if i != 10:
            append(ledger, 1735689600 + i * f.DAY)
    ledger.close()
    s, _ = report.summarize(root)
    assert s["checkpoints"]["3"]["candidates"]["A"]["status"] == "FAIL_NOT_VALIDATED"
    assert not s["checkpoints"]["3"]["candidates"]["A"]["checks"]["uninterrupted"]


def test_report_calendar_month_end():
    from datetime import UTC, datetime

    ts = int(datetime(2025, 1, 31, tzinfo=UTC).timestamp())
    assert datetime.fromtimestamp(report.months_after(ts, 1), UTC).day == 28


def test_report_stopped_run_becomes_due_without_a_new_snapshot(setup, monkeypatch):
    root, config = setup
    first = 1735689600
    ledger = f.Ledger(root, config)
    append(ledger, first)
    ledger.close()
    due = report.months_after(first, 3)
    monkeypatch.setattr(report.time, "time", lambda: due + 61)
    s, _ = report.summarize(root)
    assert s["interrupted"]
    assert s["outstanding_missed_boundaries_after_last_snapshot"][-1] == due
    assert s["checkpoints"]["3"]["candidates"]["A"]["status"] == "FAIL_NOT_VALIDATED"
    assert not s["checkpoints"]["3"]["candidates"]["A"]["checks"]["uninterrupted"]
    assert s["checkpoints"]["6"]["candidates"]["A"]["status"] == "PENDING"


def test_report_boundary_grace_and_backwards_clock(setup):
    root, config = setup
    first = 1735689600
    ledger = f.Ledger(root, config)
    append(ledger, first)
    ledger.close()
    s, _ = report.summarize(root, as_of=first + f.DAY + 60)
    assert not s["outstanding_missed_boundaries_after_last_snapshot"]
    s, _ = report.summarize(root, as_of=first + f.DAY + 61)
    assert s["outstanding_missed_boundaries_after_last_snapshot"] == [first + f.DAY]
    with pytest.raises(ValueError, match="clock predates"):
        report.summarize(root, as_of=first - 1)


def test_gap_reported_after_due_still_invalidates_that_checkpoint(setup):
    root, config = setup
    first = 1735689600
    ledger = f.Ledger(root, config)
    for i in range(90):
        append(ledger, first + i * f.DAY)
    append(ledger, first + 92 * f.DAY)
    ledger.close()
    s, _ = report.summarize(root, as_of=first + 92 * f.DAY + 2)
    c = s["checkpoints"]["3"]["candidates"]["A"]
    assert c["checks"]["minimum_days"]
    assert not c["checks"]["uninterrupted"]
    assert c["status"] == "FAIL_NOT_VALIDATED"


def test_local_KILL_during_activity_stops_shadow_loop(setup, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    root, config = setup
    monkeypatch.setattr(f, "registration", lambda now: config["registration"])

    class PublicMock:
        def __init__(self, *args):
            pass

        async def get_fees(self, symbol):
            root.mkdir(parents=True, exist_ok=True)
            (root / "KILL").touch()
            return 0.0025

    monkeypatch.setattr(f, "NobitexClient", PublicMock)
    args = SimpleNamespace(mode="shadow", root=root, max_seconds=0.1)
    assert asyncio.run(f.run(args)) == 0
    assert not list((root / "snapshots").glob("*.json"))


def test_shadow_live_refusal_occurs_before_registration_or_transport(setup, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    root, _ = setup
    monkeypatch.setattr(f, "registration", lambda *_: pytest.fail("registration should not run"))
    with pytest.raises(ValueError, match="LIVE refused"):
        asyncio.run(f.run(SimpleNamespace(mode="live", root=root, max_seconds=1)))


def test_not_before_clock_gate_is_fail_closed(monkeypatch):
    with pytest.raises(ValueError, match="clock predates"):
        f.registration(0)


def test_sequential_shadow_A_D_targets_match_frozen_strategy(setup):
    import math

    from strategy.timing import prepare, targets_for

    root, config = setup
    ts = 1735689600
    allbars = {
        s: [
            Candle(
                ts + (i - 305) * f.DAY,
                100 + 3 * math.sin(i / 5) + i * 0.1,
                105 + i * 0.1,
                95 + i * 0.1,
                100 + 3 * math.sin(i / 5) + i * 0.1,
                1.0,
            )
            for i in range(315)
        ]
        for s in f.SYMBOLS
    }
    expected = {
        name: targets_for({s: prepare(bars) for s, bars in allbars.items()}, name, start_index=304)
        for name in ("A", "D")
    }
    ledger = f.Ledger(root, config)
    for k in range(10):
        stamp = ts + k * f.DAY
        prior = ledger.records[-1] if ledger.records else None
        p = f.observation(
            config,
            prior,
            stamp,
            stamp + 1,
            {s: v[: 305 + k] for s, v in allbars.items()},
            dict.fromkeys(f.SYMBOLS, 100.0),
        )
        for name in ("A", "D"):
            for s in f.SYMBOLS:
                assert p["accounts"][name]["accepted"][s] == pytest.approx(
                    expected[name][304 + k].get(s, 0.0)
                )
        ledger.append(p)
    ledger.close()
