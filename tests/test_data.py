import asyncio
import csv

import pytest

from data.history import History, boundary, fresh, latest_segment, ranges_missing, read_csv
from tests.conftest import candles


def test_boundary_is_exchange_grid_not_utc_four_hours():
    assert boundary(20000, 14400, 1800) == 16200
    assert boundary(16200, 14400, 1800) == 16200


def test_fresh_signal_excludes_unclosed_and_one_full_frame_old():
    row = candles(1)[0]
    assert not fresh(row, row.ts + 14399, 14400)
    assert fresh(row, row.ts + 14400, 14400)
    assert not fresh(row, row.ts + 28800, 14400)


def test_gap_ranges_and_last_contiguous_segment():
    rows = candles(8)
    damaged = rows[:2] + rows[4:]
    assert ranges_missing(damaged, rows[0].ts, rows[-1].ts + 14400, 14400) == [
        (rows[2].ts, rows[4].ts)
    ]
    assert latest_segment(damaged, 14400) == rows[4:]


def test_gap_rejects_off_grid_rows():
    rows = candles(2, start=100)
    with pytest.raises(ValueError):
        ranges_missing(rows, 0, 30000, 14400)


def test_startup_backfills_missing_window_idempotently(store, market, cfg):
    rows = candles(cfg.warmup)
    market.rows = rows
    store.insert(cfg.symbol, cfg.timeframe, rows[:20] + rows[30:])
    history = History(store, market, cfg, 1800)
    now = rows[-1].ts + cfg.seconds + 20
    result = asyncio.run(history.sync(now, 12))
    assert result.gaps_before == 1
    assert result.missing == []
    assert len(result.rows) == cfg.warmup
    assert market.requests == [(rows[20].ts, rows[30].ts)]
    asyncio.run(history.sync(now, 12))
    assert len(market.requests) == 1


def test_missing_history_keeps_safe_short_segment(store, market, cfg):
    rows = candles(cfg.warmup)
    market.rows = rows[-10:]
    history = History(store, market, cfg, 1800)
    result = asyncio.run(history.sync(rows[-1].ts + cfg.seconds + 20, 12))
    assert result.missing
    assert result.rows == rows[-10:]


def test_collection_filters_unclosed_candle(store, market, cfg):
    market.rows = candles(cfg.warmup + 1)
    history = History(store, market, cfg, 1800)
    result = asyncio.run(history.sync(market.rows[-1].ts + 50, 12))
    assert result.rows[-1] == market.rows[-2]


def test_csv_import_and_future_rejection(tmp_path):
    path = tmp_path / "candles.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow([1800, 100, 102, 99, 101, 5])
    assert len(read_csv(path, 14400, 20000)) == 1
    with pytest.raises(ValueError):
        read_csv(path, 14400, 1900)


def test_sqlite_cache_persists_exact_timestamps(store, cfg):
    rows = candles(4)
    store.insert(cfg.symbol, cfg.timeframe, rows)
    store.insert(cfg.symbol, cfg.timeframe, rows)
    assert store.candles(cfg.symbol, cfg.timeframe) == rows


def test_downtime_longer_than_warmup_backfills_entire_gap(store, market, cfg):
    rows = candles(cfg.warmup + 700)
    market.rows = rows
    store.insert(cfg.symbol, cfg.timeframe, rows[:5])
    history = History(store, market, cfg, 1800)
    result = asyncio.run(history.sync(rows[-1].ts + cfg.seconds + 20, 12))
    assert not result.missing
    assert len(result.rows) == cfg.warmup
    assert store.candles(cfg.symbol, cfg.timeframe) == rows


def test_history_downloader_preserves_historical_grid_without_relabeling(store, market, cfg):
    rows = candles(10, start=3600)
    market.rows = rows
    history = History(store, market, cfg, 1800)
    asyncio.run(history.fetch(1800, rows[-1].ts + cfg.seconds, strict_grid=False))
    assert store.candles(cfg.symbol, cfg.timeframe) == rows


def test_process_lock_refuses_second_instance_and_releases(tmp_path):
    from data.store import single_instance

    path = tmp_path / "bot.lock"
    with single_instance(path):
        with pytest.raises(OSError):
            with single_instance(path):
                raise AssertionError("Second lock must not succeed")
    with single_instance(path):
        assert path.exists()


def test_history_stop_prevents_even_public_network_request(store, market, cfg):
    from exchange.base import ExchangeError

    history = History(store, market, cfg, 1800)
    history.halted = lambda: True
    with pytest.raises(ExchangeError, match="shutdown"):
        asyncio.run(history.fetch(1800, 16200))
    assert not market.requests
