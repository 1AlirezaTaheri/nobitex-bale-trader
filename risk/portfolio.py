"""Portfolio risk state and fee-aware sizing; independent of transport and storage."""

from dataclasses import asdict, dataclass
from decimal import Decimal as D
from statistics import correlation

from pydantic import Field, model_validator

from app.config import Strict
from risk import down
from strategy.layered import DAY, Layer

ZERO = D(0)
ONE = D(1)


class PortfolioLimits(Strict):
    trend_risk: D = Field(default=D(".0075"), gt=0, le=D(".05"))
    pullback_risk: D = Field(default=D(".005"), gt=0, le=D(".05"))
    open_risk: D = Field(default=D(".03"), gt=0, le=D(".10"))
    asset_cap: D = Field(default=D(".25"), gt=0, le=1)
    max_positions: int = Field(default=4, ge=1, le=6)
    trend_budget: D = Field(default=D(".50"), gt=0, lt=1)
    pullback_budget: D = Field(default=D(".30"), gt=0, lt=1)
    reserve: D = Field(default=D(".20"), ge=0, lt=1)
    half_dd: D = Field(default=D(".05"), gt=0, lt=1)
    entry_dd: D = Field(default=D(".10"), gt=0, lt=1)
    halt_dd: D = Field(default=D(".15"), gt=0, lt=1)
    daily_loss: D = Field(default=D(".02"), gt=0, lt=1)
    loss_count: int = Field(default=3, ge=1, le=30)
    cooldown_days: int = Field(default=3, ge=1, le=90)
    correlation_days: int = Field(default=60, ge=10, le=250)
    correlation_threshold: float = Field(default=0.85, gt=0, lt=1)
    correlation_scale: D = Field(default=D(".50"), gt=0, le=1)
    historical_half_spread: D = Field(default=D(".001"), ge=0, le=D(".01"))
    historical_volume_fraction: D = Field(default=D(".001"), gt=0, le=D(".01"))

    @model_validator(mode="after")
    def validate_limits(self):
        if self.trend_budget + self.pullback_budget + self.reserve != 1:
            raise ValueError("Sleeve budgets and reserve must sum to one")
        if not self.half_dd < self.entry_dd < self.halt_dd:
            raise ValueError("Require half_dd < entry_dd < halt_dd")
        return self


@dataclass(slots=True)
class PortfolioRisk:
    peak: D = ZERO
    equity: D = ZERO
    day_open: D = ZERO
    day: int = -1
    halted: bool = False
    daily_latched: bool = False
    streak: int = 0
    cooldown_until: int = 0

    @property
    def drawdown(self):
        return max(ZERO, ONE - self.equity / self.peak) if self.peak else ZERO

    def observe(self, cfg, equity, ts):
        if not equity.is_finite() or equity < 0:
            raise ValueError("Invalid portfolio equity")
        self.equity = equity
        self.peak = max(self.peak, equity)
        # Verified Nobitex daily boundary, not UTC midnight; preserve raw candle grid.
        day = (ts - 73800) // DAY
        if day > self.day:
            # The next observed gap is charged to the new day, not discarded at rollover.
            self.day_open = self.day_open if self.day < 0 else self.previous_equity
            self.day_open = self.day_open or equity
            self.day, self.daily_latched = day, False
        if self.day_open and equity <= self.day_open * (ONE - cfg.daily_loss):
            self.daily_latched = True
        self.halted |= self.drawdown >= cfg.halt_dd
        self.previous_equity = equity

    previous_equity: D = ZERO

    def blocks(self, cfg, ts):
        if self.halted:
            return "drawdown halt"
        if self.drawdown >= cfg.entry_dd:
            return "drawdown entry block"
        if self.daily_latched:
            return "daily loss"
        if ts < self.cooldown_until:
            return "loss cooldown"
        return None

    def resume(self, cfg, phrase):
        # Never reset the peak. Recovery above the halt boundary is required before re-arming.
        if phrase == "I UNDERSTAND THE RISK" and self.halted and self.drawdown < cfg.halt_dd:
            self.halted = False
            return True
        return False

    def closed(self, cfg, pnl, ts):
        self.streak = self.streak + 1 if pnl < 0 else 0
        if self.streak >= cfg.loss_count:
            self.cooldown_until = max(self.cooldown_until, ts + cfg.cooldown_days * DAY)
            self.streak = 0

    def dump(self):
        return {k: str(v) if isinstance(v, D) else v for k, v in asdict(self).items()}

    @classmethod
    def restore(cls, values):
        return cls(
            **{
                k: D(v) if k in {"peak", "equity", "day_open", "previous_equity"} else v
                for k, v in values.items()
            }
        )


def held_correlation(symbols, returns, window):
    symbols = sorted(symbols)
    if len(symbols) < 2:
        return None
    scores = []
    for i, left in enumerate(symbols):
        for right in symbols[i + 1 :]:
            x, y = returns.get(left, ())[-window:], returns.get(right, ())[-window:]
            if len(x) != window or len(y) != window:
                return None
            try:
                scores.append(correlation(x, y))
            except (ValueError, ArithmeticError):
                return None
    return sum(scores) / len(scores)


def open_risk(lots, marks, fee, slip):
    # Risk of a drop from the current mark to net stop proceeds; not a guarantee against gaps.
    out = {layer: ZERO for layer in Layer}
    for lot in lots.values():
        out[lot.layer] += lot.qty * max(
            ZERO, marks[lot.symbol] - lot.stop * (ONE - slip) * (ONE - fee)
        )
    return out


def quantity(cfg, state, ts, entry, lots, marks, cash, capital, price, rules, fee, slip, returns):
    if state.blocks(cfg, ts) or entry.symbol in lots or len(lots) >= cfg.max_positions:
        return ZERO
    if not 0 < entry.distance < price or state.equity <= 0:
        return ZERO
    equity = min(state.equity, capital)
    corr = held_correlation(lots, returns, cfg.correlation_days)
    # Insufficient or degenerate correlation data with multiple held assets is conservatively scaled.
    corr_scale = (
        cfg.correlation_scale
        if len(lots) >= 2 and (corr is None or corr > cfg.correlation_threshold)
        else ONE
    )
    ladder_scale = D(".5") if state.drawdown >= cfg.half_dd else ONE
    pct, share = (
        (cfg.trend_risk, cfg.trend_budget)
        if entry.layer == Layer.TREND
        else (cfg.pullback_risk, cfg.pullback_budget)
    )
    used = open_risk(lots, marks, fee, slip)
    budget = min(
        equity * pct * corr_scale * ladder_scale,
        equity * cfg.open_risk - sum(used.values()),
        equity * cfg.open_risk * share - used[entry.layer],
    )
    if budget <= 0:
        return ZERO
    # Conservative fill-to-stop loss, including entry fee and adverse exit/slippage.
    unit_risk = price * (ONE + fee) - (price - entry.distance) * (ONE - slip) * (ONE - fee)
    limit = min(cash, capital - sum(lot.cost for lot in lots.values()), equity * cfg.asset_cap)
    if limit <= 0:
        return ZERO
    qty = down(min(budget / unit_risk, limit / (price * (ONE + fee))), rules.quantity_step)
    return qty if qty >= rules.min_quantity and qty * price >= rules.min_quote else ZERO
