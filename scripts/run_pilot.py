"""AutoBench pilot runner: configurations x tasks x K trials.

One JSON trace per trajectory is written under the config's ``output_dir``.
Those files ARE the checkpoint: re-running skips any trajectory whose trace
already exists. No parallelism, no checkpoint DB.

Schema note: the schema has no ``task.prompt`` / ``task.tools``; the prompt is
``context.system_prompt`` + ``user_message`` and tool specs are synthesized from
``context.available_tools`` (there is no shared tool registry yet).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

import httpx
import structlog
from dotenv import load_dotenv

from autobench.adapters.base import TrajectoryTelemetry
from autobench.adapters.langgraph_adapter import LangGraphAdapter
from autobench.backends import tool_registry
from autobench.environment import FaultInjectingEnvironment
from autobench.evaluator import evaluate_trajectory
from autobench.schema import TaskSpec, load_task

log = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "experiments" / "thesis_pilot" / "config.json"

_BACKOFF_SECONDS = (5.0, 15.0, 45.0)
_MAX_RETRIES = 3
_BETWEEN_TRIAL_SLEEP_S = 2.0

# Per-trajectory hard kill switches (a stuck model can otherwise loop to
# max_iterations, burning minutes and tens of thousands of tokens).
MAX_TRAJECTORY_SECONDS = 90
MAX_TRAJECTORY_TOKENS = 15_000
# Grace over MAX_TRAJECTORY_SECONDS before abandoning a worker that never hit a
# tool boundary (e.g. hung on a single long LLM call).
_JOIN_GRACE_S = 20.0


# --------------------------------------------------------------------- helpers


def _load_env() -> None:
    for candidate in (REPO_ROOT / ".env", REPO_ROOT / "autobench" / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            return
    load_dotenv()


def _tool_specs_from_task(task: TaskSpec) -> list[dict[str, Any]]:
    """Full JSON Schema for every tool the task exposes, from the tool registry.

    Raises ``KeyError`` (from :func:`tool_registry.get_tool_schema`) if a task
    references a tool with no registry entry.
    """
    return [
        tool_registry.get_tool_schema(task.category, tool_name)
        for tool_name in task.context.available_tools
    ]


def _trace_path(traces_dir: Path, config_id: str, task_id: str, trial_index: int) -> Path:
    return traces_dir / f"{config_id}__{task_id}__trial{trial_index}.json"


def _is_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    if getattr(exc, "status_code", None) == 429:
        return True
    response = getattr(exc, "response", None)
    return bool(getattr(response, "status_code", None) == 429)


def _is_daily_quota(exc: BaseException) -> bool:
    """True for a Groq *tokens-per-day* 429 (not a transient per-minute one).

    A per-minute 429 clears in seconds; a TPD 429 needs the 00:00 UTC reset, so
    the runner should halt rather than grind every remaining trajectory into a
    back-off ERROR.
    """
    if not _is_rate_limit(exc):
        return False
    text = str(exc).lower()
    return "per day" in text or "(tpd)" in text or "tokens per day" in text


class _DailyQuotaExhausted(BaseException):
    """Signals main() to stop the run cleanly and exit for a later resume."""


def _retry_delay(exc: BaseException, attempt: int) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except (TypeError, ValueError):
                pass
    return _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]


# --------------------------------------------------------------- kill switches


class _TrajectoryKilled(BaseException):
    """Raised at a tool boundary when the watchdog trips.

    Subclasses ``BaseException`` (not ``Exception``) so LangGraph's ToolNode
    error handling and the adapter's ``except Exception`` both let it propagate
    out to the worker thread instead of turning it into an error ToolMessage.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _Watchdog:
    """Trips on a wall-clock timer or when telemetry token usage exceeds the cap."""

    def __init__(self) -> None:
        self._reason: str | None = None
        self._lock = threading.Lock()
        self._timer = threading.Timer(MAX_TRAJECTORY_SECONDS, self._on_timeout)
        self._timer.daemon = True

    def _on_timeout(self) -> None:
        with self._lock:
            if self._reason is None:
                self._reason = "timeout"

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.cancel()

    def check(self, telemetry: TrajectoryTelemetry) -> None:
        """Called before every tool dispatch; raises if the trajectory is over budget."""
        with self._lock:
            if self._reason is None and telemetry.total_tokens > MAX_TRAJECTORY_TOKENS:
                self._reason = "token_cap"
            if self._reason is not None:
                raise _TrajectoryKilled(self._reason)


def _error_record(
    cfg: Any,
    task: TaskSpec,
    trial_index: int,
    error: str,
    *,
    reason: str | None = None,
    telemetry: TrajectoryTelemetry | None = None,
    tb: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "config_id": cfg["config_id"],
        "model_name": cfg["model_name"],
        "task_id": task.task_id,
        "trial_index": trial_index,
        "status": "ERROR",
        "error": error,
    }
    if reason is not None:
        record["reason"] = reason
    if tb is not None:
        record["traceback"] = tb
    if telemetry is not None:
        record["telemetry"] = telemetry.to_json_dict()  # partial
    return record


