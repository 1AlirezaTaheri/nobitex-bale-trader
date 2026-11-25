import socket
import time
from decimal import Decimal

import pytest

from app.config import AppConfig, RiskConfig, Settings, StrategyConfig, legacy_section, load_yaml
from data.store import Store
from exchange.base import Book, Candle, MarketData, Rules

D = Decimal


@pytest.fixture(autouse=True)
def offline_tests(monkeypatch):
    original_connect = socket.socket.connect

    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must never access a real network")

    def connect(sock, address):
        # Windows asyncio builds its internal socketpair over the loopback interface.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return forbidden(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setenv("MODE", "paper")


@pytest.fixture
def cfg():
    return StrategyConfig(**legacy_section("config/strategy.yaml"))


@pytest.fixture
def risk():
    return RiskConfig(**legacy_section("config/risk.yaml"))


@pytest.fixture
def app_cfg():
    return AppConfig(**load_yaml("config/app.yaml"))


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "state.db") as value:
        yield value


class Market(MarketData):
    def __init__(self):
        self.book = Book(int(time.time()), ((D("100"), D(10)),), ((D("100.1"), D(10)),))
        self.rules = Rules(D("0.000001"), D("0.01"), D("0.5"))
        self.rows: list[Candle] = []
        self.requests = []

    async def get_candles(self, symbol, frame, start, end):
        self.requests.append((start, end))
        return [c for c in self.rows if start <= c.ts < end]

    async def get_orderbook(self, symbol):
        return self.book

    async def get_symbol_rules(self, symbol):
        return self.rules


@pytest.fixture
def market():
    return Market()


def candles(count, step=14400, start=1800):
    return [
        Candle(start + i * step, 100 + i / 100, 102 + i / 100, 98 + i / 100, 100 + i / 100, 10)
        for i in range(count)
    ]
