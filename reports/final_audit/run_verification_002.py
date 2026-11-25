"""Fresh, bounded replay recovery; preserve the timed-out first attempt."""

import concurrent.futures
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

BASE = Path("reports/final_audit")
OUTPUTS = ("results_verified_002", "replay_verified_002")


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def hashes(root):
    return {
        p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def run(name):
    started = time.perf_counter()
    command = [
        sys.executable,
        "-m",
        "backtest.final_audit",
        "--snapshot",
        str(BASE / "inputs"),
        "--output",
        str(BASE / name),
    ]
    with (BASE / (name + "_run.log")).open("x", encoding="utf-8") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        save(
            BASE / (name + "_started.json"),
            {"pid": child.pid, "utc": datetime.now(UTC).isoformat(), "timeout_seconds": 1800},
        )
        try:
            exit_code = child.wait(timeout=1800)
            timed_out = False
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            exit_code = child.returncode
            timed_out = True
    result = {
        "output": name,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "seconds": time.perf_counter() - started,
        "child_reaped": child.poll() is not None,
    }
    save(BASE / (name + "_completion.json"), result)
    return result


def main():
    for name in OUTPUTS:
        for path in (
            BASE / name,
            BASE / (name + "_run.log"),
            BASE / (name + "_started.json"),
            BASE / (name + "_completion.json"),
        ):
            if path.exists():
                raise FileExistsError("Recovery evidence exists; never overwrite")
    evidence_path = BASE / "byte_replay_verified_002.json"
    if evidence_path.exists():
        raise FileExistsError("Comparison exists")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, OUTPUTS))
    a, b = [hashes(BASE / name) for name in OUTPUTS]
    original = hashes(BASE / "results")
    original_replay = hashes(BASE / "replay")
    same = sorted(k for k in a if a.get(k) == b.get(k))
    mismatch = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    economic_keys = sorted(
        k for k in original if not k.startswith("charts/") and k != "artifact_hashes.json"
    )
    economic_drift = [
        k for k in economic_keys if a.get(k) != original[k] or b.get(k) != original[k]
    ]
    complete = all(
        r["exit_code"] == 0 and not r["timed_out"] and r["child_reaped"] for r in results
    ) and set(a) == set(original) == set(b)
    evidence = {
        "warning": "Post-results visual correction only. Failed first attempts retained separately; historical contamination and protocol provenance remain unresolved.",
        "runs": results,
        "complete": complete,
        "identical_artifacts": len(same),
        "mismatches": mismatch,
        "non_chart_artifact_count": len(economic_keys),
        "non_chart_drift_from_original": economic_drift,
        "original_pair_still_byte_identical": original == original_replay,
        "chart_changes_from_original": [
            k for k in a if k.startswith("charts/") and a[k] != original.get(k)
        ],
        "results_hashes": a,
        "replay_hashes": b,
        "pass": complete and not mismatch and not economic_drift and original == original_replay,
    }
    save(evidence_path, evidence)
    print(json.dumps({k: v for k, v in evidence.items() if not k.endswith("hashes")}, indent=2))
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