# ------------------------------------------------------------ one trajectory


def _attempt_trajectory(
    cfg: Any,
    task: TaskSpec,
    trial_index: int,
    master_seed: int,
    telemetry: TrajectoryTelemetry,
    watchdog: _Watchdog,
) -> dict[str, Any]:
    seed = f"{task.task_id}-{trial_index}-{master_seed}"
    rng = random.Random(seed)
    # LangGraph runs tool nodes on worker threads -> share the connection.
    db_conn = sqlite3.connect(":memory:", check_same_thread=False)
    env = FaultInjectingEnvironment(
        task_spec=task, db_conn=db_conn, telemetry=telemetry, rng=rng
    )

    adapter = LangGraphAdapter(
        model_name=cfg["model_name"],
        api_key=os.environ[cfg["api_key_env"]],
        base_url=cfg["base_url"],
        temperature=float(cfg.get("temperature", 0.0)),
    )
    tools = _tool_specs_from_task(task)
    task_prompt = f"{task.context.system_prompt}\n\n{task.user_message}"

    def _tool_executor(name: str, args: dict[str, Any]) -> Any:
        watchdog.check(telemetry)
        return env.execute_tool(name, args)

    try:
        final_response = adapter.run(
            task_prompt=task_prompt,
            tools=tools,
            tool_executor=_tool_executor,
            telemetry=telemetry,
        )
        metrics = evaluate_trajectory(task, db_conn, telemetry)
    finally:
        db_conn.close()

    status = "PASS" if (metrics["tsi"] == 1.0 and metrics["sec"] == 1.0) else "FAIL"
    return {
        "config_id": cfg["config_id"],
        "model_name": cfg["model_name"],
        "task_id": task.task_id,
        "trial_index": trial_index,
        "seed": seed,
        "status": status,
        "final_response": final_response,
        "metrics": metrics,
        "telemetry": telemetry.to_json_dict(),
    }


def _fill_box(
    box: dict[str, Any],
    cfg: Any,
    task: TaskSpec,
    trial_index: int,
    master_seed: int,
    telemetry: TrajectoryTelemetry,
    watchdog: _Watchdog,
) -> None:
    """Worker-thread body: run one attempt, stash exactly one of record/killed/exc."""
    try:
        box["record"] = _attempt_trajectory(
            cfg, task, trial_index, master_seed, telemetry, watchdog
        )
    except _TrajectoryKilled as exc:
        box["killed"] = exc.reason
    except Exception as exc:  # noqa: BLE001 - every failure is recorded as a trace
        box["exc"] = exc


def _run_trajectory_with_retries(
    cfg: Any, task: TaskSpec, trial_index: int, master_seed: int
) -> dict[str, Any]:
    for attempt in range(_MAX_RETRIES + 1):
        telemetry = TrajectoryTelemetry(task_id=task.task_id, trial_index=trial_index)
        watchdog = _Watchdog()
        box: dict[str, Any] = {}

        worker = threading.Thread(
            target=_fill_box,
            args=(box, cfg, task, trial_index, master_seed, telemetry, watchdog),
            name=f"traj-{task.task_id}-{trial_index}",
            daemon=True,
        )
        watchdog.start()
        worker.start()
        worker.join(timeout=MAX_TRAJECTORY_SECONDS + _JOIN_GRACE_S)
        watchdog.stop()

        common = {
            "config_id": cfg["config_id"],
            "task_id": task.task_id,
            "trial_index": trial_index,
        }

        if worker.is_alive():
            log.error("trajectory_killed", reason="timeout", hard=True,
                      tokens=telemetry.total_tokens, tool_calls=len(telemetry.tool_calls),
                      **common)
            return _error_record(
                cfg, task, trial_index,
                f"timeout: worker still running after {MAX_TRAJECTORY_SECONDS + _JOIN_GRACE_S:.0f}s",
                reason="timeout", telemetry=telemetry,
            )

        if "killed" in box:
            reason = box["killed"]
            log.warning("trajectory_killed", reason=reason, tokens=telemetry.total_tokens,
                        tool_calls=len(telemetry.tool_calls), **common)
            return _error_record(
                cfg, task, trial_index, f"killed: {reason}",
                reason=reason, telemetry=telemetry,
            )

        if "exc" in box:
            exc = box["exc"]
            if _is_daily_quota(exc):
                log.error("daily_quota_exhausted", **common)
                raise _DailyQuotaExhausted(str(exc))
            if _is_rate_limit(exc) and attempt < _MAX_RETRIES:
                delay = _retry_delay(exc, attempt)
                log.warning("rate_limited", attempt=attempt + 1, delay_s=delay, **common)
                time.sleep(delay)
                continue
            error = f"{type(exc).__name__}: {exc}"
            log.error("trajectory_error", error=error, **common)
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            return _error_record(cfg, task, trial_index, error, telemetry=telemetry, tb=tb)

        record: dict[str, Any] = box.get("record") or _error_record(
            cfg, task, trial_index, "worker produced no result", telemetry=telemetry
        )
        if telemetry.total_tokens > MAX_TRAJECTORY_TOKENS and record["status"] != "ERROR":
            log.warning("trajectory_token_cap", tokens=telemetry.total_tokens, **common)
            return _error_record(
                cfg, task, trial_index,
                f"token_cap: {telemetry.total_tokens} > {MAX_TRAJECTORY_TOKENS}",
                reason="token_cap", telemetry=telemetry,
            )
        return record
    raise RuntimeError("unreachable")  # pragma: no cover


