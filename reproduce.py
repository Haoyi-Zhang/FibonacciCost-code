"""Fresh one-worker reproduction with bounded children and reconciliation.

The destination must not exist. No retained measurement is overwritten. Timing
and process measurements are compared descriptively, not for bit equality.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from platform_support import environment_record, require_supported_environment

MEASUREMENTS = {
    "seconds",
    "cpu_seconds",
    "wall_seconds",
    "peak_rss_kib",
    "setup_seconds",
    "update_seconds",
    "total_seconds",
}


def stable(value):
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key not in MEASUREMENTS}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        help="new output directory, outside retained results; it must not already exist",
    )
    parser.add_argument(
        "--check-environment",
        action="store_true",
        help="validate and print the supported Linux runtime without running the campaign",
    )
    args = parser.parse_args()

    resource = require_supported_environment("reproduce.py")
    runtime = environment_record("reproduce.py", resource)
    if args.check_environment:
        print(json.dumps(runtime, indent=2, sort_keys=True))
        if args.out is None:
            return
    if args.out is None:
        parser.error("--out is required unless --check-environment is used alone")

    out = Path(args.out).resolve()
    if out.exists():
        raise SystemExit("output exists; select a fresh directory")
    out.mkdir(parents=True)

    start = time.perf_counter()
    cpu0 = time.process_time()
    commands: list[dict[str, object]] = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def run(parts: list[object]) -> None:
        command = [sys.executable, *[str(part) for part in parts]]
        tick = time.perf_counter()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        record: dict[str, object] = {"command": [str(part) for part in parts]}
        try:
            child = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=40,
            )
            record.update(
                exit_code=child.returncode,
                stdout=child.stdout,
                stderr=child.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            record.update(
                exit_code=None,
                status="timeout",
                stdout=str(exc.stdout or ""),
                stderr=str(exc.stderr or ""),
            )
            commands.append(record)
            (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
            raise SystemExit(
                "child timeout; partial outputs are retained, no completion claim"
            ) from exc
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record.update(
            wall_seconds=time.perf_counter() - tick,
            child_cpu_seconds=(
                after.ru_utime
                + after.ru_stime
                - before.ru_utime
                - before.ru_stime
            ),
        )
        commands.append(record)
        (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if child.returncode:
            raise SystemExit("child failed; inspect commands.json")
        print(parts[0], "exit=0", flush=True)

    run(["tests/check_bibliography.py", "--out", out / "bibliography_validation.json"])
    run(["tests/check_evaluation.py", "--out", out / "evaluation-regressions"])
    run(["tests/check_baselines.py", "--out", out / "baseline_checks.json"])
    run(["pilot.py", "--out", out / "pilot.json"])
    run(["tests/check_all.py", "--out", out / "checks.json"])
    run(["tests/check_amplification.py", "--out", out / "amplification.json"])
    run(["tests/check_support_envelope.py", "--out", out / "support_envelope.json"])
    run(["tests/check_rational_model.py", "--out", out / "rational_checks.json"])
    for first, last in ((0, 20), (20, 40), (40, 60)):
        run(["benchmark.py", "--start", first, "--stop", last, "--out", out / "campaign"])
    run(["summarize.py", "--root", out / "campaign", "--out", out])

    compared = 0
    deterministic_reports = (
        "bibliography_validation.json",
        "pilot.json",
        "checks.json",
        "amplification.json",
        "support_envelope.json",
        "rational_checks.json",
    )
    for name in deterministic_reports:
        old = json.loads((ROOT / "results" / name).read_text())
        new = json.loads((out / name).read_text())
        if stable(old) != stable(new):
            raise SystemExit("deterministic check mismatch: " + name)

    config = json.loads((ROOT / "inputs/campaign.json").read_text())
    for spec in config["cases"]:
        name = spec["id"] + ".json"
        old = json.loads((ROOT / "results/campaign" / name).read_text())
        new = json.loads((out / "campaign" / name).read_text())
        if stable(old) != stable(new):
            raise SystemExit("deterministic campaign mismatch: " + name)
        compared += len(new["runs"])

    old = json.loads((ROOT / "results/summary.json").read_text())
    new = json.loads((out / "summary.json").read_text())
    lookup = lambda summary: {
        (aggregate["family"], aggregate["method"]): aggregate
        for aggregate in summary["aggregates"]
    }
    primary, reproduced = lookup(old), lookup(new)
    ratios = [
        {
            "family": family,
            "primary_exact_over_full": primary[family, "exact"]["total_ratio"],
            "reproduction_exact_over_full": reproduced[family, "exact"]["total_ratio"],
        }
        for family in ("independent", "coupled", "relay", "all")
    ]

    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {
        "status": "passed",
        "environment": runtime,
        "deterministic_timed_searches_compared": compared,
        "deterministic_fields": (
            "input bytes decoded as JSON; graphs/dimensions; costs; all work "
            "counters; search status/cost/expansions/generated; scalar factors"
        ),
        "excluded_from_equality": sorted(MEASUREMENTS),
        "timing_comparison": ratios,
        "child_cpu_seconds": child.ru_utime + child.ru_stime,
        "parent_cpu_seconds": time.process_time() - cpu0,
        "wall_seconds": time.perf_counter() - start,
        "child_peak_rss_kib": child.ru_maxrss,
        "workers": 1,
    }
    (out / "reproduction.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
