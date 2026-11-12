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
from math import comb
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = REPO_ROOT / "experiments" / "thesis_pilot"
TRACES_DIR = PILOT_DIR / "traces"
CONFIG_PATH = PILOT_DIR / "config.json"
OUT_PATH = PILOT_DIR / "analysis" / "summary.md"

_ASSERTION_KEY_RE = re.compile(r"^(state|tool_call)\[([^\]]+)\]")

# C3 was a halted partial run (26 of 180 trials). It is excluded from every reported result.
EXCLUDED_CONFIGS = {"C3"}


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
        if path.name.split("__")[0] in EXCLUDED_CONFIGS:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("config_id") in EXCLUDED_CONFIGS:
            continue
        traces.append(data)
    return traces


def _expected_grid() -> tuple[list[str], list[str], int]:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config_ids = [c["config_id"] for c in cfg["configurations"] if c["config_id"] not in EXCLUDED_CONFIGS]
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


# ------------------------------------------------------- pass^k and hypotheses


def _pass_hat_k(traces: list[dict[str, Any]], config_ids: list[str], k: int) -> dict[str, float | None]:
    """Unbiased estimator: per task, C(c,k)/C(m,k) with c passes out of m trials; averaged over tasks."""
    out: dict[str, float | None] = {}
    for cid in config_ids:
        by_task: dict[str, list[int]] = defaultdict(list)
        for t in traces:
            if t.get("config_id") == cid:
                by_task[str(t.get("task_id"))].append(1 if _is_pass(t) else 0)
        vals = []
        for results in by_task.values():
            m = len(results)
            if m < k:
                continue
            vals.append(comb(sum(results), k) / comb(m, k))
        out[cid] = _mean(vals) if vals else None
    return out


def _table6_pass_k(traces: list[dict[str, Any]], config_ids: list[str]) -> tuple[str, dict[str, float | None], dict[str, float | None]]:
    p1 = _pass_hat_k(traces, config_ids, 1)
    p3 = _pass_hat_k(traces, config_ids, 3)
    rows: list[list[Any]] = []
    for cid in config_ids:
        if p1[cid] is None or p3[cid] is None:
            continue
        gap = (p1[cid] - p3[cid]) * 100.0
        rows.append([cid, f"{p1[cid]:.1%}", f"{p3[cid]:.1%}", f"{gap:.1f}", "yes" if gap >= 10.0 else "no"])
    table = _md_table(["config_id", "pass^1", "pass^3", "gap_pp", "gap_at_least_10pp"], rows)
    return table, p1, p3


def _hypothesis_checks(traces: list[dict[str, Any]], config_ids: list[str],
                       p1: dict[str, float | None], p3: dict[str, float | None]) -> str:
    lines: list[str] = []
    # H1: pass rate per primary configuration below 50 percent
    h1 = all(p1[c] is not None and p1[c] < 0.5 for c in config_ids)
    lines.append(f"- H1 (each configuration pass rate below 50%): {'supported' if h1 else 'not supported'}")
    # H2: pooled fault recovery below 50 percent (trajectory level)
    faulted = [t for t in traces if _metric(t, "faults_encountered", 0) > 0]
    recovered = sum(1 for t in faulted if _metric(t, "fault_recovered", None) is True)
    rate = recovered / len(faulted) if faulted else 0.0
    lines.append(
        f"- H2 (pooled fault recovery below 50%): {'supported' if rate < 0.5 else 'not supported'} "
        f"({recovered} of {len(faulted)} faulted trajectories recovered)"
    )
    # H3: IT access provisioning is the lowest category in each configuration
    h3 = True
    for cid in config_ids:
        by_cat: dict[str, list[int]] = defaultdict(list)
        for t in traces:
            if t.get("config_id") == cid:
                by_cat[_category(str(t.get("task_id")))].append(1 if _is_pass(t) else 0)
        rates = {c: sum(v) / len(v) for c, v in by_cat.items() if v}
        if not rates or min(rates, key=rates.get) != "it_access_provisioning":
            h3 = False
    lines.append(f"- H3 (IT access provisioning lowest in each configuration): {'supported' if h3 else 'not supported'}")
    # H4: pass^3 at least 10 points below pass^1 for at least one configuration
    h4 = any(p1[c] is not None and p3[c] is not None and (p1[c] - p3[c]) * 100.0 >= 10.0 for c in config_ids)
    lines.append(f"- H4 (pass^3 at least 10 points below pass^1 for at least one configuration): {'supported' if h4 else 'not supported'}")
    return "\n".join(lines)


# ----------------------------------------------------------------------- main


def build_summary() -> str:
    traces = _load_traces()
    config_ids, _task_ids, _trials = _expected_grid()
    n = len(traces)

    coverage_table, present, expected = _table5_coverage(traces)

    total_tokens = sum(int(_tel(t, "total_tokens", 0)) for t in traces)
    prompt_tokens = sum(int(_tel(t, "prompt_tokens", 0)) for t in traces)
    completion_tokens = sum(int(_tel(t, "completion_tokens", 0)) for t in traces)

    mtimes = sorted(
        f.stat().st_mtime
        for f in TRACES_DIR.glob("*.json")
        if f.name.split("__")[0] not in EXCLUDED_CONFIGS
    ) if TRACES_DIR.is_dir() else []
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
    p6_table, p1, p3 = _table6_pass_k(traces, config_ids) if traces else ("_No traces._", {}, {})
    parts.append("\n## Table 5 - Coverage matrix\n")
    parts.append(coverage_table)
    parts.append("\n## Table 6 - pass^1 and pass^3 (unbiased estimator)\n")
    parts.append(p6_table)
    parts.append("\n## Hypothesis checks (H1-H4)\n")
    parts.append(_hypothesis_checks(traces, config_ids, p1, p3) if traces else "_No traces._")
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
