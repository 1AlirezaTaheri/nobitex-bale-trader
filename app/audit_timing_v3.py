"""Audit frozen Timing V3 inputs, summaries, reports, and byte-identical replay."""

import argparse
import csv
import json
import math
from hashlib import sha256
from pathlib import Path

from app.config import ROOT


def _files(path):
    return {item.relative_to(path) for item in path.rglob("*") if item.is_file()}


def _rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def audit(source: Path, replay: Path | None = None):
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    manifest_path = source / "inputs/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256(manifest_path.read_bytes()).hexdigest() != summary["input_manifest_sha256"]:
        raise ValueError("Summary/input manifest hash mismatch")
    for label, item in manifest["files"].items():
        data = source / "inputs" / item["file"]
        if sha256(data.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Input checksum mismatch: {label}")
        rows = _rows(data)
        if len(rows) != item["rows"] or len({row["timestamp"] for row in rows}) != len(rows):
            raise ValueError(f"Input row count or timestamp uniqueness mismatch: {label}")
    fee_path = source / "inputs/fee_observation.json"
    if sha256(fee_path.read_bytes()).hexdigest() != manifest["fee_observation_sha256"]:
        raise ValueError("Fee observation checksum mismatch")
    protocol = ROOT / "docs/STRATEGY_V3_PREREGISTRATION.md"
    protocol_hash = sha256(protocol.read_bytes()).hexdigest()
    if not (
        summary["protocol_sha256"]
        == protocol_hash
        == "6f26ccabb14fa92b477a94b873f3309a0eb9b30a3d873118def5fa81ec3489af"
    ):
        raise ValueError("Protocol document or summary differs from the frozen checksum")

    acceptance = _rows(source / "acceptance.csv")
    if len(acceptance) != 28:
        raise ValueError("Expected seven acceptance results for each of four candidates")
    by_candidate = {name: [] for name in "ABCD"}
    for row in acceptance:
        by_candidate[row["candidate"]].append(row)
    report = (source / "report.md").read_text(encoding="utf-8")
    metrics = {row["name"]: row for row in _rows(source / "metrics.csv")}
    for name, candidate in summary["candidates"].items():
        if candidate["enabled"] or candidate["status"] != "NOT VALIDATED":
            raise ValueError(f"Candidate {name} is enabled or has an unexpected status")
        if len(by_candidate[name]) != 7:
            raise ValueError(f"Candidate {name} has an unexpected acceptance row count")
        expected = [
            (key, "PASS" if passed else "FAIL") for key, passed in candidate["acceptance"].items()
        ]
        if [(row["criterion"], row["result"]) for row in by_candidate[name]] != expected:
            raise ValueError(f"Acceptance CSV disagrees with summary for {name}")
        if f"| {name} | NOT VALIDATED |" not in report:
            raise ValueError(f"Markdown candidate verdict disagrees for {name}")
        row = metrics[name]
        for field, value in candidate["metrics"]["full"].items():
            if (
                isinstance(value, (int, float))
                and field in row
                and not math.isclose(float(row[field]), float(value), rel_tol=1e-12, abs_tol=1e-12)
            ):
                raise ValueError(f"Metric CSV disagrees with summary: {name}.{field}")
        null = candidate["random_timing_null"]
        if null["trials"] != 999 or abs(null["reconstruction_return_error"]) > 1e-12:
            raise ValueError(f"Timing-null run or reconstruction mismatch for {name}")
        if (
            not 0 <= null["share_net_return_ge_actual"] <= 1
            or not 0 <= null["share_calmar_ge_actual"] <= 1
        ):
            raise ValueError(f"Timing-null proportions out of range for {name}")
        if "share_net_return_ge_unshifted_reconstruction" in null:
            raise ValueError(f"Obsolete timing-null comparison remains for {name}")

    replay_count = None
    if replay:
        source_files, replay_files = _files(source), _files(replay)
        if source_files != replay_files:
            raise ValueError("Source and replay artifact file sets differ")
        differences = [
            str(name)
            for name in sorted(source_files, key=str)
            if (source / name).read_bytes() != (replay / name).read_bytes()
        ]
        if differences:
            raise ValueError("Byte-identical replay mismatch: " + ", ".join(differences))
        replay_count = len(source_files)
    return {
        "input_files": len(manifest["files"]) + 1,
        "acceptance_rows": len(acceptance),
        "candidate_statuses": {
            name: item["status"] for name, item in summary["candidates"].items()
        },
        "protocol_sha256": summary["protocol_sha256"],
        "byte_identical_replay": bool(replay),
        "byte_identical_file_count": replay_count,
        "artifact_audit": "PASS",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "reports/timing_v3")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.source, args.replay), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
