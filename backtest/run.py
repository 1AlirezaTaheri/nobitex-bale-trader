import argparse
import csv
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from app.config import ROOT, ConfigError, load
from backtest import display, report, run, write
from data.history import latest_segment, read_csv
from data.store import Store


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backtest cached real candles or an explicitly supplied CSV"
    )
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    parser.add_argument(
        "--latest-contiguous",
        action="store_true",
        help="Explicitly restrict evaluation to the latest gap-free segment; report excluded bars",
    )
    args = parser.parse_args()
    try:
        settings, cfg, risk, app = load()
        if args.csv:
            candles = read_csv(args.csv, cfg.seconds, int(time.time()))
            source = f"User CSV: {args.csv.name} (provenance is the operator's responsibility)"
        else:
            with Store(ROOT / app.data_directory / "candles.db") as store:
                candles = store.candles(
                    cfg.symbol, cfg.timeframe, end=int(time.time()) - cfg.seconds + 1
                )
            source = "Public Nobitex candles cached in data/candles.db; no synthetic substitutions"
        excluded = 0
        if args.latest_contiguous:
            segment = latest_segment(candles, cfg.seconds)
            excluded = len(candles) - len(segment)
            candles = segment
            source += f"; explicitly selected latest continuous segment, {excluded} older bars excluded after a gap"
            print(
                f"Gap policy: using {len(candles)} latest contiguous bars; excluded {excluded} earlier bars."
            )
        minimum = max(cfg.warmup + 300, cfg.warmup * 2 + 100)
        if len(candles) < minimum:
            print(
                f"Insufficient history: {len(candles)} bars, need {minimum}. "
                "Collect/download more or import CSV: timestamp,open,high,low,close,volume."
            )
            return 2
        capital = min(app.paper_cash, settings.max_capital_quote)
        evaluation = len(candles) - cfg.warmup
        split = cfg.warmup + int(evaluation * 0.7)
        train = run(candles[:split], cfg, risk, capital)
        test = run(candles, cfg, risk, capital, start_index=split)
        result = run(candles, cfg, risk, capital)
        for name, item in (("backtest", result), ("train", train), ("out_of_sample", test)):
            write(item, name, args.output)
        snapshot = args.output / "market_candles.csv"
        with snapshot.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for candle in candles:
                writer.writerow(asdict(candle).values())
        dataset_hash = sha256(snapshot.read_bytes()).hexdigest()
        grid = []
        # Sensitivity is diagnostic, not a claim that the full-sample winner should be deployed.
        for fast in (15, 20, 25):
            for multiple in (2.0, 2.5, 3.0):
                altered = type(cfg).model_validate(
                    {**cfg.model_dump(), "fast": fast, "atr_multiplier": multiple}
                )
                item = run(candles, altered, risk, capital)
                grid.append({"fast": fast, "atr_multiplier": multiple, **item.metrics})
        with (args.output / "sensitivity.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(grid[0]))
            writer.writeheader()
            writer.writerows(grid)
        walk = []
        # Expanding-window train-only selection, then disjoint out-of-sample slices. Cash resets per fold.
        first = cfg.warmup + evaluation // 2
        edges = [first + (len(candles) - first) * k // 3 for k in range(4)]
        for fold, (start, end) in enumerate(zip(edges, edges[1:]), 1):
            candidates = []
            for multiple in (2.0, 2.5, 3.0):
                altered = type(cfg).model_validate({**cfg.model_dump(), "atr_multiplier": multiple})
                candidate = run(candles[:start], altered, risk, capital)
                candidates.append((candidate.metrics["total_return"], multiple, altered))
            _, chosen, selected = max(candidates, key=lambda item: (item[0], -item[1]))
            item = run(candles[:end], selected, risk, capital, start_index=start)
            walk.append(
                {
                    "fold": fold,
                    "train_end": candles[start].ts,
                    "test_end": candles[end - 1].ts + cfg.seconds,
                    "chosen_atr": chosen,
                    "test_return": item.metrics["total_return"],
                    "buy_hold_return": item.buy_hold_return,
                    "trades": len(item.trades),
                }
            )
        with (args.output / "walk_forward.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(walk[0]))
            writer.writeheader()
            writer.writerows(walk)
        text = report(result, cfg, risk)
        text += f"\n## Provenance and holdout\n\n{source}. Generated {datetime.now(timezone.utc).isoformat()}.\n"
        text += f"\nExact evaluated input (including warmup): `market_candles.csv`; SHA256 `{dataset_hash}`.\n"
        if excluded:
            text += "\nWARNING: This segment omits a historical data gap and all preceding bars. "
            text += "Its results do not describe trading through that outage; segment selection can bias conclusions.\n"
        text += f"\n70/30 chronological evaluation split. Train return: {display(train.metrics['total_return'], True)}; "
        text += f"holdout return: {display(test.metrics['total_return'], True)}, "
        text += f"holdout buy-and-hold: {test.buy_hold_return:.2%}, holdout trades: {len(test.trades)}.\n"
        if len(test.trades) < 30:
            text += "\nHoldout has too few trades to support reliability claims.\n"
        text += "\n## Walk-forward and parameter sensitivity\n\nSee `walk_forward.csv` and `sensitivity.csv`. "
        text += "Three expanding-window folds select ATR multiple on past training return only, then test on "
        text += "the next disjoint slice. Each fold restarts cash/risk state: fold returns are NOT a single "
        text += "continuous equity curve. The nine full-sample sensitivity combinations are descriptive, "
        text += (
            "not independent confirmations. The fixed holdout uses no grid-selected parameters.\n"
        )
        for row in walk:
            text += f"\n- Fold {row['fold']}: selected ATR={row['chosen_atr']}, test={row['test_return']:.2%}, "
            text += f"benchmark={row['buy_hold_return']:.2%}, trades={row['trades']}."
        text += "\n"
        (args.output / "backtest_report.md").write_text(text, encoding="utf-8")
        summary = {
            "full": result.metrics,
            "train": train.metrics,
            "holdout": test.metrics,
            "source": source,
            "strategy": cfg.model_dump(mode="json"),
            "risk": risk.model_dump(mode="json"),
            "capital": str(capital),
            "dataset_sha256": dataset_hash,
            "walk_forward": walk,
        }
        (args.output / "backtest_summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
        )
        print(text)
        return 0
    except (ConfigError, ValueError, OSError, KeyError, OverflowError) as error:
        print(
            f"Backtest failed: {type(error).__name__}. "
            "Check closed, consecutive OHLCV candles, configuration and writable output path."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
