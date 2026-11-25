"""Independent public-data SHADOW ledger. No real order or cancellation transport."""

import argparse
import asyncio
import copy
import json
import math
import os
import signal
import sqlite3
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx

from app.config import ROOT
from data.history import boundary
from data.store import single_instance
from exchange.base import Candle, ExchangeError
from exchange.nobitex import NobitexClient, Spec
from strategy.timing import prepare, raw_targets

DAY = 86400
BASE = ROOT / "reports/final_audit"
PRODUCT_BASE = ROOT / "reports/final_product"
SYMBOLS = ("BTC/USDT", "ETH/USDT")
NAMES = ("A", "D", "B1", "B3", "B4_25", "B4_50", "B4_75", "B7_A", "B7_D", "B8")
ZERO_HASH = "0" * 64


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def hashed(obj):
    return sha256(canonical(obj)).hexdigest()


def safe_root(root):
    root = Path(root).resolve()
    if not any(
        root.is_relative_to(base.resolve()) and root != base.resolve()
        for base in (BASE, PRODUCT_BASE)
    ):
        raise ValueError("Shadow storage must be isolated under an approved reports root")
    return root


def registration(now):
    record = json.loads((BASE / "preregistration_amendment_001.json").read_text(encoding="utf-8"))
    source = ROOT / record["file"]
    if sha256(source.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("Frozen audit protocol checksum mismatch")
    v3 = json.loads(
        (ROOT / "reports/v3_preregistration_manifest.json").read_text(encoding="utf-8-sig")
    )
    if sha256((ROOT / v3["file"]).read_bytes()).hexdigest() != v3["sha256"]:
        raise ValueError("Frozen V3 protocol checksum mismatch")
    not_before = datetime.fromisoformat(record["forward_not_before_utc"]).timestamp()
    if now < not_before:
        raise ValueError(
            "Execution clock predates 2026-11-25 / registered not-before; no valid forward activation"
        )
    return {
        "audit_sha256": record["sha256"],
        "v3_sha256": v3["sha256"],
        "not_before": int(not_before),
        "provenance_warning": "Old audit manifest mismatch remains unresolved; amendment-bound forward only",
    }


def config_for(binding, fee):
    return {
        "schema": 2,
        "experiment": "product-shadow-v2",
        "mode": "SHADOW_PUBLIC_ONLY",
        "registration": binding,
        "names": list(NAMES),
        "fee": max(0.0025, float(fee)),
        "slippage": 0.0015,
        "capital": 100.0,
        "boundary_grace_seconds": 60,
        "warmup": 300,
        "dca_monthly_cash_budget": 100 / 12,
        "minimum_observed_intervals": [80, 160, 320],
        "rules": "Frozen A/D; monthly B4 5pp band; lagged expanding causal B7; B8 prior SMA200; no backfill",
        "source_hashes": {
            name: sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "strategy/timing.py",
                "app/forward_shadow.py",
                "app/forward_report.py",
                "exchange/nobitex.py",
                "exchange/nobitex_spec.yaml",
                "data/history.py",
                "requirements.lock",
                "app/product_ops.py",
                "app/product_shadow.py",
                "notify/product.py",
            )
        },
    }


