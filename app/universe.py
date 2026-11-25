"""Deterministic public market screen and daily history collection."""

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.config import ROOT, load_yaml
from data.history import History, boundary, latest_segment
from data.store import Store
from exchange.base import ExchangeError, number
from exchange.nobitex import NobitexClient, Spec

DAY = 86400
EXCLUDED = {
    "USDT",
    "USDC",
    "DAI",
    "FDUSD",
    "TUSD",
    "USDE",
    "USDP",
    "USD1",
    "PYUSD",
    "EURC",
    "PAXG",
    "XAUT",
}


@dataclass(frozen=True)
class DailyHistory:
    symbol: str
    warmup: int = 602
    timeframe: str = "1d"
    seconds: int = DAY


def utc(ts):
    return datetime.fromtimestamp(ts, UTC).isoformat()


def depth(book, band=0.005):
    mid = float((book.bid + book.ask) / 2)
    return (
        float(book.ask - book.bid) / mid,
        sum(float(p * q) for p, q in book.bids if float(p) >= mid * (1 - band)),
        sum(float(p * q) for p, q in book.asks if float(p) <= mid * (1 + band)),
    )


def coverage(rows):
    return {
        "count": len(rows),
        "first": utc(rows[0].ts) if rows else None,
        "last": utc(rows[-1].ts) if rows else None,
        "gaps": [
            (utc(a.ts), utc(b.ts), b.ts - a.ts)
            for a, b in zip(rows, rows[1:])
            if b.ts - a.ts != DAY
        ],
    }


async def download(market, spec, store, symbol, now, pages):
    # Older DST grids can yield one extra row in a nominal 500-day window.
    history = History(
        store, market, DailyHistory(symbol), spec.offset("1d"), spec.raw["history_limit"] - 1
    )
    try:
        fetched, count, reason = await history.download(now, pages)
        return f"{fetched} fetched / {count} windows / {reason}"
    except ExchangeError as error:
        return f"INCOMPLETE: {error}; successful pages retained"


async def screen(market, spec, store, now, count):
    stats = (await market._call("market_stats"))["stats"]
    options = (await market.options())["nobitex"]
    known = {k for k in options["amountPrecisions"] if k.endswith("USDT")} & set(
        options["pricePrecisions"]
    )
    ranked = []
    for key, row in stats.items():
        base, sep, quote = key.upper().partition("-")
        if (
            sep
            and quote == "USDT"
            and base not in EXCLUDED
            and base + quote in known
            and row.get("isClosed") is False
        ):
            try:
                ranked.append((float(number(row["volumeDst"])), base + "/USDT"))
            except (ExchangeError, KeyError):
                continue
    ranked = sorted(ranked, key=lambda item: (-item[0], item[1]))
    shortlist = dict((symbol, volume) for volume, symbol in ranked[:16])
    if "BTC/USDT" not in shortlist:
        shortlist.update((symbol, volume) for volume, symbol in ranked if symbol == "BTC/USDT")
    samples = {symbol: [] for symbol in shortlist}
    for _ in range(3):
        raw = await market._call("books")  # Local throttle separates snapshots.
        observed = int(time.time())
        for symbol in shortlist:
            try:
                book = market.parse_book(raw[symbol.replace("/", "")])
                if -10 <= observed - book.ts <= 90:
                    samples[symbol].append((book.ts, *depth(book)))
            except (ExchangeError, KeyError):
                continue
    end = boundary(now, DAY, spec.offset("1d"))
    for symbol in shortlist:
        # At most two current-grid windows for screening; full collection follows selection.
        history = History(store, market, DailyHistory(symbol), spec.offset("1d"))
        for page in range(2):
            high = end - page * 500 * DAY
            try:
                await history.fetch(high - 500 * DAY, high, strict_grid=False)
            except ExchangeError as error:
                print(f"Screen {symbol} page {page + 1}: {error}", flush=True)
    metrics = {}
    for symbol, turnover in shortlist.items():
        rows = store.candles(symbol, "1d", end - 1000 * DAY, end)
        segment = latest_segment([row for row in rows if row.ts % DAY == spec.offset("1d")], DAY)
        quote = statistics.median([r.close * r.volume for r in segment[-90:]]) if segment else 0
        books = samples[symbol]
        spread, bid, ask = (
            statistics.median(s[i] for s in books) if books else None for i in (1, 2, 3)
        )
        failures = []
        if len(rows) < 750 or len(segment) < 301 or segment[-1].ts != end - DAY:
            failures.append(
                "<750 raw bars, <301 recent contiguous current-grid bars, or stale latest"
            )
        if quote < 10_000:
            failures.append("median daily quote-volume proxy <10,000 USDT")
        if len(books) != 3 or spread is None or spread > 0.004 or min(bid, ask) < 500:
            failures.append(
                "requires 3 fresh books, median spread <=0.40%, depth >=500 USDT each side"
            )
        metrics[symbol] = dict(
            turnover=turnover,
            raw=len(rows),
            contiguous=len(segment),
            median_quote=quote,
            spread=spread,
            bid_depth=bid,
            ask_depth=ask,
            books=books,
            reasons=failures,
        )
    eligible = sorted(
        (s for s, m in metrics.items() if not m["reasons"]),
        key=lambda s: (-metrics[s]["median_quote"], s),
    )
    selected = eligible[:count] if "BTC/USDT" in eligible and len(eligible) >= 4 else []
    if selected and "BTC/USDT" not in selected:
        selected[-1] = "BTC/USDT"
    return selected, metrics, len(ranked)


