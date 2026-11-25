"""Evaluate the frozen daily LayeredPortfolio without promoting or tuning its defaults."""

import argparse
import csv
import json
import math
import shutil
import time
from dataclasses import astuple
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path

import pandas as pd

from app.config import ROOT, ConfigError, load
from app.portfolio_config import load_portfolio
from app.universe import utc
from backtest import plt
from backtest import run as legacy_run
from backtest.portfolio import (
    buy_hold,
    common_segments,
    monthly_returns,
    simulate,
    statistics,
    trade_records,
)
from data.history import read_csv
from data.store import Store
from exchange.base import Rules
from exchange.nobitex import Spec
from strategy.layered import DAY, LayeredConfig

HEADER = ["timestamp", "open", "high", "low", "close", "volume"]
PCT = {"total_return", "cagr", "max_drawdown", "worst_month", "exposure_fraction"}
GRID = {
    "donchian_entry": (30, 45, 55, 75, 100),
    "donchian_exit": (10, 15, 20, 30, 40),
    "trend_atr": (2, 2.5, 3, 3.5, 4),
    "pullback_atr": (2, 2.5, 3, 3.5, 4),
    "rsi_entry": (5, 10, 15, 20, 25, 30),
    "ema_period": (100, 150, 200, 225, 250),
}


def variant(cfg, **values):
    return LayeredConfig.model_validate({**cfg.model_dump(), **values})


def checks(full, stress, holdout, eq, perturbed, trend, pullback):
    result = full["total_return"]
    floor = 0.5 * result
    robust = (
        bool(perturbed)
        and result > 0
        and all(x["total_return"] > 0 and x["total_return"] >= floor for x in perturbed)
    )
    return {
        "At least 100 completed trades": full["trades"] >= 100,
        "Positive net return at baseline and 2x costs": result > 0 and stress["total_return"] > 0,
        "Positive fixed final-25% holdout return": holdout["total_return"] > 0,
        "Profit factor greater than 1.30": full["profit_factor"] is not None
        and full["profit_factor"] > 1.3,
        "Maximum drawdown no worse than 25%": full["max_drawdown"] >= -0.25,
        "Calmar better than equal-weight buy and hold": full["calmar"] is not None
        and eq["calmar"] is not None
        and full["calmar"] > eq["calmar"],
        "Robust to +/-20% perturbations": robust,
        "Combined drawdown no worse than worst pure single trading layer": full["max_drawdown"]
        >= min(trend["max_drawdown"], pullback["max_drawdown"]),
    }


def csv_rows(path, rows, fields=None):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_inputs(root, data, legacy, rules, evidence, info):
    folder = root / "inputs"
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for label, rows in {**data, "BTC/USDT_4h": legacy}.items():
        name = label.replace("/", "-") + ".csv"
        with (folder / name).open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(HEADER)
            writer.writerows(astuple(r) for r in rows)
        files[label] = {
            "file": name,
            "sha256": sha256((folder / name).read_bytes()).hexdigest(),
            "rows": len(rows),
        }
    manifest = {
        "files": files,
        "coverage": info,
        "universe": evidence,
        "rules": {
            s: {
                k: str(getattr(r, k))
                for k in ("quantity_step", "price_tick", "min_quote", "min_quantity")
            }
            for s, r in rules.items()
        },
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_inputs(folder, universe, segment_type, legacy_cfg, now):
    if folder:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        rows = {}
        for label in (*universe, "BTC/USDT_4h"):
            item = manifest["files"][label]
            path = folder / (label.replace("/", "-") + ".csv")
            if sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"Snapshot checksum mismatch for {label}")
            rows[label] = (
                read_csv(path, 14400 if label.endswith("_4h") else DAY, now) if item["rows"] else []
            )
            if len(rows[label]) != item["rows"]:
                raise ValueError("Snapshot manifest row count mismatch")
        legacy = rows.pop("BTC/USDT_4h")
        rules = {s: Rules(**{k: D(v) for k, v in manifest["rules"][s].items()}) for s in universe}
        return rows, legacy, rules, manifest["universe"], manifest["coverage"]
    evidence = json.loads((ROOT / "reports/universe.json").read_text(encoding="utf-8"))
    if set(universe) != set(evidence["selected"]):
        raise ValueError("Run public universe screen and record matching configured symbols first")
    rules = {
        s: Rules(**{k: D(v) for k, v in evidence["coverage"][s]["rules"].items()}) for s in universe
    }
    with Store(ROOT / "data/candles.db") as store:
        cached = {s: store.candles(s, "1d", end=now - DAY + 1) for s in universe}
        segments = common_segments(cached, Spec.load().offset("1d"))
        if not segments:
            raise ValueError("No shared daily segment on the verified grid")
        n = universe[0]
        data = (
            segments[-1]
            if segment_type == "latest"
            else max(segments, key=lambda d: (len(d[n]), d[n][-1].ts))
        )
        legacy = store.candles("BTC/USDT", "4h", start=data[n][0].ts, end=data[n][-1].ts + DAY)
    if legacy_cfg.timeframe != "4h" or legacy_cfg.symbol != "BTC/USDT":
        raise ValueError(
            "The unchanged BTC comparator requires the existing BTC/USDT 4h configuration"
        )
    info = {
        "policy": segment_type,
        "first": utc(data[n][0].ts),
        "last": utc(data[n][-1].ts),
        "used_per_asset": len(data[n]),
        "excluded_by_asset": {s: len(cached[s]) - len(data[s]) for s in universe},
        "common_segment_lengths": [len(x[n]) for x in segments],
    }
    return data, legacy, rules, evidence, info


