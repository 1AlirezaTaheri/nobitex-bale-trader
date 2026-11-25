"""Bounded public probes and local-only reliability/security evidence for the final audit."""

import argparse
import asyncio
import ctypes
import importlib.util
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np

from app.config import ROOT
from backtest.final_audit import BASE, confined, digest, write_csv, write_json
from backtest.final_audit_core import metrics
from exchange.base import Candle


def child_command(folder, phase, recover=False):
    return [
        sys.executable,
        "-m",
        "app.final_audit_fault_worker",
        "--root",
        str(folder),
        "--phase",
        phase,
        *(["--recover"] if recover else []),
    ]


def process_drills(folder):
    """Kill only PIDs created here; never discover/terminate unrelated processes."""
    results = []
    for phase in ("cycle", "order", "suspend"):
        root = folder / phase
        p = subprocess.Popen(
            child_command(root, phase),
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        start = time.perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(p.stdout.readline)
                try:
                    ready = future.result(timeout=20).strip()
                    if ready != "READY":
                        raise ValueError("Fault child did not reach the local test barrier")
                except Exception:
                    p.kill()
                    p.wait(timeout=5)
                    raise
            ready_seconds = time.perf_counter() - start
            if phase in ("cycle", "order"):
                killed = time.perf_counter()
                p.kill()
                p.wait(timeout=5)
                terminated = time.perf_counter() - killed
                restarted = time.perf_counter()
                r = subprocess.run(
                    child_command(root, phase, True),
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                data = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
                good = (
                    data.get("reconciled")
                    and data.get("active") == 0
                    and data.get("uncommitted_marker") is None
                )
                if phase == "order":
                    good = good and data.get("quantity") == "0.1" and data.get("orders") == 1
                else:
                    good = good and data.get("quantity") == "0" and data.get("orders") == 0
                results.append(
                    {
                        "drill": "actual_child_kill_mid_" + phase,
                        "pass": bool(good),
                        "ready_seconds": ready_seconds,
                        "termination_seconds": terminated,
                        "restart_wall_seconds": time.perf_counter() - restarted,
                        **data,
                    }
                )
            else:
                if os.name != "nt":
                    os.kill(p.pid, signal.SIGSTOP)
                    time.sleep(0.25)
                    os.kill(p.pid, signal.SIGCONT)
                else:
                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel.OpenProcess.restype = ctypes.c_void_p
                    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
                    handle = kernel.OpenProcess(0x0800 | 0x1000, False, p.pid)
                    if not handle:
                        raise OSError("Cannot open own child for suspend drill")
                    ntdll = ctypes.WinDLL("ntdll")
                    ntdll.NtSuspendProcess.argtypes = [ctypes.c_void_p]
                    ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    suspended = False
                    try:
                        if ntdll.NtSuspendProcess(handle) != 0:
                            raise OSError("Own-child suspend refused")
                        suspended = True
                        time.sleep(0.25)  # Deliberate fault duration, not background-job polling.
                    finally:
                        status = ntdll.NtResumeProcess(handle) if suspended else -1
                        kernel.CloseHandle(handle)
                    if status != 0:
                        raise OSError("Own-child resume refused")
                stdout, _ = p.communicate("resume\n", timeout=10)
                data = json.loads(stdout.strip().splitlines()[-1])
                results.append(
                    {
                        "drill": "actual_own_child_suspend_resume",
                        "pass": p.returncode == 0 and data.get("elapsed_seconds", 0) >= 0.25,
                        "ready_seconds": ready_seconds,
                        **data,
                        "limitation": "Process pause only, not native laptop suspend or full engine polling loop",
                    }
                )
        except Exception as e:
            results.append({"drill": phase, "pass": False, "error_type": type(e).__name__})
        finally:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=5)
            if p.stdin:
                p.stdin.close()
            if p.stdout:
                p.stdout.close()
            if p.stderr:
                p.stderr.close()
    return results


def live_refusals(folder):
    results = []
    # Override only Settings loading and storage root in the child. Never read .env or provide keys.
    script = """
import sys
from pathlib import Path
from app import main as m
from app.config import Settings,StrategyConfig,RiskConfig,AppConfig,legacy_section,load_yaml
m.ROOT=Path(sys.argv[1])
m.load=lambda:(Settings(mode='live',_env_file=None),StrategyConfig(**legacy_section('config/strategy.yaml')),RiskConfig(**legacy_section('config/risk.yaml')),AppConfig(**load_yaml('config/app.yaml')))
sys.argv=['audit-live-refusal']+sys.argv[2:]
raise SystemExit(m.main())
"""
    for name, flags in (
        ("legacy", []),
        ("portfolio", ["--portfolio-paper"]),
        ("timing_A", ["--timing-paper", "--timing-candidate", "A"]),
        ("timing_D", ["--timing-paper", "--timing-candidate", "D"]),
    ):
        root = folder / name
        start = time.perf_counter()
        p = subprocess.run(
            [sys.executable, "-c", script, str(root), *flags],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        results.append(
            {
                "path": name,
                "exit_code": p.returncode,
                "pass": p.returncode == 2,
                "seconds": time.perf_counter() - start,
                "storage_isolated": True,
                "no_credentials_loaded": True,
            }
        )
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.forward_shadow",
            "--mode",
            "live",
            "--root",
            str(folder / "shadow_live"),
            "--max-seconds",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    results.append({"path": "forward_shadow", "exit_code": p.returncode, "pass": p.returncode == 2})
    return results


def secret_findings(text):
    """Return counts only; never return matched strings or credential values."""
    patterns = {
        "credential_assignment": r"(?im)^[ \t]*(?:BALE_BOT_TOKEN|NOBITEX_(?:PUBLIC|PRIVATE)_KEY|API_SECRET|PRIVATE_KEY)[ \t]*=[ \t]*['\"]?([^\s'\"#]{8,})",
        "bot_token_shape": r"\b\d{7,14}:[A-Za-z0-9_-]{25,}\b",
        "private_key_pem": r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
    }
    counts = {}
    for label, pattern in patterns.items():
        count = 0
        for match in re.finditer(pattern, text):
            value = match.group(1) if match.lastindex else match.group(0)
            if any(
                w in value.lower()
                for w in (
                    "example",
                    "placeholder",
                    "changeme",
                    "fake",
                    "redacted",
                    "invalid",
                    "your_",
                )
            ):
                continue
            count += 1
        if count:
            counts[label] = count
    return counts


def security_scan():
    findings = []
    count = 0
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(
            x in p.parts for x in (".venv", "__pycache__", ".ruff_cache", ".pytest_cache")
        ):
            continue
        if p.suffix.lower() not in (
            ".py",
            ".yaml",
            ".yml",
            ".md",
            ".json",
            ".jsonl",
            ".txt",
            ".log",
            ".toml",
        ) and p.name not in (".env", ".env.example", ".gitignore"):
            continue
        raw = p.read_bytes()
        try:
            text = (
                raw.decode("utf-16")
                if raw.startswith((b"\xff\xfe", b"\xfe\xff"))
                else raw.decode("utf-8-sig")
            )
        except UnicodeError:
            continue
        counts = secret_findings(text)
        count += 1
        if counts:
            findings.append(
                {
                    "file": p.relative_to(ROOT).as_posix(),
                    "counts": counts,
                    "classification": "synthetic_fixture_review"
                    if "tests" in p.parts
                    else "manual_review_required_no_values_exposed",
                }
            )
    ignore = (ROOT / ".gitignore").read_text()
    return {
        "warnings": [
            "Heuristic scan is NOT proof of secret absence or compromise freedom. Values are never printed. No Git repository is present, so historical exposure/remote commits cannot be audited.",
            "No offline vulnerability advisory database was supplied; dependency vulnerability scan NOT RUN. pip check is compatibility only.",
        ],
        "files_scanned": count,
        "findings": findings,
        "env_ignored": bool(re.search(r"(?m)^/?\.env\s*$", ignore)),
        "env_example_present": (ROOT / ".env.example").exists(),
        "git_present": (ROOT / ".git").exists(),
        "offline_scanner_installed": importlib.util.find_spec("pip_audit") is not None,
        "vulnerability_scan": "NOT_RUN_NO_OFFLINE_ADVISORY_DATABASE",
        "redaction_and_messenger_contract": "See full offline JUnit: test_notify_config.py; unknown IDs/forwarded/stale commands and redaction, not real Bale delivery",
    }


def memory_bytes():
    if os.name != "nt":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            *[
                (name, ctypes.c_size_t)
                for name in (
                    "PeakWorkingSetSize",
                    "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                )
            ],
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(Counters),
        ctypes.c_ulong,
    ]
    return (
        int(counters.WorkingSetSize)
        if psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        else None
    )


async def public_probes(folder):
    folder.mkdir(parents=True)
    rawfolder = folder / "raw"
    rawfolder.mkdir()
    records = []
    responses = {}
    start = time.perf_counter()
    cpu = time.process_time()
    now = int(time.time())
    coverage = json.loads((BASE / "results/coverage.json").read_text())
    windows = [
        (
            int(datetime.fromisoformat(v["start"].replace("Z", "+00:00")).timestamp())
            + 300 * 86400,
            int(datetime.fromisoformat(v["end"].replace("Z", "+00:00")).timestamp()) + 86400,
        )
        for v in coverage["common_segments"]
        if v["eligible_after_300_warmup"]
    ]
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(5, connect=3), trust_env=False, follow_redirects=False
    ) as http:

        async def get(label, path, params=None):
            began = time.perf_counter()
            status = None
            data = None
            error = None
            try:
                response = await http.get(
                    "https://apiv2.nobitex.ir" + path,
                    params=params,
                    headers={"User-Agent": "NobitexBaleTrader-FinalAudit-PUBLIC-ONLY"},
                )
                status = response.status_code
                payload = response.content
                with (rawfolder / (label + ".response")).open("xb") as f:
                    f.write(payload)
                if 200 <= status < 300:
                    data = response.json()
                    responses[label] = data
            except (httpx.HTTPError, ValueError) as e:
                error = type(e).__name__
            records.append(
                {
                    "label": label,
                    "path": path,
                    "params": params,
                    "status": status,
                    "error_type": error,
                    "seconds": time.perf_counter() - began,
                    "attempt": 1,
                    "retry": False,
                }
            )
            return data

        try:
            async with asyncio.timeout(45):
                await get("options", "/v2/options")
                for s in ("USDTIRT", "BTCIRT"):
                    await get("metadata_" + s, "/market/udf/symbols", {"symbol": s})
                    for segment, (left, right) in enumerate(windows):
                        part = 0
                        while left < right:
                            end = min(left + 490 * 86400, right)
                            await get(
                                f"history_{s}_{segment}_{part}",
                                "/market/udf/history",
                                {"symbol": s, "resolution": "D", "from": left, "to": end - 1},
                            )
                            left = end
                            part += 1
                            await asyncio.sleep(0.15)
                for i in range(6):
                    await get(f"book_{i}", "/v3/orderbook/BTCUSDT")
                    await asyncio.sleep(1.0)
        except TimeoutError:
            records.append(
                {"label": "outer_deadline", "status": None, "error_type": "Bounded45SecondDeadline"}
            )
    elapsed = time.perf_counter() - start
    write_csv(folder / "requests.csv", records)
    latencies = [r["seconds"] for r in records if "seconds" in r]
    statuses = [r.get("status") for r in records]
    with sqlite3.connect(folder / "telemetry.db") as db:
        db.execute("CREATE TABLE request (sequence INTEGER PRIMARY KEY, payload TEXT)")
        db.executemany(
            "INSERT INTO request VALUES (?,?)",
            [(i, json.dumps(r, sort_keys=True)) for i, r in enumerate(records)],
        )
    bytes_db = (folder / "telemetry.db").stat().st_size
    bytes_logs = (folder / "requests.csv").stat().st_size
    irt = {}
    fx_rows = {}
    for s in ("USDTIRT", "BTCIRT"):
        values = {}
        errors = 0
        for label, data in responses.items():
            if (
                not label.startswith("history_" + s)
                or not isinstance(data, dict)
                or data.get("s") != "ok"
            ):
                continue
            try:
                parsed = [
                    Candle(int(ts), float(o), float(h), float(low), float(close), float(v))
                    for ts, o, h, low, close, v in zip(*(data[k] for k in "tohlcv"), strict=True)
                ]
                for row in parsed:
                    if row.ts in values and values[row.ts] != row:
                        errors += 1
                    values[row.ts] = row
            except (ValueError, KeyError, TypeError):
                errors += 1
        metadata = responses.get("metadata_" + s, {})
        # Require explicit primary response quote-unit description, not inferred BTC cross-rates.
        unit_text = (
            " ".join(
                str(metadata.get(k, ""))
                for k in ("currency_code", "description", "currency", "quote_currency")
            )
            if isinstance(metadata, dict)
            else ""
        )
        unit_verified = "TOMAN" in unit_text.upper() or "تومان" in unit_text
        needed = {
            int(r["timestamp"])
            for r in __import__("csv").DictReader(
                (BASE / "results/curves.csv").open(encoding="utf-8")
            )
            if r["name"] == "B1"
        }
        irt[s] = {
            "genuine_validated_rows": len(values),
            "exact_common_matches": len(set(values) & needed),
            "needed": len(needed),
            "conflicting_or_invalid_pages": errors,
            "unit_verified": unit_verified,
            "unit_status": "EXPLICIT_TOMAN_METADATA"
            if unit_verified
            else "NOT_VERIFIED_IRT_VS_IRR_FROM_PRIMARY_RESPONSE",
            "exists_on_this_probe": bool(values),
            "fx_evaluation": "UNAVAILABLE_UNLESS_COMPLETE_VERIFIED_OVERLAP",
        }
        write_csv(folder / (s + "_genuine.csv"), [asdict(v) for _, v in sorted(values.items())])
        fx_rows[s] = values
    fx_info = irt["USDTIRT"]
    fx_info["fx_evaluation"] = "UNAVAILABLE_INCOMPLETE_OR_UNVERIFIED_UNITS"
    if (
        fx_info["unit_verified"]
        and fx_info["exact_common_matches"] == fx_info["needed"]
        and not fx_info["conflicting_or_invalid_pages"]
    ):
        curves = list(
            __import__("csv").DictReader((BASE / "results/curves.csv").open(encoding="utf-8"))
        )
        translated = []
        usd = json.loads((BASE / "results/summary.json").read_text())["pooled"]
        for name in dict.fromkeys(r["name"] for r in curves):
            previous_irt = 100.0
            compounded = 100.0
            segment = None
            converted = []
            for row in (r for r in curves if r["name"] == name):
                ts = int(row["timestamp"])
                fx = fx_rows["USDTIRT"][ts]
                if row["segment"] != segment:
                    usd_initial = float(row["equity"]) / (1 + float(row["return"]))
                    fx_initial = fx.open
                    segment = row["segment"]
                    segment_capital = compounded
                compounded = (
                    segment_capital * (float(row["equity"]) / usd_initial) * (fx.close / fx_initial)
                )
                converted.append(
                    {
                        "timestamp": ts,
                        "segment": segment,
                        "equity": compounded,
                        "return": compounded / previous_irt - 1,
                        "cost": None,
                        "notional": None,
                        "exposure": float(row["exposure"]) if row.get("exposure") else None,
                        "trips": None,
                        "legs": None,
                    }
                )
                previous_irt = compounded
            m = metrics(converted)
            translated.append(
                {
                    "name": name,
                    "exploratory": True,
                    "IRT_total_return": m["total_return"],
                    "IRT_max_drawdown": m["max_drawdown"],
                    "USD_total_return": usd[name]["total_return"],
                    "USD_max_drawdown": usd[name]["max_drawdown"],
                    "note": "Exact raw daily FX only; FX resets at segment boundaries; normalized returns, not fabricated FX trades or tax accounting",
                }
            )
        for key in ("IRT_total_return", "USD_total_return"):
            order = sorted(translated, key=lambda r: r[key], reverse=True)
            for rank, row in enumerate(order, 1):
                row[key + "_rank"] = rank
        write_csv(folder / "IRT_exploratory_metrics.csv", translated)
        write_json(folder / "IRT_exploratory_metrics.json", translated)
        fx_info["fx_evaluation"] = "EXPLORATORY_COMPLETE_EXACT_FX_TRANSLATION"
    result = {
        "warnings": [
            "Tiny bounded public sample, not an SLA. Initial setup and one-off page downloads dominate file-growth projections. No retries were attempted; retry rate=0 by design, not evidence that retries never occur.",
            "Historical IRT translation is unavailable unless quote units AND every exact daily timestamp are verified. Do not infer or interpolate FX.",
        ],
        "observed_execution_utc": datetime.now(UTC).isoformat(),
        "execution_clock_unix": now,
        "elapsed_seconds": elapsed,
        "requests": len(records),
        "status_counts": {str(v): statuses.count(v) for v in set(statuses)},
        "latency_seconds_p50_p95_max": [float(x) for x in np.quantile(latencies, [0.5, 0.95, 1])]
        if latencies
        else None,
        "timeout_count": sum(
            "Timeout" in (r.get("error_type") or "") or "Deadline" in (r.get("error_type") or "")
            for r in records
        ),
        "retry_count": 0,
        "rate_limit_hits": statuses.count(429),
        "startup_first_options_seconds": records[0].get("seconds"),
        "startup_to_shadow_ready_seconds": None,
        "cpu_seconds": time.process_time() - cpu,
        "working_set_bytes": memory_bytes(),
        "file_growth": {
            "request_log_bytes": bytes_logs,
            "telemetry_db_bytes": bytes_db,
            "projected_30day_log_bytes_linear": int(bytes_logs / elapsed * 86400 * 30),
            "projected_30day_db_bytes_linear": int(bytes_db / elapsed * 86400 * 30),
            "validity": "VERY_LOW_CONFIDENCE_STARTUP_DOMINATED_DO_NOT_SIZE_PRODUCTION_FROM_THIS",
        },
        "IRT": irt,
    }
    write_json(folder / "public_probes.json", result)
    write_json(folder / "raw_hashes.json", {p.name: digest(p) for p in rawfolder.iterdir()})
    return result


def old_log_summary():
    path = ROOT / "logs/bot.jsonl"
    if not path.exists():
        return {"status": "no prior log"}
    dates = []
    count = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        count += 1
        for key in ("time", "timestamp", "ts", "asctime"):
            value = row.get(key)
            if isinstance(value, str):
                try:
                    dates.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
                except ValueError:
                    pass
    return {
        "file": "logs/bot.jsonl",
        "bytes": path.stat().st_size,
        "json_records": count,
        "parseable_timestamps": len(dates),
        "content_not_exposed": True,
        "startup_to_ready": "UNAVAILABLE_NOT_INFERRED_FROM_UNSTRUCTURED_MESSAGES",
        "per_day_growth": "UNAVAILABLE_NO_CONTINUOUS_ACTIVITY_DENOMINATOR",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=BASE / "operations")
    p.add_argument("--public", action="store_true")
    args = p.parse_args()
    out = confined(args.output)
    if out.exists():
        print("Refused: output already exists")
        return 2
    out.mkdir(parents=True)
    drills = process_drills(out / "faults")
    live = live_refusals(out / "live_refusal")
    security = security_scan()
    write_json(out / "security.json", security)
    write_json(
        out / "reliability.json",
        {
            "warnings": [
                "Local/mock drills only; no real orders, real laptop sleep, Task Scheduler, real Bale delivery, or all hypothetical LIVE bypasses are certified.",
                "Storage corruption/lock, stale/skew, duplicate process, KILL, network/timeout and command-whitelist contracts are covered by separately recorded offline tests. Test elapsed durations are not real venue recovery times.",
            ],
            "process_drills": drills,
            "live_refusals": live,
            "prior_log_measurements": old_log_summary(),
            "all_owned_children_reaped": True,
        },
    )
    if args.public:
        asyncio.run(public_probes(out / "public"))
    print(
        json.dumps(
            {
                "local_drills": len(drills),
                "local_passes": sum(r["pass"] for r in drills),
                "live_refusals": live,
                "secret_scan_files": security["files_scanned"],
                "secret_pattern_files": len(security["findings"]),
            }
        )
    )
    return 0 if all(r["pass"] for r in drills + live) else 1


if __name__ == "__main__":
    raise SystemExit(main())