async def run(args):
    spec = Spec.load()
    now = int(time.time())
    output = ROOT / "reports"
    output.mkdir(exist_ok=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=5), trust_env=False) as http:
        market = NobitexClient(spec, http)
        with Store(ROOT / "data/candles.db") as store:
            evidence = output / "universe.json"
            if args.screen:
                chosen, metrics, market_count = await screen(market, spec, store, now, args.count)
                record = dict(
                    observed_utc=utc(now),
                    selected=chosen,
                    candidates=metrics,
                    eligible_market_list_count=market_count,
                )
            else:
                chosen = load_yaml("config/universe.yaml")["symbols"]
                record = (
                    json.loads(evidence.read_text(encoding="utf-8")) if evidence.exists() else {}
                )
                if chosen != record.get("selected"):
                    raise ValueError(
                        "Configured symbols do not match frozen universe evidence; run --screen first"
                    )
            record["coverage"] = {}
            for symbol in chosen:
                status = await download(market, spec, store, symbol, now, args.max_pages)
                rows = store.candles(symbol, "1d", end=now - DAY + 1)
                rules = await market.get_symbol_rules(symbol)
                record["coverage"][symbol] = dict(
                    **coverage(rows),
                    download=status,
                    rules={
                        key: str(getattr(rules, key))
                        for key in ("quantity_step", "price_tick", "min_quote", "min_quantity")
                    },
                )
                print(f"{symbol}: {len(rows)} cached; {status}", flush=True)
            record["public_fee_ceiling"] = str(await market.get_fees("BTC/USDT"))
    evidence.write_text(json.dumps(record, indent=2), encoding="utf-8")
    lines = [
        "# Nobitex daily universe",
        "",
        f"Screen UTC: {record.get('observed_utc')}. Selected: {', '.join(chosen) or 'NONE'}.",
        "",
        "Source: public market stats, options, full order books and actual daily candles. No returns used to select.",
        "Screen: top 16 open USDT markets by current 24h quote turnover (plus BTC), with public rules; exclude stable/fiat/gold proxies listed in code.",
        "The first screen required 750 consecutive bars; no symbol passed because of genuine daily discontinuities. Before evaluating returns,",
        "the history rule was split into >=750 raw bars and >=301 recent consecutive current-grid bars including the latest close.",
        "Require median of last 90 daily close x base volume >=10,000 USDT,",
        "and three fresh book observations (<=90s old), median spread <=0.40% and >=500 USDT each side within 0.50% of midpoint.",
        "Rank eligible markets by median daily quote-volume proxy; BTC is mandatory for the regime. Screening is a current snapshot,",
        "subject to survivorship/selection bias when applied to older history; it is not historical liquidity evidence.",
        "",
        "| Symbol | 24h turnover | Raw / recent contiguous | 90d median quote proxy | Median spread | Bid / ask depth USDT | Decision |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for symbol, m in record.get("candidates", {}).items():
        book = (
            f"{m['spread']:.3%} | {m['bid_depth']:.0f} / {m['ask_depth']:.0f}"
            if m["spread"] is not None
            else "NA | NA"
        )
        decision = (
            "Selected" if symbol in chosen else "; ".join(m["reasons"]) or "Eligible below cutoff"
        )
        lines.append(
            f"| {symbol} | {m['turnover']:.0f} | {m['raw']} / {m['contiguous']} | {m['median_quote']:.0f} | {book} | {decision} |"
        )
    lines += ["", "## Raw cached coverage (UTC candle opens)", ""]
    for symbol, info in record["coverage"].items():
        lines.append(
            f"- {symbol}: {info['count']} bars, {info['first']} to {info['last']}; {info['download']}."
        )
        for a, b, delta in info["gaps"]:
            detail = (
                f"{delta // DAY - 1} missing days"
                if delta % DAY == 0
                else f"{delta}s discontinuity (grid shift)"
            )
            lines.append(f"  - Gap from {a} to {b}: {detail}.")
    (output / "universe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Selected: " + ", ".join(chosen), flush=True)
    return 0 if len(chosen) >= 4 else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screen", action="store_true", help="Refresh evidence, does not edit runtime YAML"
    )
    parser.add_argument("--count", type=int, choices=range(4, 7), default=5)
    parser.add_argument(
        "--max-pages", type=int, choices=range(1, 101), default=20, metavar="1..100"
    )
    try:
        return asyncio.run(run(parser.parse_args()))
    except (ExchangeError, ValueError, OSError, KeyError) as error:
        print(f"Universe collection failed: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
