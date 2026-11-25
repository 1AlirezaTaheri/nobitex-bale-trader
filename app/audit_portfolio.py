"""Offline snapshot, output-consistency and deterministic replay audit (not validation)."""

import argparse
import csv
import json
import math
import struct
from collections import Counter
from hashlib import sha256
from pathlib import Path

from app.config import ROOT

CHARTS = ("equity_vs_benchmarks.png", "drawdown.png", "per_layer_equity.png", "monthly_heatmap.png")


def audit(source, replay=None):
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((source / "inputs/manifest.json").read_text(encoding="utf-8"))
    if len(summary["acceptance"]) != 8 or summary["validated"] != all(
        summary["acceptance"].values()
    ):
        raise ValueError("Acceptance count/status inconsistent")
    report = (source / "backtest_report.md").read_text(encoding="utf-8")
    for label, passed in summary["acceptance"].items():
        if f"- **{'PASS' if passed else 'FAIL'}** — {label}" not in report:
            raise ValueError("Report acceptance disagrees with JSON")
    for label, item in manifest["files"].items():
        file = source / "inputs" / item["file"]
        if (
            sha256(file.read_bytes()).hexdigest() != item["sha256"]
            or item != summary["input_files"][label]
        ):
            raise ValueError(f"Input checksum/manifest mismatch: {label}")
        with file.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != item["rows"] or len({r["timestamp"] for r in rows}) != len(rows):
            raise ValueError("Input row/uniqueness mismatch")
    with (source / "layeredportfolio_equity.csv").open(encoding="utf-8", newline="") as handle:
        curve = list(csv.DictReader(handle))
    equity = [float(r["equity"]) for r in curve]
    peak = equity[0]
    worst = 0.0
    for row, eq in zip(curve, equity, strict=True):
        peak = max(peak, eq)
        worst = min(worst, eq / peak - 1)
        if not math.isclose(
            eq - equity[0], float(row["trend_pnl"]) + float(row["pullback_pnl"]), abs_tol=1e-10
        ):
            raise ValueError("Sleeve PnL attribution does not sum to equity change")
    for actual, key in ((equity[-1] / equity[0] - 1, "total_return"), (worst, "max_drawdown")):
        if not math.isclose(actual, summary["full"][key], abs_tol=1e-12):
            raise ValueError(f"Equity/metric mismatch: {key}")
    with (source / "trades.csv").open(encoding="utf-8", newline="") as handle:
        trades = list(csv.DictReader(handle))
    if len(trades) != summary["full"]["trades"] or Counter(t["symbol"] for t in trades) != Counter(
        summary["full"]["by_asset"]
    ):
        raise ValueError("Trade-count/asset mismatch")
    for chart in CHARTS:
        raw = (source / chart).read_bytes()
        if raw[:8] != b"\x89PNG\r\n\x1a\n" or min(struct.unpack(">II", raw[16:24])) < 100:
            raise ValueError(f"Invalid/undersized PNG: {chart}")
    for name, expected in (
        ("sensitivity.csv", 31),
        ("perturbation.csv", 14),
        ("walk_forward.csv", 3),
    ):
        with (source / name).open(encoding="utf-8", newline="") as handle:
            if sum(1 for _ in csv.DictReader(handle)) != expected:
                raise ValueError(f"Unexpected case count: {name}")
    if replay:
        other = json.loads((replay / "summary.json").read_text(encoding="utf-8"))
        if other != summary:
            raise ValueError("Replay JSON does not exactly reproduce source results")
        for file in source.glob("*.csv"):
            if file.read_bytes() != (replay / file.name).read_bytes():
                raise ValueError(f"Replay CSV mismatch: {file.name}")
    return {
        "source": str(source),
        "input_files": len(manifest["files"]),
        "equity_rows": len(curve),
        "trades": len(trades),
        "pngs": len(CHARTS),
        "exact_replay": bool(replay),
        "ARTIFACT_AUDIT_PASS": True,
        "strategy_validated": summary["validated"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "reports/portfolio")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.source, args.replay), indent=2))
        return 0
    except (OSError, ValueError, KeyError, ArithmeticError) as error:
        print(f"Artifact audit failed: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
