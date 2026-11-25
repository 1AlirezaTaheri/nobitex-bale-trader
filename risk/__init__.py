from dataclasses import asdict, dataclass
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from app.config import RiskConfig
from exchange.base import Rules

D = Decimal


def down(value: D, step: D) -> D:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def up(value: D, step: D) -> D:
    return (value / step).to_integral_value(rounding=ROUND_UP) * step


def size(
    config: RiskConfig,
    rules: Rules,
    equity: D,
    cash: D,
    capital: D,
    price: D,
    stop_distance: D,
    fee: D,
) -> D:
    if min(equity, cash, capital, price, stop_distance) <= 0 or stop_distance >= price:
        return D(0)
    cap = min(cash, capital, config.max_order_quote)
    roundtrip = 2 * price * (fee + config.slippage)
    qty = down(
        min(
            min(equity, capital) * config.risk_pct / (stop_distance + roundtrip),
            cap / (price * (1 + fee)),
        ),
        rules.quantity_step,
    )
    return qty if qty >= rules.min_quantity and qty * price >= rules.min_quote else D(0)


def trail(previous: D, reference: D, distance: D) -> D:
    return max(previous, reference - distance) if distance > 0 else previous


@dataclass
class RiskState:
    day: int = -1
    day_start: D = D(0)
    high: D = D(0)
    drawdown_latched: bool = False
    daily_latched: bool = False
    losses: int = 0
    cooldown_until: int = 0

    def observe(self, config: RiskConfig, equity: D, ts: int) -> str | None:
        if ts // 86400 > self.day:
            self.day, self.day_start, self.daily_latched = ts // 86400, equity, False
        self.high = max(self.high, equity)
        if equity <= self.high * (1 - config.max_drawdown):
            self.drawdown_latched = True
        if equity <= self.day_start * (1 - config.max_daily_loss):
            self.daily_latched = True
        if self.drawdown_latched:
            return "maximum drawdown (latched)"
        if self.daily_latched:
            return "daily loss (latched until next UTC day)"
        if ts < self.cooldown_until:
            return "loss cooldown"
        return None

    def closed(self, config: RiskConfig, pnl: D, ts: int, step: int) -> None:
        self.losses = self.losses + 1 if pnl < 0 else 0
        if self.losses >= config.consecutive_losses:
            self.cooldown_until = ts + step * config.cooldown_bars
            self.losses = 0

    def serialize(self) -> dict:
        return {k: str(v) if isinstance(v, D) else v for k, v in asdict(self).items()}

    @classmethod
    def restore(cls, obj: dict) -> "RiskState":
        return cls(**{k: D(v) if k in {"day_start", "high"} else v for k, v in obj.items()})