# --------------------------------------------------------------------- driver


def _print_progress(n: int, total: int, record: dict[str, Any]) -> None:
    prefix = (
        f"[{n}/{total}] {record['config_id']} {record['task_id']} "
        f"trial{record['trial_index']}:"
    )
    if record["status"] == "ERROR":
        print(f"{prefix} ERROR {record.get('error', '')}")
        return
    m = record["metrics"]
    print(
        f"{prefix} {record['status']} "
        f"tsi={int(m['tsi'])} sec={int(m['sec'])} "
        f"cost=${m['total_cost_usd']:.4f} latency={m['duration_ms']:.0f}ms"
    )


def _print_summary(total: int, counts: dict[str, int]) -> None:
    print("\n=== SUMMARY ===")
    print(f"total trajectories : {total}")
    for key in ("PASS", "FAIL", "ERROR", "SKIP"):
        print(f"  {key:<5} : {counts.get(key, 0)}")


def run_pilot(
    config: dict[str, Any],
    traces_dir: Path,
    tasks_root: Path,
    *,
    between_trial_sleep_s: float = _BETWEEN_TRIAL_SLEEP_S,
    limit: int | None = None,
) -> dict[str, int]:
    traces_dir.mkdir(parents=True, exist_ok=True)
    master_seed = int(config["master_seed"])
    trials = int(config["trials_per_task"])
    configs = config["configurations"]

    task_paths: list[Path] = []
    for category in config["task_categories"]:
        task_paths.extend(sorted((tasks_root / category).glob("task_*.json")))

    total = len(configs) * len(task_paths) * trials
    counts: dict[str, int] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
    n = 0
    executed = 0

    try:
        for cfg in configs:
            for task_path in task_paths:
                task = load_task(str(task_path))
                for trial_index in range(trials):
                    n += 1
                    trace_path = _trace_path(
                        traces_dir, cfg["config_id"], task.task_id, trial_index
                    )
                    if trace_path.exists():
                        counts["SKIP"] += 1
                        print(
                            f"[{n}/{total}] {cfg['config_id']} {task.task_id} "
                            f"trial{trial_index}: SKIP (trace exists)"
                        )
                        continue

                    if limit is not None and executed >= limit:
                        print(f"\nReached --limit {limit}; stopping. Re-run to continue.")
                        _print_summary(total, counts)
                        return counts

                    record = _run_trajectory_with_retries(
                        cfg, task, trial_index, master_seed
                    )
                    trace_path.write_text(
                        json.dumps(record, indent=2, default=str), encoding="utf-8"
                    )
                    _print_progress(n, total, record)
                    counts[record["status"]] = counts.get(record["status"], 0) + 1
                    executed += 1

                    if limit is not None and executed >= limit:
                        print(f"\nReached --limit {limit}; stopping. Re-run to continue.")
                        _print_summary(total, counts)
                        return counts

                    if between_trial_sleep_s > 0:
                        time.sleep(between_trial_sleep_s)
    except KeyboardInterrupt:
        print(f"\nStopped at trajectory {n}/{total}. Re-run to resume from checkpoint.")
        _print_summary(total, counts)
        return counts
    except _DailyQuotaExhausted:
        print(
            f"\nDAILY TOKEN QUOTA EXHAUSTED at trajectory {n}/{total}. "
            "Stopping cleanly; resume after the next 00:00 UTC reset."
        )
        counts["QUOTA_STOP"] = 1
        _print_summary(total, counts)
        return counts

    _print_summary(total, counts)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AutoBench thesis pilot.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="stop after this many freshly executed trajectories (skips don't count)",
    )
    args = parser.parse_args()

    _load_env()
    config: dict[str, Any] = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    traces_dir = REPO_ROOT / config["output_dir"]
    tasks_root = REPO_ROOT / config["task_pool"]
    counts = run_pilot(config, traces_dir, tasks_root, limit=args.limit)
    # Exit 2 signals wait_and_resume that a daily-quota reset is needed.
    return 2 if counts.get("QUOTA_STOP") else 0


if __name__ == "__main__":
    sys.exit(main())

