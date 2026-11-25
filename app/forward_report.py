"""Weaknesses-first weekly SHADOW report with hash verification and fixed checkpoints."""

import argparse
import calendar
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.forward_shadow import BASE, NAMES, PRODUCT_BASE, hashed, load_chain, safe_root
from backtest import plt
from backtest.final_audit import fmt, write_csv, write_json


def months_after(timestamp, months):
    date = datetime.fromtimestamp(timestamp, UTC)
    number = date.month - 1 + months
    year = date.year + number // 12
    month = number % 12 + 1
    return int(
        date.replace(
            year=year, month=month, day=min(date.day, calendar.monthrange(year, month)[1])
        ).timestamp()
    )


def summarize(root, as_of=None):
    root = safe_root(root)
    config = (
        json.loads((root / "configuration.json").read_bytes())
        if (root / "configuration.json").exists()
        else None
    )
    records = load_chain(root, hashed(config) if config else None)
    if records and not config:
        raise ValueError("Forward configuration missing")
    as_of = int(time.time()) if as_of is None else int(as_of)
    if records and as_of < records[-1]["payload"]["timestamp"]:
        raise ValueError("Report clock predates the latest snapshot")
    outstanding = (
        list(range(records[-1]["payload"]["timestamp"] + 86400, as_of - 60, 86400))
        if records
        else []
    )
    summary = {
        "warnings": [
            "No clean historical holdout; this is forward SHADOW only, not executable orders or permission to invest.",
            "Short regimes can flatter any method. PASS only permits continued observation. No parameter changes; any change starts a new clock.",
            "Hash chains detect inconsistency, not a malicious rewrite/deletion of the entire root; export the latest hash to an independent location weekly.",
            "Economic marked equity includes downtime exposure; unobserved interval returns are null in clean performance. Interruption forbids checkpoint PASS.",
        ],
        "snapshots": len(records),
        "first_timestamp": records[0]["payload"]["timestamp"] if records else None,
        "latest_hash": records[-1]["hash"] if records else None,
        "interrupted": any(r["payload"]["interrupted"] for r in records) or bool(outstanding),
        "missing_boundaries": [ts for r in records for ts in r["payload"]["missing_boundaries"]],
        "as_of_execution_timestamp": as_of,
        "outstanding_missed_boundaries_after_last_snapshot": outstanding,
        "observed_intervals": sum(
            r["payload"]["returns"]["A"]["interval_observed"] for r in records
        ),
        "accounts": {},
        "checkpoints": {},
    }
    for name in NAMES:
        eq = np.array([100.0, *[r["payload"]["accounts"][name]["equity"] for r in records]])
        dd = eq / np.maximum.accumulate(eq) - 1
        last = records[-1]["payload"]["accounts"][name] if records else {}
        clean = [r["payload"]["returns"][name]["clean_observed_return"] for r in records]
        clean = [r for r in clean if r is not None]
        costs = last.get("costs", 0.0)
        gross = float(eq[-1] - 100 + costs)
        summary["accounts"][name] = {
            "equity": float(eq[-1]),
            "net_return": float(eq[-1] / 100 - 1),
            "max_drawdown": float(dd.min()),
            "current_exposure": last.get("exposure", 0.0),
            "costs": costs,
            "gross_profit": gross,
            "costs_pct_gross_profit": costs / gross if gross > 0 else None,
            "trade_legs": last.get("trade_legs", 0),
            "round_trips": last.get("round_trips", 0),
            "clean_rebased_return_excluding_gaps": float(np.prod(1 + np.array(clean)) - 1)
            if clean
            else None,
        }
    summary["matched_risk_constant_mix"] = risk_comparisons(summary, records)
    for months, minimum in ((3, 80), (6, 160), (12, 320)):
        due = months_after(summary["first_timestamp"], months) if records else None
        chosen = [r for r in records if r["payload"]["timestamp"] <= due] if due else []
        # Freeze checkpoint on the observed window ending at/before its due boundary.
        # A later date cannot rescue a checkpoint that lacked enough timely observations.
        due_reached = bool(records) and as_of >= due
        checkpoint = {"due_timestamp": due, "minimum_observed_intervals": minimum, "candidates": {}}
        for name in ("A", "D"):

            def stats(account):
                eq = np.array(
                    [100.0, *[r["payload"]["accounts"][account]["equity"] for r in chosen]]
                )
                cost = chosen[-1]["payload"]["accounts"][account]["costs"] if chosen else 0.0
                return (
                    float(eq[-1] / 100 - 1),
                    float(abs((eq / np.maximum.accumulate(eq) - 1).min())),
                    cost,
                    float(eq[-1] - 100 + cost),
                )

            ret, dd, cost, gross = stats(name)
            observed = sum(r["payload"]["returns"][name]["interval_observed"] for r in chosen)
            checks = {
                "minimum_days": observed >= minimum,
                "uninterrupted": not any(r["payload"]["interrupted"] for r in chosen)
                and not any(ts <= due for ts in summary["missing_boundaries"] + outstanding),
                "dd_le_60pct_B1": dd <= 0.6 * stats("B1")[1],
                "return_ge_B7_minus_2pp": ret >= stats("B7_" + name)[0] - 0.02,
                "positive_gross_and_costs_le_25pct": gross > 0 and cost <= 0.25 * gross,
            }
            checkpoint["candidates"][name] = {
                "status": "PENDING"
                if not due_reached
                else "PASS_CONTINUE_OBSERVING_ONLY"
                if all(checks.values())
                else "FAIL_NOT_VALIDATED",
                "checks": checks,
                "observed_intervals": observed,
            }
        summary["checkpoints"][str(months)] = checkpoint
    return summary, records


