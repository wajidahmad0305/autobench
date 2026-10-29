"""One-off diagnostic: C1 (qwen/qwen3.8-27b) vs C2 (openai/gpt-oss-120b) on
crm_order_fulfilment task_002 and task_001, one trial each.

Not part of the pilot and writes no trace files. Reuses the pilot's exact
trajectory machinery (tool-spec synthesis, fault env, 90s/15K watchdog kill
switches, evaluator) so the outcome matches what run_pilot.py would produce.

Usage:  python scripts/diagnose_c2_vs_c1.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from run_pilot import _load_env, _run_trajectory_with_retries  # sibling module in scripts/

from autobench.schema import load_task

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_SEED = 20260827

_pilot = json.loads(
    (REPO_ROOT / "experiments" / "thesis_pilot" / "config.json").read_text(encoding="utf-8")
)
CONFIGS: list[dict[str, Any]] = list(_pilot["configurations"])


def _outcome(record: dict[str, Any]) -> str:
    if record["status"] in ("PASS", "FAIL"):
        return str(record["status"])
    reason = record.get("reason")
    if reason == "timeout":
        return "TIMEOUT"
    if reason == "token_cap":
        return "TOKEN_CAP"
    return "ERROR"


def _run(task_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    task = load_task(str(REPO_ROOT / "tasks" / "crm_order_fulfilment" / f"{task_id}.json"))
    start = time.monotonic()
    record = _run_trajectory_with_retries(cfg, task, 0, MASTER_SEED)
    elapsed_ms = (time.monotonic() - start) * 1000.0

    tele = record.get("telemetry", {})
    calls = tele.get("tool_calls", [])
    metrics = record.get("metrics", {})
    return {
        "config": cfg["config_id"],
        "model": cfg["model_name"],
        "task": task.task_id,
        "outcome": _outcome(record),
        "tsi": metrics.get("tsi"),
        "sec": metrics.get("sec"),
        "tool_calls": len(calls),
        "wall_clock_ms": round(elapsed_ms),
        "adapter_wall_ms": round(tele.get("wall_clock_time_ms", 0.0)),
        "tokens": tele.get("total_tokens", 0),
        "failed_assertions": metrics.get("failed_assertions", []),
        "last_5": [(c["tool_name"], c["arguments"]) for c in calls[-5:]],
        "error": record.get("error"),
    }


def _print_row(r: dict[str, Any]) -> None:
    print(f"  {r['config']}  {r['model']}")
    print(f"    outcome       : {r['outcome']}    tsi={r['tsi']}  sec={r['sec']}")
    print(f"    tool_calls    : {r['tool_calls']}")
    print(f"    wall_clock_ms : {r['wall_clock_ms']}  (adapter-recorded {r['adapter_wall_ms']})")
    print(f"    tokens        : {r['tokens']}")
    if r["error"]:
        print(f"    error         : {r['error']}")
    if r["failed_assertions"]:
        print("    failed_assertions:")
        for fa in r["failed_assertions"]:
            print(f"      - {fa}")
    print("    last 5 tool calls:")
    for name, args in r["last_5"]:
        print(f"      - {name}  {args}")


def main() -> int:
    _load_env()
    results: list[dict[str, Any]] = []
    for task_id in ("task_001", "task_002"):
        print("=" * 78)
        print(f"TASK  crm_order_fulfilment/{task_id}.json")
        print("=" * 78)
        for cfg in CONFIGS:
            row = _run(task_id, cfg)
            results.append(row)
            _print_row(row)
            print()

    passed = sum(1 for r in results if r["outcome"] == "PASS")
    print("=" * 78)
    print(f"OVERALL: {passed}/{len(results)} trajectories PASS")
    for r in results:
        print(f"  {r['config']} {r['task']}: {r['outcome']}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