def legacy_comparator(candles, cfg, risk, rules, capital, first, last, *, daily_comparable=False):
    selected = [c for c in candles if c.ts < last]
    start = next((i for i, c in enumerate(selected) if c.ts == first), None)
    if start is None or start < cfg.warmup or not selected or selected[-1].ts + cfg.seconds != last:
        return None
    try:
        result = legacy_run(selected, cfg, risk, capital, rules, start_index=start)
    except ValueError:
        return None
    curve = result.equity[["timestamp", "equity"]].iloc[:: DAY // cfg.seconds].copy()
    # Legacy benchmark's exposure isn't candle-derived; use entry/exit intervals (bar-resolution).
    ts = curve.timestamp.to_list()
    exposure = [
        any(t.entry_ts < b and t.exit_ts >= a for t in result.trades) for a, b in zip(ts, ts[1:])
    ]
    m = statistics(curve, [], exposure)
    if daily_comparable:
        # Comparable metrics use the daily-sampled curve; report and retain 4h DD.
        m["daily_sampled_max_drawdown"] = m["max_drawdown"]
        m["max_drawdown_4h"] = result.metrics["max_drawdown"]
        m["max_drawdown"] = result.metrics["max_drawdown"]
        m["calmar"] = m["cagr"] / -m["max_drawdown"] if m["max_drawdown"] < 0 else None
        m["trade_legs"] = len(result.trades)
    else:
        m.update(result.metrics)
        # The original 4h max DD is kept; ratios below use daily returns.
        m.update({k: statistics(curve, [], exposure)[k] for k in ("sharpe", "sortino")})
        m["calmar"] = m["cagr"] / -m["max_drawdown"] if m["max_drawdown"] < 0 else None
    return curve, m


def chart(root, curves, full, solo):
    def lines(values, name, ylabel):
        fig, ax = plt.subplots(figsize=(11, 5))
        for label, frame, series in values:
            ax.plot(pd.to_datetime(frame.timestamp, unit="s", utc=True), series, label=label)
        ax.legend(fontsize=8)
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.2)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(root / name, dpi=140)
        plt.close(fig)

    lines(
        [(s, c, c.equity) for s, c in curves.items()], "equity_vs_benchmarks.png", "Equity (USDT)"
    )
    lines(
        [(s, c, 100 * (c.equity / c.equity.cummax() - 1)) for s, c in curves.items()],
        "drawdown.png",
        "Drawdown (%)",
    )
    lines(
        [(s, x.curve, x.curve.equity) for s, x in solo.items()],
        "per_layer_equity.png",
        "Standalone sleeve-account equity (USDT)",
    )
    monthly = monthly_returns(full.curve)
    table = (
        pd.DataFrame(
            {
                "year": monthly.index.year,
                "month": monthly.index.month,
                "return": 100 * monthly.to_numpy(),
            }
        )
        .pivot(index="year", columns="month", values="return")
        .reindex(columns=range(1, 13))
    )
    fig, ax = plt.subplots(figsize=(10, max(2, 1 + len(table))))
    image = ax.imshow(
        table,
        cmap="RdYlGn",
        aspect="auto",
        vmin=-max(0.1, abs(table).max().max()),
        vmax=max(0.1, abs(table).max().max()),
    )
    ax.set_xticks(range(12), range(1, 13))
    ax.set_yticks(range(len(table)), table.index)
    for j, row in enumerate(table.to_numpy()):
        for i, value in enumerate(row):
            if math.isfinite(value):
                ax.text(i, j, f"{value:.1f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, label="Monthly return (%)")
    fig.tight_layout()
    fig.savefig(root / "monthly_heatmap.png", dpi=140)
    plt.close(fig)


def fmt(m, k):
    value = m.get(k)
    return (
        "N/A"
        if value is None
        else f"{value:.2%}"
        if k in PCT
        else f"{value:.3f}"
        if isinstance(value, float)
        else str(value)
    )


def evaluate(args):
    settings, legacy_cfg, base_risk, app = load()
    cfg, limits, universe = load_portfolio()
    data, legacy, rules, evidence, info = load_inputs(
        args.snapshot, universe.symbols, args.segment, legacy_cfg, int(time.time())
    )
    capital = min(settings.max_capital_quote, app.paper_cash)
    fee = max(base_risk.fee, D(evidence["public_fee_ceiling"]))
    slip = base_risk.slippage
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    symbols = list(data)
    n = len(data[symbols[0]])
    start = cfg.warmup
    split = start + (n - start) * 3 // 4
    if n - start < 100:
        raise ValueError("Need 100 evaluable consecutive days after warmup")
    manifest = save_inputs(output, data, legacy, rules, evidence, info)

    def sim(c=cfg, a=start, b=n, multiplier=1):
        return simulate(
            data, c, limits, rules, fee * multiplier, slip * multiplier, capital, start=a, end=b
        )

    trend = variant(
        cfg, trend_enabled=True, pullback_enabled=False, btc_filter=False, breadth_enabled=False
    )
    pull = variant(
        cfg, trend_enabled=False, pullback_enabled=True, btc_filter=False, breadth_enabled=False
    )
    combined = variant(
        cfg, trend_enabled=True, pullback_enabled=True, btc_filter=False, breadth_enabled=False
    )
    full_cfg = variant(
        cfg, trend_enabled=True, pullback_enabled=True, btc_filter=True, breadth_enabled=False
    )
    ablations = {
        "L1 Trend only": sim(trend),
        "L2 Pullback only": sim(pull),
        "L1+L2 (no BTC gate)": sim(combined),
        "Full (L1+L2+BTC)": sim(full_cfg),
        "Full + breadth": sim(variant(full_cfg, breadth_enabled=True)),
    }
    full = ablations["Full (L1+L2+BTC)"]
    holdout = sim(full_cfg, split, n)
    stress = {x: sim(full_cfg, multiplier=x) for x in (2, 3)}
    eq_curve, eq = buy_hold(data, symbols, start, n, fee, slip, capital, limits)
    btc_curve, btc = buy_hold(data, ["BTC/USDT"], start, n, fee, slip, capital, limits)
    cash_curve = eq_curve.assign(equity=float(capital))
    cash_metrics = statistics(cash_curve, [], [False] * (n - start))
    first, last = int(eq_curve.iloc[0].timestamp), int(eq_curve.iloc[-1].timestamp)
    legacy_result = legacy_comparator(
        legacy, legacy_cfg, base_risk, rules["BTC/USDT"], capital, first, last
    )
    curves = {"LayeredPortfolio": full.curve, "Equal weight B&H": eq_curve, "BTC B&H": btc_curve}
    benchmarks = {"Equal weight B&H": eq, "BTC B&H": btc}
    if legacy_result:
        curves["Legacy 4h BTC trend"], benchmarks["Legacy 4h BTC trend"] = legacy_result
    sensitivity = []
    plusminus = []

    def assess(label, c, rows):
        x = sim(c).stats
        rows.append(
            {
                "case": label,
                **{k: getattr(c, k) for k in GRID},
                **{k: x[k] for k in ("total_return", "max_drawdown", "calmar", "sharpe", "trades")},
            }
        )

    for key, values in GRID.items():
        for value in values:
            if key == "donchian_exit" and value >= full_cfg.donchian_entry:
                continue
            assess(f"{key}={value}", variant(full_cfg, **{key: value}), sensitivity)
    for factor in (0.8, 1.2):
        joint = {}
        for key in GRID:
            value = getattr(full_cfg, key) * factor
            if key in {"donchian_entry", "donchian_exit", "ema_period"}:
                value = round(value)
            joint[key] = value
            assess(f"{key} x {factor}", variant(full_cfg, **{key: value}), plusminus)
        assess(f"joint x {factor}", variant(full_cfg, **joint), plusminus)
    walk = []
    # Restricted candidate set; the fixed 25% holdout is never used to select defaults.
    candidates = [
        variant(full_cfg, donchian_entry=d, trend_atr=a)
        for d in (45, 55, 75)
        for a in (2.5, 3.0, 3.5)
    ]
    midpoint = start + (split - start) // 2
    edges = [midpoint + (split - midpoint) * i // 3 for i in range(4)]
    for a, b in zip(edges, edges[1:]):
        chosen = max(
            candidates, key=lambda c: (sim(c, start, a).stats["total_return"], c == full_cfg)
        )
        x = sim(chosen, a, b).stats
        walk.append(
            {
                "test_start": utc(data[symbols[0]][a].ts),
                "test_end": utc(data[symbols[0]][b - 1].ts + DAY),
                "entry_window": chosen.donchian_entry,
                "atr": chosen.trend_atr,
                "return": x["total_return"],
                "drawdown": x["max_drawdown"],
                "trades": x["trades"],
            }
        )
    csv_rows(output / "sensitivity.csv", sensitivity)
    csv_rows(output / "perturbation.csv", plusminus)
    csv_rows(output / "walk_forward.csv", walk)
    csv_rows(
        output / "trades.csv",
        trade_records(full),
        ["symbol", "layer", "entry_ts", "exit_ts", "reason", "quantity", "pnl"],
    )
    for name, frame in curves.items():
        frame.to_csv(
            output / (name.lower().replace(" ", "_").replace("&", "") + "_equity.csv"), index=False
        )
    holdout.curve.to_csv(output / "holdout_equity.csv", index=False)
    for name, x in ablations.items():
        x.curve.to_csv(
            output
            / (
                name.split()[0].replace("+", "_")
                + "_"
                + str(list(ablations).index(name))
                + "_ablation.csv"
            ),
            index=False,
        )
    monthly_returns(full.curve).rename("return").to_csv(output / "monthly.csv")
    solo = {k: ablations[k] for k in ("L1 Trend only", "L2 Pullback only")}
    chart(output, curves, full, solo)
    lret = solo["L1 Trend only"].curve.equity.pct_change()
    rret = solo["L2 Pullback only"].curve.equity.pct_change()
    corr = lret.corr(rret) if lret.std() > 0 and rret.std() > 0 else float("nan")
    corr = float(corr) if math.isfinite(corr) else None
    contributions = (
        full.curve[["trend_pnl", "pullback_pnl"]].diff().div(full.curve.equity.shift(), axis=0)
    )
    a, b = contributions.trend_pnl, contributions.pullback_pnl
    actual_corr = float(a.corr(b)) if a.std() > 0 and b.std() > 0 else None
    passed = checks(
        full.stats, stress[2].stats, holdout.stats, eq, plusminus, *(x.stats for x in solo.values())
    )
    summary = {
        "evaluation_utc": [utc(first), utc(last)],
        "acceptance": passed,
        "validated": all(passed.values()),
        "strategy": full_cfg.model_dump(mode="json"),
        "runtime_strategy": cfg.model_dump(mode="json"),
        "risk": limits.model_dump(mode="json"),
        "legacy_strategy": legacy_cfg.model_dump(mode="json"),
        "base_costs": {"fee": str(fee), "slippage": str(slip), "capital": str(capital)},
        "full": full.stats,
        "holdout": holdout.stats,
        "holdout_start": utc(data[symbols[0]][split].ts),
        "holdout_days": n - split,
        "ablation": {"L3 Cash only": cash_metrics, **{k: v.stats for k, v in ablations.items()}},
        "benchmarks": benchmarks,
        "layer_return_correlation": corr,
        "combined_contribution_correlation": actual_corr,
        "stress": {k: v.stats for k, v in stress.items()},
        "walk_forward": walk,
        "input_files": manifest["files"],
        "coverage": info,
        "zero_volume_inputs": {
            symbol: sum(row.volume == 0 for row in rows) for symbol, rows in data.items()
        },
        "rejected": dict(full.rejected),
        "blocked_days": dict(full.blocked),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    text = report(summary, sensitivity, plusminus)
    (output / "backtest_report.md").write_text(text, encoding="utf-8")
    if output == (ROOT / "reports/portfolio").resolve():
        target = ROOT / "reports/backtest_report.md"
        archive = ROOT / "reports/legacy_4h_backtest_report.md"
        if (
            target.exists()
            and not archive.exists()
            and "LayeredPortfolio" not in target.read_text(encoding="utf-8")
        ):
            shutil.copyfile(target, archive)
        target.write_text(text, encoding="utf-8")
    print(text)
    return 0


def report(s, sensitivity, perturb):
    full = s["full"]
    rows = [
        "# LayeredPortfolio — daily Nobitex PAPER research",
        "",
        "## Weaknesses first",
        "",
        f"**{'ALL NUMERICAL CHECKS PASSED (not a live certification)' if s['validated'] else 'NOT VALIDATED — numerical acceptance failed'}**. Runtime default enabled: `{str(s['runtime_strategy']['enabled']).lower()}`.",
        "- Today's universe/precision create survivorship and selection bias. Excluded gaps and older/unmatched bars are not traded through.",
        "- Historical order books are unavailable: each modeled IOC uses the existing depth walk, a fixed half-spread and a one-level capacity of 0.1% of the prior closed day's base volume at default. This is an assumption, not measured historical executable liquidity.",
        f"- Zero-volume input bars per asset: `{s['zero_volume_inputs']}`. Zero-volume prior bars imply zero modeled capacity: no substitution or inferred liquidity. A no-trade run cannot validate the strategy.",
        "- Daily OHLC cannot time stops across assets or capture the intraday equity minimum. Reported drawdown uses daily closes; the ladder also checks opens. Paper stops require connectivity. A rejected exit may remain exposed.",
        "- Walk-forward accounts restart risk and cash, do not compound fold returns, and use only the pre-holdout period. The holdout is not evidence of future safety. Small trade counts make ratios fragile.",
        "",
        "## Acceptance (frozen criteria)",
        "",
        *[f"- **{'PASS' if ok else 'FAIL'}** — {k}" for k, ok in s["acceptance"].items()],
        "",
        "Perturbation passes only when baseline is positive and **all** one-at-a-time and joint +/-20% runs stay positive and retain at least 50% of baseline net return. No rule was changed to pass.",
        "",
        "## Coverage and reproducibility",
        "",
        f"Evaluation UTC: {s['evaluation_utc'][0]} to {s['evaluation_utc'][1]}. Final holdout: {s['holdout_days']} days from {s['holdout_start']}.",
        f"Common contiguous policy: `{s['coverage']['policy']}`, {s['coverage']['used_per_asset']} inputs per asset including warmup. Excluded counts: `{s['coverage']['excluded_by_asset']}`.",
        f"Base costs per side: fee {D(s['base_costs']['fee']):.2%}, adverse slippage {D(s['base_costs']['slippage']):.2%}, plus modeled half-spread {D(s['risk']['historical_half_spread']):.2%}.",
        "See `inputs/manifest.json` next to this report's artifacts for raw input CSV SHA256; `reports/universe.md` records raw coverage/gaps. A snapshot can be replayed without API access.",
        "",
        "## Ablation and benchmarks",
        "",
        "| Run | Return | CAGR | Max DD | Calmar | Sharpe | Sortino | Trades | PF |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in (s["ablation"] | s["benchmarks"]).items():
        rows.append(
            "| "
            + " | ".join(
                [
                    name,
                    *[
                        fmt(m, k)
                        for k in (
                            "total_return",
                            "cagr",
                            "max_drawdown",
                            "calmar",
                            "sharpe",
                            "sortino",
                            "trades",
                            "profit_factor",
                        )
                    ],
                ]
            )
            + " |"
        )
    if "Legacy 4h BTC trend" not in s["benchmarks"]:
        rows.append(
            "\nLegacy 4h comparator unavailable for the exact sample (missing aligned warmup/coverage or gaps); no mismatched period substituted."
        )
    else:
        rows.append(
            "\nLegacy BTC strategy uses its unchanged rules/fill model, 4h drawdown observations and daily-sampled Sharpe/Sortino. Buy-and-hold buys equal weights once, not daily rebalanced, with modeled round-trip costs and fractional units; it does not impose the portfolio's risk or modeled-depth caps."
        )
    corr = s["layer_return_correlation"]
    rows += [
        "",
        f"Pearson correlation of aligned daily net returns of the standalone L1 and L2 sleeves (including cash days): **{corr:.3f}**."
        if corr is not None
        else "Sleeve return correlation: undefined.",
        "Layer 3 alone is all cash; it has no trade/exit rule. Sleeve capital caps are unchanged in all ablations.",
        f"Daily contribution correlation inside the actual combined account (sleeve PnL changes divided by prior total equity): `{s['combined_contribution_correlation']}`.",
        "",
    ]
    for name in ("L1 Trend only", "L2 Pullback only"):
        for combo in ("L1+L2 (no BTC gate)", "Full (L1+L2+BTC)"):
            a, b = s["ablation"][combo], s["ablation"][name]

            def compare(k):
                return (
                    "undefined"
                    if a[k] is None or b[k] is None
                    else "YES"
                    if a[k] > b[k] + 1e-12
                    else "NO"
                )

            rows.append(
                f"- {combo} vs {name}: strictly reduced drawdown **{compare('max_drawdown')}**; improved Calmar **{compare('calmar')}**; improved Sharpe **{compare('sharpe')}**."
            )
    rows += [
        "",
        "## Risk, trade and stability details",
        "",
        f"- Final holdout: {fmt(s['holdout'], 'total_return')}, {s['holdout']['trades']} completed trades, DD {fmt(s['holdout'], 'max_drawdown')}.",
        *[
            f"- {k}x fee/slippage stress (spread/depth fixed): {fmt(x, 'total_return')}, DD {fmt(x, 'max_drawdown')}, {x['trades']} trades."
            for k, x in s["stress"].items()
        ],
        f"- Sensitivity ({len(sensitivity)} cases): return {min(x['total_return'] for x in sensitivity):.2%} to {max(x['total_return'] for x in sensitivity):.2%}; perturbations ({len(perturb)} cases): {min(x['total_return'] for x in perturb):.2%} to {max(x['total_return'] for x in perturb):.2%}.",
        f"- Closed trades by asset: `{full['by_asset']}`; by layer (count and win rate): `{full['by_layer']}`.",
        f"- Win rate {full['win_rate']:.2%}; average win/loss {full['average_win']:.4f} / {full['average_loss']:.4f} USDT; exposure {fmt(full, 'exposure_fraction')}; longest flat period {full['longest_flat_days']} days.",
        f"- Worst month {fmt(full, 'worst_month')}; maximum consecutive losses {full['max_consecutive_losses']}; longest underwater stretch {full['drawdown_duration_days']} days (including unrecovered tail).",
        f"- Breaker days by first blocking reason: `{s['blocked_days']}`. Size/fill rejections: `{s['rejected']}`. Unliquidated at sample end: `{full['unliquidated_at_end']}`.",
        "",
        "No execution guarantee, no evidence of a live edge, and no authorization for real orders.",
    ]
    return "\n".join(rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segment", choices=("longest", "latest"), default="longest")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/portfolio")
    parser.add_argument(
        "--snapshot", type=Path, help="Directory containing a verified input manifest and CSVs"
    )
    try:
        return evaluate(parser.parse_args())
    except (ConfigError, ValueError, KeyError, OSError, ArithmeticError) as error:
        print(f"Portfolio evaluation refused: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
