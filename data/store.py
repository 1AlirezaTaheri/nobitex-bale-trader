import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from exchange.base import Candle


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS candles (
                symbol TEXT, frame TEXT, ts INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL,
                PRIMARY KEY (symbol, frame, ts));
            CREATE TABLE IF NOT EXISTS paper_orders (
                cid TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS intent (
                cid TEXT PRIMARY KEY, request TEXT NOT NULL, created INTEGER NOT NULL,
                state TEXT NOT NULL, result TEXT, reason TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_order_scope (cid TEXT PRIMARY KEY, symbol TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS intent_scope (cid TEXT PRIMARY KEY, symbol TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS portfolio_closure (
                seq INTEGER PRIMARY KEY, symbol TEXT NOT NULL, pnl TEXT NOT NULL, ts INTEGER NOT NULL);
        """)

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *args: object) -> None:
        self.db.close()

    def get(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def write(self, key: str, value: Any) -> None:
        """Write within the caller's transaction."""
        self.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value)))

    def set(self, key: str, value: Any) -> None:
        with self.db:
            self.write(key, value)

    def insert(self, symbol: str, frame: str, candles: list[Candle]) -> None:
        with self.db:
            self.db.executemany(
                "INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)",
                [(symbol, frame, c.ts, c.open, c.high, c.low, c.close, c.volume) for c in candles],
            )

    def candles(self, symbol: str, frame: str, start: int = 0, end: int = 2**62) -> list[Candle]:
        rows = self.db.execute(
            "SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND frame=? "
            "AND ts>=? AND ts<? ORDER BY ts",
            (symbol, frame, start, end),
        )
        return [Candle(*row) for row in rows]

    def history_end(self, symbol: str, frame: str) -> int | None:
        return self.db.execute(
            "SELECT max(ts) FROM candles WHERE symbol=? AND frame=?", (symbol, frame)
        ).fetchone()[0]


@contextmanager
def single_instance(path: Path) -> Iterator[None]:
    """OS lock is released on crash; keep the stable lock file, including after shutdown."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as file:
        if os.name == "nt":
            import msvcrt

            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