def risk_comparisons(summary, records):
    """Report all registered mixes; a realized-risk match is explicitly hindsight."""
    result = {
        "method": "All registered B4 weights; closest absolute marked MaxDD distance is descriptive hindsight, not an investable selection or exact risk match.",
        "status": "DESCRIPTIVE_ONLY"
        if summary["observed_intervals"] >= 20
        else "INSUFFICIENT_OBSERVATIONS",
        "minimum_clean_intervals": 20,
        "candidates": {},
    }
    for name in ("A", "D"):
        rows = []
        for mix in ("B4_25", "B4_50", "B4_75"):
            strategy, baseline = summary["accounts"][name], summary["accounts"][mix]
            clean = [
                [
                    r["payload"]["returns"][account]["clean_observed_return"]
                    for r in records
                    if r["payload"]["returns"][account]["interval_observed"]
                ]
                for account in (name, mix)
            ]
            rows.append(
                {
                    "baseline": mix,
                    "baseline_return": baseline["net_return"],
                    "baseline_max_drawdown": baseline["max_drawdown"],
                    "absolute_drawdown_distance": abs(
                        strategy["max_drawdown"] - baseline["max_drawdown"]
                    ),
                    "strategy_minus_baseline_return": strategy["net_return"]
                    - baseline["net_return"],
                    "clean_annualized_volatility": {
                        account: float(np.std(values, ddof=1) * np.sqrt(365))
                        if len(values) >= 20
                        else None
                        for account, values in zip((name, mix), clean, strict=True)
                    },
                }
            )
        result["candidates"][name] = {
            "comparisons": rows,
            "closest_realized_dd_descriptive_only": min(
                rows, key=lambda r: r["absolute_drawdown_distance"]
            )["baseline"]
            if result["status"] == "DESCRIPTIVE_ONLY"
            else None,
        }
    return result