def exclusive_json(path, value):
    # Publish a complete immutable file atomically without ever replacing an old path.
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".pending_", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as f:
            f.write(canonical(value) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.link(temporary, path)  # NTFS/local hard-link support is required; fail closed otherwise.
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_chain(root, expected_fingerprint=None):
    root = Path(root)
    records = []
    prev = ZERO_HASH
    last_ts = None
    for path in sorted((root / "snapshots").glob("snapshot_*.json")):
        item = json.loads(path.read_bytes())
        payload = item["payload"]
        if item["hash"] != hashed(payload) or payload["previous_hash"] != prev:
            raise ValueError("Broken forward hash chain")
        ts = payload["timestamp"]
        if (
            path.name != f"snapshot_{ts}.json"
            or (last_ts is not None and ts <= last_ts)
            or payload["sequence"] != len(records)
        ):
            raise ValueError("Nonmonotone or renamed forward snapshot")
        if expected_fingerprint and payload["configuration_fingerprint"] != expected_fingerprint:
            raise ValueError("Forward rules changed; restart observation with new storage")
        if (
            records
            and payload["configuration_fingerprint"]
            != records[0]["payload"]["configuration_fingerprint"]
        ):
            raise ValueError("Mixed forward configurations")
        if set(payload["accounts"]) != set(NAMES):
            raise ValueError("Missing shadow account")
        records.append(item)
        last_ts, prev = ts, item["hash"]
    return records


class Ledger:
    """Snapshots authoritative; SQLite is a verified, crash-recoverable secondary index."""

    def __init__(self, root, config):
        self.root = safe_root(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.fingerprint = hashed(config)
        path = self.root / "configuration.json"
        if path.exists():
            if path.read_bytes() != canonical(config) + b"\n":
                raise ValueError("Forward configuration changed; use a new root and restart clock")
        else:
            if (self.root / "shadow.db").exists() or list((self.root / "snapshots").glob("*.json")):
                raise ValueError("Missing configuration with existing shadow state")
            exclusive_json(path, config)
        (self.root / "snapshots").mkdir(exist_ok=True)
        self.records = load_chain(self.root, self.fingerprint)
        self.db = sqlite3.connect(self.root / "shadow.db", timeout=0.2)
        try:
            if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Shadow database integrity check failed")
            self.db.executescript(
                "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS snapshot (seq INTEGER PRIMARY KEY, hash TEXT NOT NULL, payload TEXT NOT NULL);"
            )
            db_rows = list(self.db.execute("SELECT seq,hash,payload FROM snapshot ORDER BY seq"))
            if len(db_rows) > len(self.records):
                raise ValueError("Database is ahead of immutable snapshot chain")
            for seq, digest, text in db_rows:
                if (
                    seq >= len(self.records)
                    or digest != self.records[seq]["hash"]
                    or text != canonical(self.records[seq]["payload"]).decode()
                ):
                    raise ValueError("Database/snapshot mismatch")
            with self.db:
                for seq in range(len(db_rows), len(self.records)):
                    item = self.records[seq]
                    self.db.execute(
                        "INSERT INTO snapshot VALUES (?,?,?)",
                        (seq, item["hash"], canonical(item["payload"]).decode()),
                    )
        except Exception:
            self.db.close()
            raise

    def append(self, payload):
        expected = self.records[-1]["hash"] if self.records else ZERO_HASH
        if (
            payload["previous_hash"] != expected
            or payload["sequence"] != len(self.records)
            or payload["configuration_fingerprint"] != self.fingerprint
        ):
            raise ValueError("Invalid append predecessor or configuration")
        item = {"payload": payload, "hash": hashed(payload)}
        exclusive_json(self.root / "snapshots" / f"snapshot_{payload['timestamp']}.json", item)
        with self.db:
            self.db.execute(
                "INSERT INTO snapshot VALUES (?,?,?)",
                (len(self.records), item["hash"], canonical(payload).decode()),
            )
        self.records.append(item)
        return item

    def close(self):
        self.db.close()


def empty_account():
    return {
        "cash": 100.0,
        "holdings": dict.fromkeys(SYMBOLS, 0.0),
        "equity": 100.0,
        "exposure": 0.0,
        "costs": 0.0,
        "trade_legs": 0,
        "round_trips": 0,
        "accepted": dict.fromkeys(SYMBOLS, 0.0),
        "last_month": None,
        "exposure_sum": 0.0,
        "exposure_observations": 0,
    }


def transact(account, prices, weights, fee, slip):
    eq = account["cash"] + sum(account["holdings"][s] * prices[s] for s in SYMBOLS)
    desired = {s: eq * weights.get(s, 0) / prices[s] for s in SYMBOLS}
    fills = []
    for s in SYMBOLS:
        qty = max(0.0, account["holdings"][s] - desired[s])
        if qty > 1e-14:
            raw = qty * prices[s]
            proceeds = raw * (1 - slip) * (1 - fee)
            account["cash"] += proceeds
            account["holdings"][s] -= qty
            account["costs"] += raw - proceeds
            account["trade_legs"] += 1
            if account["holdings"][s] <= 1e-12:
                account["holdings"][s] = 0.0
                account["round_trips"] += 1
            fills.append({"symbol": s, "side": "sell", "quantity": qty, "cost": raw - proceeds})
    buys = {s: max(0.0, desired[s] - account["holdings"][s]) for s in SYMBOLS}
    required = sum(buys[s] * prices[s] * (1 + slip) * (1 + fee) for s in SYMBOLS)
    scale = min(1.0, max(0.0, account["cash"]) / required) if required else 1.0
    for s in SYMBOLS:
        qty = buys[s] * scale
        if qty > 1e-14:
            raw = qty * prices[s]
            paid = raw * (1 + slip) * (1 + fee)
            account["cash"] -= paid
            account["holdings"][s] += qty
            account["costs"] += paid - raw
            account["trade_legs"] += 1
            fills.append({"symbol": s, "side": "buy", "quantity": qty, "cost": paid - raw})
    return fills


def observation(config, previous, timestamp, observed_at, warmup, opens):
    """One actually observed boundary only; past bars initialize indicators, never past trades."""
    if observed_at < config["registration"]["not_before"] or not 0 <= observed_at - timestamp <= 60:
        raise ValueError("Clock skew or missed execution boundary; no retroactive shadow fill")
    if set(opens) != set(SYMBOLS) or any(not math.isfinite(p) or p <= 0 for p in opens.values()):
        raise ValueError("Invalid common public opening prices")
    if set(warmup) != set(SYMBOLS):
        raise ValueError("Both assets require genuine warmup")
    for s, bars in warmup.items():
        if (
            len(bars) < 300
            or bars[-1].ts + DAY != timestamp
            or any(b.ts - a.ts != DAY for a, b in zip(bars, bars[1:]))
        ):
            raise ValueError("Warmup not contiguous through immediately previous close")
        if [r.ts for r in bars] != [r.ts for r in warmup[SYMBOLS[0]]]:
            raise ValueError("Warmup timestamps differ")
    prior = previous["payload"] if previous else None
    if prior and (timestamp <= prior["timestamp"] or (timestamp - prior["timestamp"]) % DAY):
        raise ValueError("Duplicate, backwards or shifted daily boundary")
    if prior and observed_at < prior["observed_at"]:
        raise ValueError("Observed clock moved backwards")
    missing = list(range(prior["timestamp"] + DAY, timestamp, DAY)) if prior else []
    accounts = (
        copy.deepcopy(prior["accounts"]) if prior else {name: empty_account() for name in NAMES}
    )
    features = {s: prepare(bars) for s, bars in warmup.items()}
    raw = {name: raw_targets(features, name)[-1] for name in ("A", "D")}
    month = datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m")
    all_fills = {}
    returns = {}
    for name in NAMES:
        a = accounts[name]
        before = a["cash"] + sum(a["holdings"][s] * opens[s] for s in SYMBOLS)
        weights = {s: a["holdings"][s] * opens[s] / before for s in SYMBOLS}
        exposure = sum(weights.values())
        target = {s: 0.0 for s in SYMBOLS}
        trade = False
        if name in ("A", "D"):
            proposed = {s: raw[name].get(s, 0.0) for s in SYMBOLS}
            accepted = a["accepted"]
            if name == "A" or sum(abs(proposed[s] - accepted[s]) for s in SYMBOLS) + 1e-12 >= 0.25:
                target = proposed
            else:
                target = dict(accepted)
            trade = not prior or target != accepted
        elif name == "B1":
            target[SYMBOLS[0]] = 1.0
            trade = not prior
        elif name == "B3":
            amount = min(max(0.0, a["cash"]), 100 / 12)
            target[SYMBOLS[0]] = (
                weights[SYMBOLS[0]]
                + amount / (1 + config["slippage"]) / (1 + config["fee"]) / before
            )
            trade = a["last_month"] != month
        elif name.startswith("B4_"):
            target[SYMBOLS[0]] = int(name.split("_")[-1]) / 100
            trade = not prior or (
                a["last_month"] != month and abs(exposure - sum(target.values())) >= 0.05 - 1e-14
            )
        elif name.startswith("B7_"):
            source = prior["accounts"][name[-1]] if prior else empty_account()
            weight = (
                source["exposure_sum"] / source["exposure_observations"]
                if source["exposure_observations"]
                else 0.0
            )
            target[SYMBOLS[0]] = weight if name == "B7_A" else weight / 2
            target[SYMBOLS[1]] = 0.0 if name == "B7_A" else weight / 2
            trade = not prior or a["last_month"] != month
        else:
            closes = [r.close for r in warmup[SYMBOLS[0]]]
            target[SYMBOLS[0]] = float(closes[-1] > sum(closes[-200:]) / 200)
            trade = not prior or target != a["accepted"]
        all_fills[name] = (
            transact(a, opens, target, config["fee"], config["slippage"]) if trade else []
        )
        a["accepted"] = target
        a["last_month"] = month
        eq = a["cash"] + sum(a["holdings"][s] * opens[s] for s in SYMBOLS)
        old = prior["accounts"][name]["equity"] if prior else 100.0
        returns[name] = {
            "economic_mark_return": eq / old - 1,
            "clean_observed_return": None if missing else eq / old - 1,
            "interval_observed": bool(prior) and not missing,
        }
        a["equity"] = eq
        a["exposure"] = sum(a["holdings"][s] * opens[s] for s in SYMBOLS) / eq
        a["exposure_sum"] += a["exposure"]
        a["exposure_observations"] += 1
    return {
        "schema": 1,
        "configuration_fingerprint": hashed(config),
        "sequence": prior["sequence"] + 1 if prior else 0,
        "previous_hash": previous["hash"] if previous else ZERO_HASH,
        "timestamp": timestamp,
        "observed_at": observed_at,
        "missing_boundaries": missing,
        "interrupted": bool(missing) or bool(prior and prior["interrupted"]),
        "prices": opens,
        "warmup_sha256": hashed({s: [asdict(r) for r in bars] for s, bars in warmup.items()}),
        "accounts": accounts,
        "fills": all_fills,
        "returns": returns,
        "warning": "Idealized public next-open SHADOW, not executable fills. Missed economic exposure remains in marked equity; clean interval return is null across gaps.",
    }


def cache_warmup(root, timestamp, warmup):
    """Append-only cache observations: an old public revision is never silently replaced."""
    path = Path(root) / "public_cache.db"
    with sqlite3.connect(path, timeout=0.2) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute(
            "CREATE TABLE IF NOT EXISTS observation (boundary INTEGER PRIMARY KEY, hash TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        obj = {s: [asdict(row) for row in bars] for s, bars in warmup.items()}
        old = db.execute(
            "SELECT hash,payload FROM observation WHERE boundary=?", (timestamp,)
        ).fetchone()
        if old and old != (hashed(obj), canonical(obj).decode()):
            raise ValueError("Conflicting immutable public warmup observation")
        if not old:
            db.execute(
                "INSERT INTO observation VALUES (?,?,?)",
                (timestamp, hashed(obj), canonical(obj).decode()),
            )


def retained_warmup(root, prior, fetched):
    if not prior:
        return fetched
    path = Path(root) / "public_cache.db"
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT hash,payload FROM observation WHERE boundary=?",
            (prior["payload"]["timestamp"],),
        ).fetchone()
    if (
        not row
        or hashed(json.loads(row[1])) != row[0]
        or row[0] != prior["payload"]["warmup_sha256"]
    ):
        raise ValueError("Prior warmup cache/hash missing or corrupted; forward restart refused")
    old = {s: [Candle(**r) for r in values] for s, values in json.loads(row[1]).items()}
    combined = {}
    for s in SYMBOLS:
        known = {r.ts: r for r in old[s]}
        for r in fetched[s]:
            if r.ts in known and r != known[r.ts]:
                raise ValueError(
                    "Venue revised previously frozen closed candle; do not rewrite history"
                )
            known[r.ts] = r
        combined[s] = [known[ts] for ts in sorted(known)]
    return combined


async def run(args):
    if args.mode != "shadow" or os.environ.get("MODE", "paper").lower() != "paper":
        raise ValueError("SHADOW only; LIVE refused, no real order transport")
    binding = registration(int(time.time()))
    root = safe_root(args.root)
    root.mkdir(parents=True, exist_ok=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous_handlers = {}
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            previous_handlers[sig] = signal.signal(
                sig, lambda *_: loop.call_soon_threadsafe(stop.set)
            )
    start = time.monotonic()
    records_before = 0
    ledger = None
    try:
        with single_instance(root / "shadow.lock"):
            if (root / "KILL").exists():
                raise ValueError("Shadow KILL file exists; observation refused")
            spec = Spec.load()
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(6, connect=4), trust_env=False
            ) as http:
                market = NobitexClient(spec, http)  # No Settings, keys or private endpoints.
                fee = await market.get_fees(SYMBOLS[0])
                config = config_for(binding, fee)
                ledger = Ledger(root, config)
                records_before = len(ledger.records)
                print(
                    "SHADOW READY; LIVE unavailable; observed snapshots:",
                    records_before,
                    flush=True,
                )
                while not stop.is_set() and not (root / "KILL").exists():
                    if args.max_seconds and time.monotonic() - start >= args.max_seconds:
                        break
                    now = int(time.time())
                    ts = boundary(now, DAY, spec.offset("1d"))
                    if (
                        not (root / "PAUSE").exists()
                        and 0 <= now - ts <= 60
                        and (not ledger.records or ts > ledger.records[-1]["payload"]["timestamp"])
                    ):
                        data = {}
                        opens = {}
                        for s in SYMBOLS:
                            # Stay below the documented 500-candle response ceiling.
                            fetched = await market.get_candles(s, "1d", ts - 490 * DAY, ts + DAY)
                            closed = [r for r in fetched if r.ts + DAY <= ts]
                            # Retain only the latest contiguous raw segment; require >=300.
                            first = len(closed) - 1
                            while first > 0 and closed[first].ts - closed[first - 1].ts == DAY:
                                first -= 1
                            data[s] = closed[first:] if closed else []
                            opens[s] = next(r.open for r in fetched if r.ts == ts)
                        prior = ledger.records[-1] if ledger.records else None
                        data = retained_warmup(root, prior, data)
                        payload = observation(config, prior, ts, int(time.time()), data, opens)
                        if (root / "KILL").exists() or stop.is_set():
                            break
                        if (root / "PAUSE").exists():
                            continue
                        cache_warmup(root, ts, data)
                        item = ledger.append(payload)
                        print(
                            "SHADOW SNAPSHOT",
                            ts,
                            item["hash"],
                            "interrupted=",
                            payload["interrupted"],
                            flush=True,
                        )
                    try:
                        await asyncio.wait_for(
                            stop.wait(),
                            timeout=min(
                                1.0, max(0.01, args.max_seconds - (time.monotonic() - start))
                            )
                            if args.max_seconds
                            else 1.0,
                        )
                    except TimeoutError:
                        pass
    finally:
        if ledger:
            total = len(ledger.records)
            ledger.close()
            print("SHADOW STOP; new observations:", total - records_before, flush=True)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", default="shadow")
    p.add_argument("--root", type=Path, default=PRODUCT_BASE / "shadow_v2")
    p.add_argument("--max-seconds", type=float, default=0.0)
    args = p.parse_args()
    if args.max_seconds < 0:
        p.error("max-seconds must be nonnegative")
    try:
        return asyncio.run(
            asyncio.wait_for(run(args), timeout=args.max_seconds + 60 if args.max_seconds else None)
        )
    except (
        ValueError,
        OSError,
        sqlite3.Error,
        StopIteration,
        RuntimeError,
        httpx.HTTPError,
        ExchangeError,
        TimeoutError,
    ) as error:
        # Never print arbitrary exception payloads that could contain headers or credentials.
        print(
            "SHADOW REFUSED / ALERT:",
            type(error).__name__,
            str(error)
            if isinstance(error, ValueError)
            else "Public data/storage operation failed; inspect local state; no orders sent",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
