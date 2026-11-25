from decimal import Decimal

import pytest

from exchange.base import Rules
from risk import RiskState, down, size, trail, up

D = Decimal


def test_size_respects_every_cap_and_roundtrip_risk(risk):
    rules = Rules(D("0.000001"), D("0.01"), D("0.5"))
    price, distance, fee = D(100), D(5), D("0.0025")
    qty = size(risk, rules, D(100), D(100), D(20), price, distance, fee)
    assert qty > 0
    assert qty % rules.quantity_step == 0
    assert qty * price * (1 + fee) <= 20
    assert qty * (distance + 2 * price * (fee + risk.slippage)) <= D(20) * risk.risk_pct


@pytest.mark.parametrize("distance", [D(0), D(-1), D(100), D(101)])
def test_invalid_stop_has_zero_size(risk, distance):
    assert (
        size(
            risk,
            Rules(D("0.001"), D("0.01"), D("0.5")),
            D(100),
            D(100),
            D(100),
            D(100),
            distance,
            D("0.0025"),
        )
        == 0
    )


def test_minimum_order_never_rounded_up(risk):
    assert (
        size(risk, Rules(D("0.01"), D("0.01"), D(50)), D(100), D(1), D(100), D(100), D(5), risk.fee)
        == 0
    )


def test_higher_fees_reduce_size(risk, market):
    args = (risk, market.rules, D(100), D(100), D(100), D(100), D(2))
    assert size(*args, D("0.02")) < size(*args, D("0.001"))


def test_rounding_and_trailing_never_loosen():
    assert down(D("1.239"), D("0.01")) == D("1.23")
    assert up(D("1.231"), D("0.01")) == D("1.24")
    assert trail(D(95), D(98), D(5)) == 95
    assert trail(D(95), D(110), D(5)) == 105


def test_daily_limit_latches_and_resets_only_next_day(risk):
    state = RiskState()
    assert state.observe(risk, D(100), 86400) is None
    assert "daily" in state.observe(risk, D(96), 86401)
    assert "daily" in state.observe(risk, D(100), 86402)
    assert state.observe(risk, D(100), 2 * 86400) is None


def test_drawdown_latch_survives_rebound_and_restart(risk):
    state = RiskState()
    state.observe(risk, D(100), 86400)
    assert "drawdown" in state.observe(risk, D(89), 86401)
    restored = RiskState.restore(state.serialize())
    assert "drawdown" in restored.observe(risk, D(110), 3 * 86400)


def test_loss_streak_cooldown(risk):
    state = RiskState()
    for _ in range(risk.consecutive_losses):
        state.closed(risk, D(-1), 100, 14400)
    assert state.observe(risk, D(100), 101) == "loss cooldown"
    assert state.observe(risk, D(100), 100 + risk.cooldown_bars * 14400) is None


def test_zero_pnl_breaks_loss_streak(risk):
    state = RiskState(losses=2)
    state.closed(risk, D(0), 100, 14400)
    assert state.losses == 0


@pytest.mark.parametrize("args", [(D(0), D(1), D(1)), (D(1), D(0), D(1)), (D(1), D(1), D(-1))])
def test_rules_reject_invalid_steps(args):
    with pytest.raises(ValueError):
        Rules(*args)