def text_report(s):
    rows = [
        "# Weekly SHADOW observation report",
        "",
        "## Weaknesses FIRST",
        "",
        *["- " + w for w in s["warnings"]],
        "",
        f"Observed snapshots: {s['snapshots']}; clean observed intervals: {s['observed_intervals']}; interrupted: {s['interrupted']}.",
        f"Latest independently exportable chain hash: `{s['latest_hash']}`.",
        f"Missing daily boundaries (Unix UTC): `{s['missing_boundaries']}`.",
        f"Outstanding missed boundaries after the latest snapshot: `{s['outstanding_missed_boundaries_after_last_snapshot']}`.",
        f"Report execution time (Unix UTC): `{s['as_of_execution_timestamp']}`.",
        "",
        "| Account | Equity USDT | Net return | Max marked DD | Exposure | Costs | Legs |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in s["accounts"].items():
        rows.append(
            f"| {name} | {m['equity']:.3f} | {fmt(m['net_return'], True)} | {fmt(m['max_drawdown'], True)} | {fmt(m['current_exposure'], True)} | {m['costs']:.3f} | {m['trade_legs']} |"
        )
    rows += [
        "",
        "B7 uses only lagged observed average exposure. It is not an exactly matched future-exposure control. No terminal liquidation is assumed in marked forward accounts.",
        "Initial entry costs are included even before a full observed daily interval. Clean rebased returns exclude gap factors and are NOT economic account returns.",
        "",
        "## Fixed review checkpoints",
        "",
    ]
    for months, checkpoint in s["checkpoints"].items():
        for name, v in checkpoint["candidates"].items():
            rows.append(
                f"- {months} months / {name}: **{v['status']}**, due={checkpoint['due_timestamp']}, checks={v['checks']}."
            )
    rows += [
        "",
        "## Registered constant-mix risk comparisons (descriptive hindsight only)",
        "",
        s["matched_risk_constant_mix"]["method"],
        "Status: " + s["matched_risk_constant_mix"]["status"],
        "",
        "| Strategy | Mix | Mix return | Mix MaxDD | DD distance | Return difference |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, comparison in s["matched_risk_constant_mix"]["candidates"].items():
        for r in comparison["comparisons"]:
            rows.append(
                f"| {name} | {r['baseline']} | {fmt(r['baseline_return'], True)} | {fmt(r['baseline_max_drawdown'], True)} | {fmt(r['absolute_drawdown_distance'], True)} | {fmt(r['strategy_minus_baseline_return'], True)} |"
            )
    rows += [
        "",
        "There is not enough evidence to infer an edge from a short forward period. No LIVE authorization, parameter changes or performance promises.",
    ]
    return "\n".join(rows) + "\n"


def generate(root, output):
    output = Path(output).resolve()
    if (
        not any(
            output.is_relative_to(base.resolve()) and output != base.resolve()
            for base in (BASE, PRODUCT_BASE)
        )
        or output.exists()
    ):
        raise ValueError("Use a fresh report folder under an approved reports root")
    s, records = summarize(root)
    output.mkdir(parents=True)
    write_json(output / "weekly.json", s)
    (output / "weekly.md").write_text(text_report(s), encoding="utf-8")
    write_csv(
        output / "accounts.csv", [{"account": name, **m} for name, m in s["accounts"].items()]
    )
    rows = [
        {
            "account": name,
            "timestamp": r["payload"]["timestamp"],
            **r["payload"]["accounts"][name],
            **r["payload"]["returns"][name],
            "interrupted": r["payload"]["interrupted"],
        }
        for r in records
        for name in NAMES
    ]
    write_csv(output / "curves.csv", rows)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for name in NAMES:
        chosen = [r for r in rows if r["account"] == name]
        x = [datetime.fromtimestamp(r["timestamp"], UTC) for r in chosen]
        eq = np.array([r["equity"] for r in chosen])
        if len(eq):
            dd = 100 * (eq / np.maximum.accumulate(np.r_[100.0, eq])[1:] - 1)
            for ax, values in zip(
                axes.flat,
                (eq, dd, [r["exposure"] * 100 for r in chosen], [r["costs"] for r in chosen]),
                strict=True,
            ):
                ax.plot(x, values, label=name)
    if not rows:
        for ax in axes.flat:
            ax.text(
                0.5,
                0.5,
                "NO FORWARD OBSERVATIONS\nPerformance unavailable",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=12,
            )
            ax.set_xticks([])
            ax.set_yticks([])
    for ax, label in zip(
        axes.flat,
        ("Marked equity USDT", "Marked drawdown %", "Exposure %", "Cumulative modeled costs USDT"),
        strict=True,
    ):
        ax.set_ylabel(label)
        ax.grid(alpha=0.2)
        if rows:
            ax.legend(fontsize=6, ncol=3)
    fig.suptitle("SHADOW only; missing intervals are not clean performance")
    fig.tight_layout()
    fig.savefig(output / "weekly.png", dpi=130)
    plt.close(fig)
    return s


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=PRODUCT_BASE / "shadow_v2")
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    out = args.output or PRODUCT_BASE / ("weekly_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    try:
        s = generate(args.root, out)
        print(text_report(s))
        print("Report directory:", out)
        return 0
    except (ValueError, OSError, KeyError) as error:
        print("Forward report refused / ALERT:", type(error).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
