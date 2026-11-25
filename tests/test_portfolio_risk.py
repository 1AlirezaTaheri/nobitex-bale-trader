from dataclasses import replace
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.portfolio_config import Universe, load_portfolio
from exchange.base import Rules
from risk.portfolio import PortfolioLimits, PortfolioRisk, held_correlation, open_risk, quantity
from strategy.layered import DAY, Entry, Layer, LayeredConfig, Lot

NOW = 73800 + 100 * DAY


def state(equity=100):
    s = PortfolioRisk()
    s.observe(PortfolioLimits(), D(equity), NOW)
    return s


def sized(cfg=None, risk=None, lots=None, cash=D(100), rules=None, entry=None, returns=None):
    return quantity(
        cfg or PortfolioLimits(),
        risk or state(),
        NOW,
        entry or Entry("BTC/USDT", Layer.TREND, D(6)),
        lots or {},
        {s: D(100) for s in (lots or {})},
        cash,
        D(100),
        D(100),
        rules or Rules(D(".0001"), D(".01"), D(".5")),
        D(".0025"),
        D(".0015"),
        returns or {},
    )


def test_fee_aware_risk_asset_cap_and_minimum_tick():
    q = sized()
    assert q % D(".0001") == 0
    assert q * D(100) * D("1.0025") <= 25
    risk = q * (D("100.25") - D(94) * D(".9985") * D(".9975"))
    assert risk <= D(".75")
    assert sized(rules=Rules(D(1), D(1), D(50))) == 0
    assert sized(cash=D(".1")) == 0


def test_total_open_risk_and_sleeve_budgets_and_duplicate_symbol():
    lots = {s: Lot(s, Layer.PULLBACK, D(".3"), D(30), D(90), NOW) for s in ("ETH/USDT", "SOL/USDT")}
    assert sized(lots=lots) == 0
    assert sized(lots={"BTC/USDT": replace(lots["ETH/USDT"], symbol="BTC/USDT")}) == 0
    held = {"ETH/USDT": Lot("ETH/USDT", Layer.TREND, D(".2"), D(20), D(90), NOW)}
    assert sized(lots=held) == 0  # Trend's 1.5% share already exceeded, even below total cap.
    assert open_risk(held, {"ETH/USDT": D(100)}, D(".0025"), D(".0015"))[Layer.TREND] > 2


def test_max_positions_and_capital_cannot_be_bypassed():
    lots = {str(i): Lot(str(i), Layer.PULLBACK, D(".01"), D(20), D(99), NOW) for i in range(4)}
    assert sized(lots=lots) == 0
    assert sized(cfg=PortfolioLimits(max_positions=6), lots=lots, cash=D(100)) <= D(".2")


def test_drawdown_ladder_and_halt_persist_in_sqlite(store):
    c, s = PortfolioLimits(), state()
    q = sized(risk=s)
    s.observe(c, D(95), NOW + DAY)
    assert not s.halted and s.blocks(c, NOW + 2 * DAY) == "daily loss"
    s.observe(c, D(95), NOW + 2 * DAY)
    assert s.blocks(c, NOW + 2 * DAY) is None
    assert 0 < sized(risk=s) <= q * D(".51")
    s.observe(c, D(90), NOW + 2 * DAY + 1)
    assert s.blocks(c, NOW + 2 * DAY + 1) == "drawdown entry block"
    s.observe(c, D(85), NOW + 2 * DAY + 2)
    assert s.halted
    store.set("risk-test", s.dump())
    restored = PortfolioRisk.restore(store.get("risk-test"))
    assert restored.dump() == s.dump()
    restored.observe(c, D(95), NOW + 4 * DAY)
    assert restored.halted
    assert not restored.resume(c, "yes")
    assert restored.resume(c, "I UNDERSTAND THE RISK")
    assert restored.peak == 100 and restored.drawdown == D(".05")


def test_resume_at_halt_boundary_refused_even_exact_confirmation():
    c, s = PortfolioLimits(), state()
    s.observe(c, D(84), NOW + 1)
    assert not s.resume(c, "I UNDERSTAND THE RISK")
    s.observe(c, D(85), NOW + 2)
    assert not s.resume(c, "I UNDERSTAND THE RISK")


def test_daily_loss_latch_uses_exchange_day_and_does_not_ignore_open_gap():
    c, s = PortfolioLimits(), state()
    s.observe(c, D(98), NOW + 1)
    s.observe(c, D(101), NOW + 2)
    assert s.daily_latched
    s.observe(c, D(101), NOW + DAY - 1)
    assert s.daily_latched
    s.observe(c, D(101), NOW + DAY)
    assert not s.daily_latched
    s.observe(c, D(98), NOW + 2 * DAY)
    assert s.daily_latched  # Gap charged to previous known equity, not a reset mark.


def test_three_losses_cooldown_is_persistent_and_expires_only_after_three_days(store):
    c, s = PortfolioLimits(), state()
    for _ in range(3):
        s.closed(c, D(-1), NOW)
    store.set("risk-test", s.dump())
    s = PortfolioRisk.restore(store.get("risk-test"))
    assert s.blocks(c, NOW + 3 * DAY - 1) == "loss cooldown"
    assert s.blocks(c, NOW + 3 * DAY) is None


def test_correlation_guard_held_assets_only_and_missing_is_conservative():
    returns = {
        "ETH/USDT": [float(i % 7) / 100 for i in range(60)],
        "SOL/USDT": [float(i % 7) / 50 for i in range(60)],
        "BTC/USDT": [0.0] * 60,
    }
    assert held_correlation(("ETH/USDT", "SOL/USDT"), returns, 60) > 0.99
    lots = {s: Lot(s, Layer.PULLBACK, D(".01"), D(1), D(99), NOW) for s in ("ETH/USDT", "SOL/USDT")}
    low = {**returns, "SOL/USDT": [-x for x in returns["ETH/USDT"]]}
    assert sized(lots=lots, returns=returns) < sized(lots=lots, returns=low) * D(".51")
    assert sized(lots=lots, returns={}) == sized(lots=lots, returns=returns)
    assert held_correlation(("ETH/USDT",), returns, 60) is None


@pytest.mark.parametrize(
    "values", [{"open_risk": 0}, {"trend_budget": ".8"}, {"half_dd": ".12"}, {"max_positions": 7}]
)
def test_invalid_risk_configuration(values):
    with pytest.raises(ValidationError):
        PortfolioLimits(**values)


@pytest.mark.parametrize("values", [{"rsi_entry": 70}, {"donchian_entry": 10}, {"typo": True}])
def test_invalid_strategy_configuration(values):
    with pytest.raises(ValidationError):
        LayeredConfig(**values)


def test_universe_validation_and_frozen_defaults():
    with pytest.raises(ValidationError):
        Universe(symbols=["BTC/USDT"] * 4)
    c, r, u = load_portfolio()
    assert not c.enabled and not c.breadth_enabled
    assert c.ema_period == 200 and c.donchian_entry == 55 and c.donchian_exit == 20
    assert r.trend_risk == D(".0075") and r.reserve == D(".20")
    assert 4 <= len(u.symbols) <= 6
