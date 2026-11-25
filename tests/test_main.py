import asyncio

import pytest

from app import main as runner
from app.config import ConfigError
from app.engine import Engine
from data.store import Store
from exchange.base import Candle
from notify import BaleNotifier


@pytest.mark.parametrize("failure", ["shutdown", "control"])
def test_runner_reports_failure_and_still_reconciles(
    failure, monkeypatch, tmp_path, settings, cfg, risk, app_cfg, market
):
    """Control-task exceptions must not skip the financial shutdown path."""
    calls = []

    class TestEngine(Engine):
        async def tick(self, now):
            self.data_ready = True
            # Let the control task reach its failing outcome before cleanup.
            await asyncio.sleep(0)
            self.stop.set()

        async def shutdown(self):
            calls.append("shutdown")
            clean = await super().shutdown()
            return False if failure == "shutdown" else clean

    async def fees(symbol):
        return risk.fee

    async def failed_poll(self, *args):
        raise RuntimeError("Mock control failure")

    async def silent_send(self, message):
        pass

    if failure == "control":
        settings = type(settings)(_env_file=None, bale_bot_token="test-token", bale_chat_id=777)
        monkeypatch.setattr(BaleNotifier, "poll", failed_poll)
        monkeypatch.setattr(BaleNotifier, "send", silent_send)
    monkeypatch.setattr(market, "get_fees", fees, raising=False)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "load", lambda: (settings, cfg, risk, app_cfg))
    monkeypatch.setattr(runner, "NobitexClient", lambda *args: market)
    monkeypatch.setattr(runner, "Engine", TestEngine)
    monkeypatch.setattr(runner, "install_signals", lambda engine: lambda: None)

    assert asyncio.run(runner.run(10)) == 1
    assert calls == ["shutdown"]
    with Store(tmp_path / app_cfg.data_directory / "paper.db") as store:
        assert store.get("clean_stop") is True


@pytest.mark.parametrize(
    "flags", [{"timing_candidate": "B"}, {"timing_paper": True, "portfolio_paper": True}]
)
def test_timing_selection_refused_before_transport(
    monkeypatch, settings, cfg, risk, app_cfg, flags
):
    monkeypatch.setattr(runner, "load", lambda: (settings, cfg, risk, app_cfg))
    monkeypatch.setattr(runner, "NobitexClient", lambda *args: pytest.fail("transport opened"))
    with pytest.raises(ConfigError):
        asyncio.run(runner.run(10, **flags))


def test_timing_live_refused_before_transport(monkeypatch, settings, cfg, risk, app_cfg):
    live = settings.model_copy(update={"mode": "live"})
    monkeypatch.setattr(runner, "load", lambda: (live, cfg, risk, app_cfg))
    monkeypatch.setattr(runner, "NobitexClient", lambda *args: pytest.fail("transport opened"))
    with pytest.raises(ConfigError, match="LIVE is blocked"):
        asyncio.run(runner.run(10, timing_paper=True))


def test_explicit_timing_d_routes_to_separate_state_and_cache(
    monkeypatch, tmp_path, settings, cfg, risk, app_cfg, market
):
    directory = tmp_path / app_cfg.data_directory
    symbols = ("BTC/USDT", "ETH/USDT")
    candle = Candle(73800, 100, 101, 99, 100, 1)
    with Store(directory / "candles.db") as store:
        store.insert(symbols[0], "1d", [candle])
    with Store(directory / "paper.db") as store:
        store.set("legacy_sentinel", True)
    tracked = (directory / "paper.db", directory / "candles.db")
    before = [path.read_bytes() for path in tracked]

    class OneTick(runner.TimingEngine):
        async def tick(self, now):
            assert self.symbols == self.exchange.symbols == symbols
            assert self.exchange.allow_additions
            cache = self.histories[symbols[0]].store
            assert cache.candles(symbols[0], "1d") == [candle]
            cache.insert(symbols[1], "1d", [candle])
            self.data_ready = True
            self.stop.set()

    async def fees(symbol):
        return risk.fee

    monkeypatch.setattr(market, "get_fees", fees, raising=False)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "load", lambda: (settings, cfg, risk, app_cfg))
    monkeypatch.setattr(runner, "NobitexClient", lambda *args: market)
    monkeypatch.setattr(runner, "TimingEngine", OneTick)
    monkeypatch.setattr(runner, "Engine", lambda *args: pytest.fail("legacy route selected"))
    monkeypatch.setattr(runner, "install_signals", lambda engine: lambda: None)
    assert asyncio.run(runner.run(10, timing_paper=True, timing_candidate="D")) == 0
    assert [path.read_bytes() for path in tracked] == before
    assert not (directory / "portfolio_paper.db").exists()
    with Store(directory / "timing_v3_D_paper.db") as state:
        assert state.get("clean_stop") is True
        assert set(state.get("paper_wallet")) == {"USDT", "BTC", "ETH"}
    with Store(directory / "timing_v3_candles.db") as cache:
        assert cache.candles(symbols[1], "1d") == [candle]
