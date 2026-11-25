"""Event-driven, closed-signal/next-open backtesting, using shared strategy and risk code."""

import csv
import math
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.config import ROOT, RiskConfig, StrategyConfig
from exchange.base import Candle, Rules
from risk import RiskState, size, trail
from strategy import Action, Strategy, build

D = Decimal
YEAR = 31_557_600


@dataclass(frozen=True)
class Trade:
    entry_ts: int
    exit_ts: int
    quantity: float
    entry: float
    exit: float
    pnl: float
    reason: str


@dataclass
class Result:
    metrics: dict[str, float | int | None]
    equity: pd.DataFrame
    trades: list[Trade]
    buy_hold_return: float
    buy_hold_metrics: dict[str, float | int | None]
    bars: int
    warmup: int
    blocked_bars: int


def metrics(equity: pd.Series, trades: list[Trade], seconds: int) -> dict[str, float | int | None]:
    returns = equity.pct_change().dropna()
    total = float(equity.iloc[-1] / equity.iloc[0] - 1)
    years = max((len(equity) - 1) * seconds / YEAR, seconds / YEAR)
    draw = equity / equity.cummax() - 1
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    gains, loss = sum(wins), -sum(losses)
    std = float(returns.std(ddof=1))
    # Downside deviation below zero, rather than standard deviation of negative observations only.
    downside = float((returns.clip(upper=0).pow(2).mean()) ** 0.5)
    annual = math.sqrt(YEAR / seconds)
    return {
        "total_return": total,
        "cagr": float(math.expm1(math.log1p(total) / years)) if total > -1 else -1.0,
        "max_drawdown": float(draw.min()),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "profit_factor": gains / loss if loss else None,
        "sharpe": float(returns.mean() / std * annual) if std > 0 and math.isfinite(std) else None,
        "sortino": float(returns.mean() / downside * annual) if downside > 0 else None,
        "trades": len(trades),
        "average_win": gains / len(wins) if wins else 0.0,
        "average_loss": -loss / len(losses) if losses else 0.0,
    }


def run(
    candles: list[Candle],
    cfg: StrategyConfig,
    risk: RiskConfig,
    capital: D,
    rules: Rules | None = None,
    *,
    strategy: Strategy | None = None,
    start_index: int | None = None,
) -> Result:
    start = cfg.warmup if start_index is None else start_index
    if start < cfg.warmup or len(candles) < start + 2:
        raise ValueError(f"Insufficient closed candles: need warmup={start} plus at least 2 bars")
    if capital <= 0 or not capital.is_finite():
        raise ValueError("Backtest capital must be finite and positive")
    if any(b.ts - a.ts != cfg.seconds for a, b in zip(candles, candles[1:])):
        raise ValueError("Backtest needs consecutive candles; missing bars are never synthesized")
    rules = rules or Rules(D("0.000001"), D("0.01"), D("0.5"))
    strategy = strategy or build(cfg)
    prepared = strategy.prepare(candles)  # All provided indicators are strictly causal.
    cash, quantity, cost, stop = capital, D(0), D(0), D(0)
    entry_price, entry_ts = D(0), 0
    risk_state, blocked_bars = RiskState(), 0
    trades: list[Trade] = []
    equity_rows = [(candles[start].ts, float(capital), float(capital))]
    first_open = D(str(candles[start].open))
    benchmark_qty = capital / (first_open * (1 + risk.slippage) * (1 + risk.fee))

    def close(ts: int, reference: D, reason: str) -> None:
        nonlocal cash, quantity, cost, stop
        fill = reference * (1 - risk.slippage)
        proceeds = fill * quantity * (1 - risk.fee)
        pnl = proceeds - cost
        cash += proceeds
        trades.append(
            Trade(
                entry_ts, ts, float(quantity), float(entry_price), float(fill), float(pnl), reason
            )
        )
        quantity, cost, stop = D(0), D(0), D(0)
        risk_state.closed(risk, pnl, ts, cfg.seconds)

    for i in range(start, len(candles)):
        candle = candles[i]
        open_price, low = D(str(candle.open)), D(str(candle.low))
        signal = strategy.evaluate(prepared, i - 1)
        if signal.ts != candles[i - 1].ts:
            raise ValueError("Strategy signal must belong to the previous closed candle")
        halted = risk_state.observe(risk, cash + quantity * open_price, candle.ts)
        blocked_bars += bool(halted)
        exited = False
        # An existing stop gap executes first; a close-based exit executes at the open, not a future low.
        if quantity and open_price <= stop:
            close(candle.ts, open_price, "gap through ATR stop")
            exited = True
        elif quantity and signal.action == Action.SELL:
            close(candle.ts, open_price, "closed-candle strategy exit")
            exited = True
        if not quantity and not exited and signal.action == Action.BUY and not halted:
            price = open_price * (1 + risk.slippage)
            distance = D(str(signal.distance))
            qty = size(risk, rules, cash, cash, capital, price, distance, risk.fee)
            if qty:
                quantity, cost, stop = qty, qty * price * (1 + risk.fee), price - distance
                cash -= cost
                entry_price, entry_ts = price, candle.ts
        # Includes a newly opened trade: the initial stop can be hit during its entry candle.
        if quantity and low <= stop:
            close(candle.ts, min(open_price, stop), "intrabar ATR stop")
        if quantity:
            # Only known at this bar's close; the tightened stop becomes active on the next bar.
            current = strategy.evaluate(prepared, i)
            stop = trail(stop, D(str(candle.high)), D(str(current.distance)))
        equity = cash + quantity * D(str(candle.close))
        risk_state.observe(risk, equity, candle.ts + cfg.seconds - 1)
        benchmark = benchmark_qty * D(str(candle.close))
        equity_rows.append((candle.ts + cfg.seconds, float(equity), float(benchmark)))
    if quantity:
        close(candles[-1].ts + cfg.seconds, D(str(candles[-1].close)), "end-of-test liquidation")
        ts, _, benchmark = equity_rows[-1]
        equity_rows[-1] = (ts, float(cash), benchmark)
    # Benchmark is also liquidated with exit slippage and fees for an apples-to-apples final value.
    ts, eq, benchmark = equity_rows[-1]
    equity_rows[-1] = (ts, eq, benchmark * float((1 - risk.slippage) * (1 - risk.fee)))
    curve = pd.DataFrame(equity_rows, columns=["timestamp", "equity", "buy_hold"])
    return Result(
        metrics(curve.equity, trades, cfg.seconds),
        curve,
        trades,
        float(curve.buy_hold.iloc[-1] / float(capital) - 1),
        metrics(curve.buy_hold, [], cfg.seconds),
        len(candles) - start,
        start,
        blocked_bars,
    )


