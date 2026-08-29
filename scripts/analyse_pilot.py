"""Aggregate ``experiments/thesis_pilot/traces/*.json`` into a markdown summary.

Works for any number of trace files (1..120). Writes
``experiments/thesis_pilot/analysis/summary.md`` and echoes it to stdout.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = REPO_ROOT / "experiments" / "thesis_pilot"
TRACES_DIR = PILOT_DIR / "traces"
CONFIG_PATH = PILOT_DIR / "config.json"
OUT_PATH = PILOT_DIR / "analysis" / "summary.md"

_ASSERTION_KEY_RE = re.compile(r"^(state|tool_call)\[([^\]]+)\]")


# ------------------------------------------------------------------- accessors


def _metric(trace: dict[str, Any], key: str, default: Any = 0.0) -> Any:
    return trace.get("metrics", {}).get(key, default)


def _tel(trace: dict[str, Any], key: str, default: Any = 0) -> Any:
    return trace.get("telemetry", {}).get(key, default)


def _is_pass(trace: dict[str, Any]) -> bool:
    return trace.get("status") == "PASS" or (
        _metric(trace, "tsi") == 1.0 and _metric(trace, "sec") == 1.0
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _category(task_id: str) -> str:
    return task_id.rsplit(".", 1)[0]


# --------------------------------------------------------------------- loading


def _load_traces() -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    if not TRACES_DIR.is_dir():
        return traces
    for path in sorted(TRACES_DIR.glob("*.json")):
        try:
            traces.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return traces


def _expected_grid() -> tuple[list[str], list[str], int]:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config_ids = [c["config_id"] for c in cfg["configurations"]]
    trials = int(cfg["trials_per_task"])
    task_ids: list[str] = []
    for category in cfg["task_categories"]:
        for task_file in sorted((REPO_ROOT / cfg["task_pool"] / category).glob("task_*.json")):
            task_ids.append(json.loads(task_file.read_text(encoding="utf-8"))["task_id"])
    return config_ids, task_ids, trials


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------------- tables


def _table1_leaderboard(traces: list[dict[str, Any]], config_ids: list[str]) -> str:
    rows: list[list[Any]] = []
    for cid in config_ids:
        sub = [t for t in traces if t.get("config_id") == cid]
        if not sub:
            continue
        errors = [t for t in sub if t.get("status") == "ERROR"]
        completed = [t for t in sub if t.get("status") != "ERROR"]
        passes = sum(1 for t in sub if _is_pass(t))
        rows.append(
            [
                cid,
                len(sub),
                f"{passes / len(sub):.1%}",
                f"{_mean([_metric(t, 'tsi') for t in completed]):.3f}",
                f"{_mean([_metric(t, 'sec') for t in completed]):.3f}",
                f"{_mean([_metric(t, 'sla_compliance') for t in completed]):.3f}",
                f"{_mean([_metric(t, 'duration_ms') for t in completed]):.0f}",
                f"{_mean([float(_tel(t, 'prompt_tokens')) for t in completed]):.0f}",
                f"{_mean([float(_tel(t, 'completion_tokens')) for t in completed]):.0f}",
                len(errors),
            ]
        )
    headers = [
        "config_id", "trials", "pass_rate", "mean_tsi", "mean_sec",
        "mean_sla_compliance", "mean_latency_ms", "mean_prompt_tokens",
        "mean_completion_tokens", "error_count",
    ]
    note = (
        "\n\n_pass_rate = (tsi==1 AND sec==1) / trials (ERRORs count as non-pass). "
        "mean_* are over completed (non-ERROR) trajectories._"
    )
    return _md_table(headers, rows) + note


def _table2_per_category(traces: list[dict[str, Any]], config_ids: list[str]) -> str:
    categories = sorted({_category(t["task_id"]) for t in traces})
    rows: list[list[Any]] = []
    for category in categories:
        row: list[Any] = [category]
        for cid in config_ids:
            sub = [
                t
                for t in traces
                if t.get("config_id") == cid and _category(t["task_id"]) == category
            ]
            passes = sum(1 for t in sub if _is_pass(t))
            row.append(len(sub))
            row.append(f"{passes / len(sub):.1%}" if sub else "-")
        rows.append(row)
    headers = ["category"]
    for cid in config_ids:
        headers += [f"{cid}_trials", f"{cid}_pass_rate"]
    return _md_table(headers, rows)


def _table3_failure_modes(traces: list[dict[str, Any]]) -> str:
    counter: Counter[str] = Counter()
    for trace in traces:
        if trace.get("status") != "FAIL":
            continue
        for assertion in _metric(trace, "failed_assertions", []):
            match = _ASSERTION_KEY_RE.match(str(assertion))
            key = f"{match.group(1)}[{match.group(2)}]" if match else str(assertion)[:70]
            counter[key] += 1
    if not counter:
        return "_No failed_assertions recorded on FAIL trajectories._"
    rows = [[key, count] for key, count in counter.most_common(10)]
    return _md_table(["assertion_key", "occurrences"], rows)


def _table4_fault_recovery(traces: list[dict[str, Any]]) -> str:
    agg: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for trace in traces:
        if _metric(trace, "faults_encountered", 0) <= 0:
            continue
        cid = str(trace.get("config_id", "?"))
        recovered = _metric(trace, "fault_recovered", None) is True
        fault_types = {
            str(tc.get("fault_injected"))
            for tc in _tel(trace, "tool_calls", [])
            if tc.get("fault_injected")
        }
        for fault_type in fault_types or {"UNKNOWN"}:
            agg[(cid, fault_type)][0] += 1
            if recovered:
                agg[(cid, fault_type)][1] += 1
    if not agg:
        return "_No trajectories with faults_encountered > 0 (no fault_injection_rules in the pilot tasks)._"
    rows: list[list[Any]] = []
    for (cid, fault_type), (count, recovered_count) in sorted(agg.items()):
        rate = f"{recovered_count / count:.1%}" if count else "n/a"
        rows.append([cid, fault_type, count, recovered_count, rate])
    return _md_table(["config_id", "fault_type", "count", "recovered_count", "recovery_rate"], rows)


def _table5_coverage(traces: list[dict[str, Any]]) -> tuple[str, int, int]:
    config_ids, task_ids, trials = _expected_grid()
    filled = {
        (t.get("config_id"), t.get("task_id"), t.get("trial_index")) for t in traces
    }
    expected = len(config_ids) * len(task_ids) * trials
    present = 0
    rows: list[list[Any]] = []
    for cid in config_ids:
        for tid in task_ids:
            cells = []
            for trial in range(trials):
                hit = (cid, tid, trial) in filled
                present += int(hit)
                cells.append("x" if hit else ".")
            rows.append([cid, tid, " ".join(cells)])
    table = _md_table(["config", "task", f"trials 0..{trials - 1}"], rows)
    return table, present, expected


# ----------------------------------------------------------------------- main


def build_summary() -> str:
    traces = _load_traces()
    config_ids, _task_ids, _trials = _expected_grid()
    n = len(traces)

    coverage_table, present, expected = _table5_coverage(traces)

    total_tokens = sum(int(_tel(t, "total_tokens", 0)) for t in traces)
    prompt_tokens = sum(int(_tel(t, "prompt_tokens", 0)) for t in traces)
    completion_tokens = sum(int(_tel(t, "completion_tokens", 0)) for t in traces)

    mtimes = sorted(f.stat().st_mtime for f in TRACES_DIR.glob("*.json")) if TRACES_DIR.is_dir() else []
    if mtimes:
        first = datetime.fromtimestamp(mtimes[0], tz=timezone.utc)
        last = datetime.fromtimestamp(mtimes[-1], tz=timezone.utc)
        span = f"{first.isoformat(timespec='seconds')} -> {last.isoformat(timespec='seconds')} " \
               f"({timedelta(seconds=int(mtimes[-1] - mtimes[0]))})"
    else:
        span = "n/a"

    outcomes = Counter(t.get("status", "?") for t in traces)
    coverage_pct = (present / expected * 100.0) if expected else 0.0

    parts: list[str] = []
    parts.append("# AutoBench Thesis Pilot - Summary\n")
    parts.append(f"- **Total:** {n}/{expected}")
    parts.append(
        f"- **Total tokens consumed:** {total_tokens:,} "
        f"(prompt {prompt_tokens:,}, completion {completion_tokens:,})"
    )
    parts.append(f"- **Wall-clock time span:** {span}")
    parts.append(f"- **Coverage:** {present}/{expected} = {coverage_pct:.1f}%")
    parts.append(
        f"- **Outcomes:** PASS {outcomes.get('PASS', 0)}, "
        f"FAIL {outcomes.get('FAIL', 0)}, ERROR {outcomes.get('ERROR', 0)}"
    )
    parts.append(f"- _Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_\n")

    parts.append("## Table 1 - Headline leaderboard\n")
    parts.append(_table1_leaderboard(traces, config_ids) if traces else "_No traces._")
    parts.append("\n## Table 2 - Per-category pass rate\n")
    parts.append(_table2_per_category(traces, config_ids) if traces else "_No traces._")
    parts.append("\n## Table 3 - Failure-mode breakdown (top 10)\n")
    parts.append(_table3_failure_modes(traces))
    parts.append("\n## Table 4 - Fault recovery\n")
    parts.append(_table4_fault_recovery(traces))
    parts.append("\n## Table 5 - Coverage matrix\n")
    parts.append(coverage_table)
    parts.append("")
    return "\n".join(parts)


def main() -> int:
    summary = build_summary()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\n[written] {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
