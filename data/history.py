import csv
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from data.store import Store
from exchange.base import Candle, ExchangeError, MarketData


def boundary(now: int, step: int, offset: int) -> int:
    return (now - offset) // step * step + offset


def ranges_missing(rows: list[Candle], start: int, end: int, step: int) -> list[tuple[int, int]]:
    cursor, missing = start, []
    for row in rows:
        if row.ts < cursor or row.ts >= end or (row.ts - start) % step:
            raise ValueError("Duplicate, unordered or off-grid candle")
        if row.ts > cursor:
            missing.append((cursor, row.ts))
        cursor = row.ts + step
    if cursor < end:
        missing.append((cursor, end))
    return missing


def latest_segment(rows: list[Candle], step: int) -> list[Candle]:
    for i in range(len(rows) - 1, 0, -1):
        if rows[i].ts - rows[i - 1].ts != step:
            return rows[i:]
    return rows


def fresh(candle: Candle, now: int, step: int) -> bool:
    return 0 <= now - candle.ts - step < step


@dataclass(frozen=True)
class Sync:
    rows: list[Candle]
    missing: list[tuple[int, int]]
    gaps_before: int
    end: int


class HistoryConfig(Protocol):
    @property
    def symbol(self) -> str: ...
    @property
    def timeframe(self) -> str: ...
    @property
    def seconds(self) -> int: ...
    @property
    def warmup(self) -> int: ...


class History:
    def __init__(
        self, store: Store, market: MarketData, config: HistoryConfig, offset: int, page: int = 500
    ):
        self.store, self.market, self.config, self.offset, self.page = (
            store,
            market,
            config,
            offset,
            page,
        )
        self.halted: Callable[[], bool] = lambda: False

    async def fetch(self, start: int, end: int, *, strict_grid: bool = True) -> list[Candle]:
        cfg = self.config
        if self.halted():
            raise ExchangeError("Candle collection interrupted by shutdown")
        rows = await self.market.get_candles(cfg.symbol, cfg.timeframe, start, end)
        if self.halted():
            raise ExchangeError("Candle collection interrupted by shutdown")
        if strict_grid:
            try:
                ranges_missing(rows, start, end, cfg.seconds)
            except ValueError:
                raise ExchangeError(
                    "Nobitex candle grid changed or response is inconsistent"
                ) from None
        self.store.insert(cfg.symbol, cfg.timeframe, rows)
        return rows

    async def sync(self, now: int, grace: int) -> Sync:
        c = self.config
        end = boundary(now - grace, c.seconds, self.offset)
        start = end - c.warmup * c.seconds
        previous_end = self.store.history_end(c.symbol, c.timeframe)
        if (
            previous_end is not None
            and previous_end < start
            and (previous_end - self.offset) % c.seconds == 0
        ):
            start = previous_end + c.seconds
        rows = self.store.candles(c.symbol, c.timeframe, start, end)
        missing = ranges_missing(rows, start, end, c.seconds)
        size = self.page * c.seconds
        for low, high in reversed(missing):
            for cursor in range(low, high, size):
                await self.fetch(cursor, min(cursor + size, high))
        rows = self.store.candles(c.symbol, c.timeframe, start, end)
        remaining = ranges_missing(rows, start, end, c.seconds)
        recent = [row for row in rows if row.ts >= end - c.warmup * c.seconds]
        recent_missing = ranges_missing(recent, end - c.warmup * c.seconds, end, c.seconds)
        return Sync(
            latest_segment(recent, c.seconds), recent_missing or remaining, len(missing), end
        )

    async def download(self, now: int, max_pages: int) -> tuple[int, int, str]:
        size = self.page * self.config.seconds
        end = boundary(now, self.config.seconds, self.offset)
        downloaded = 0
        empty = 0
        for page in range(1, max_pages + 1):
            rows = await self.fetch(end - size, end, strict_grid=False)
            print(f"History window {page}: {len(rows)} closed candles", flush=True)
            downloaded += len(rows)
            empty = 0 if rows else empty + 1
            if empty == 2:
                return downloaded, page, "two consecutive empty windows"
            end -= size
        return downloaded, max_pages, "configured page ceiling; earlier history may exist"


def read_csv(path: Path, step: int, now: int) -> list[Candle]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = sorted(
            (
                Candle(
                    int(row["timestamp"]),
                    *(float(row[key]) for key in ("open", "high", "low", "close", "volume")),
                )
                for row in csv.DictReader(file)
            ),
            key=lambda c: c.ts,
        )
    if not rows or rows[-1].ts + step > now or len({c.ts for c in rows}) != len(rows):
        raise ValueError("CSV must contain unique closed candles using Unix seconds")
    return rows