def write(result: Result, name: str = "backtest", root: Path | None = None) -> None:
    root = root or ROOT / "reports"
    root.mkdir(parents=True, exist_ok=True)
    with (root / f"{name}_trades.csv").open("w", newline="", encoding="utf-8") as file:
        fields = ["entry_ts", "exit_ts", "quantity", "entry", "exit", "pnl", "reason"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(t) for t in result.trades)
    result.equity.to_csv(root / f"{name}_equity.csv", index=False)
    fig, ax = plt.subplots(figsize=(10, 4))
    dates = pd.to_datetime(result.equity.timestamp, unit="s", utc=True)
    ax.plot(dates, result.equity.equity, label="Strategy")
    ax.plot(dates, result.equity.buy_hold, label="Buy and hold", alpha=0.75)
    ax.legend()
    ax.set_title("Simulated equity; both series include fees and slippage")
    ax.set_ylabel("USDT")
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(root / f"{name}_equity.png", dpi=140)
    plt.close(fig)


def display(value: float | int | None, percent: bool = False) -> str:
    if value is None or not math.isfinite(value):
        return "undefined"
    return f"{value:.2%}" if percent else f"{value:.4f}"


def report(result: Result, cfg: StrategyConfig, risk: RiskConfig) -> str:
    m, bm = result.metrics, result.buy_hold_metrics
    verdict = "outperformed" if m["total_return"] > result.buy_hold_return else "did NOT outperform"
    sample = (
        "TOO FEW TRADES for meaningful statistical conclusions"
        if m["trades"] < 30
        else "a historical sample, not a forecast"
    )
    first = pd.to_datetime(result.equity.timestamp.iloc[0], unit="s", utc=True)
    last = pd.to_datetime(result.equity.timestamp.iloc[-1], unit="s", utc=True)
    rows = []
    for key, label, percent in (
        ("total_return", "Total return", True),
        ("cagr", "CAGR", True),
        ("max_drawdown", "Max drawdown", True),
        ("sharpe", "Sharpe", False),
        ("sortino", "Sortino", False),
    ):
        rows.append(f"| {label} | {display(m[key], percent)} | {display(bm[key], percent)} |")
    return f"""# Backtest report — {cfg.symbol} / {cfg.timeframe}

**Verdict:** Strategy {verdict} buy-and-hold on this sample. {sample}.

Evaluation UTC: {first} to {last}. Evaluation bars: {result.bars}; excluded warmup: {result.warmup}.
Fees each side: {risk.fee:.2%}; slippage each side: {risk.slippage:.2%}. Risk-blocked bars: {result.blocked_bars}.

| Measure | Strategy | Buy and hold |
|---|---:|---:|
{chr(10).join(rows)}

Trades: {m["trades"]}; win rate: {display(m["win_rate"], True)}; profit factor: {display(m["profit_factor"])}.
Average win / loss in USDT: {display(m["average_win"])} / {display(m["average_loss"])}.
Risk-free rate is assumed zero. Crypto annualization uses 365.25 days. Undefined ratios are not zeroes.

## Method and weaknesses

Signals use closed bars; fills use the next bar open. Existing gap stops precede open-time exits;
the entry-bar initial stop can execute within that bar. Trailing stops calculated from a completed
bar only activate for the following bar. Fees and slippage apply on both sides, including the benchmark.
Daily loss, drawdown latches, cooldown, quantity steps, and capped position sizing use the same risk code
as the PAPER runner. Drawdown latches persist for the entire simulated account (they do not silently reset).

Candles cannot reveal order queues, contemporaneous spread, intrabar stop latency, or execution depth.
The PAPER runner can reject depth-limited fills that the historical open model would accept. Software
stops require the laptop to be online; historical intrabar stop simulation is more responsive than polling.
Constant fees/slippage and present-day symbol rules are approximations, not historical venue guarantees.
Past public candles may be revised by the venue. Missing candles are not invented. Forced end-of-test
liquidation is a reporting convention. Short-period CAGR and annualized ratios may be misleading.
Parameter grids and walk-forward selection can overfit; out-of-sample results are not a guarantee.

No profitability is promised. Thin liquidity, spreads/fees, exchange counterparty risk, internet failures,
API changes, and laptop sleep/power/downtime can cause substantial loss. This is not financial advice.
"""
