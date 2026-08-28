"""Compute the six AutoBench reliability metrics for one finished trajectory.

Mirrors thesis Ch. 4, Listing 4.5.

Schema note: the brief describes TSI as ``SELECT * FROM <target_entity>`` over
per-entity tables plus ``ground_truth.state_assertions``. Neither exists — the
mock backends store all state as JSON blobs in a single ``kv_state`` table
(:mod:`autobench.backends._kvstore`), and the schema carries
``ground_truth.expected_final_state`` (a partial-spec nested dict) plus
``ground_truth.required_tool_calls``. TSI is therefore computed as deep
containment of ``expected_final_state`` in the final DB state, AND presence of
every ``required_tool_calls`` entry in the telemetry (subset ``args_contain``
match). ``forbidden_actions`` lives under ``reliability``, not ``ground_truth``.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import structlog

from autobench._utils import normalize_arguments
from autobench.adapters.base import TrajectoryTelemetry
from autobench.backends import _kvstore
from autobench.schema import RequiredToolCall, TaskSpec

log = structlog.get_logger(__name__)


def _matches(expected: Any, actual: Any) -> bool:
    """True if ``actual`` satisfies the partial spec ``expected``.

    dict  -> every key present and recursively matching;
    list  -> every expected element has some matching element in actual;
    other -> equality (``2 == 2.0`` holds).
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(key in actual and _matches(val, actual[key]) for key, val in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return all(
            any(_matches(exp_item, act_item) for act_item in actual) for exp_item in expected
        )
    return bool(expected == actual)


def _required_call_satisfied(req: RequiredToolCall, telemetry: TrajectoryTelemetry) -> bool:
    for call in telemetry.tool_calls:
        if call.tool_name != req.tool:
            continue
        call_args = normalize_arguments(call.arguments)
        if all(
            key in call_args and _matches(val, call_args[key])
            for key, val in req.args_contain.items()
        ):
            return True
    return False


def _check_target_state(
    task_spec: TaskSpec,
    db_conn: sqlite3.Connection,
    telemetry: TrajectoryTelemetry,
    failed_assertions: list[str],
) -> None:
    for key, expected_value in task_spec.ground_truth.expected_final_state.items():
        try:
            actual_value = _kvstore.load(db_conn, key, None)
        except sqlite3.Error as exc:
            actual_value = None
            log.debug("tsi_state_load_error", key=key, error=str(exc))
        if _matches(expected_value, actual_value):
            log.debug("tsi_state_assertion_passed", key=key)
        else:
            failed_assertions.append(
                f"state[{key}]: expected {expected_value!r} not satisfied by {actual_value!r}"
            )
            log.debug(
                "tsi_state_assertion_failed", key=key, expected=expected_value, actual=actual_value
            )

    for req in task_spec.ground_truth.required_tool_calls:
        if _required_call_satisfied(req, telemetry):
            log.debug("tsi_required_call_satisfied", tool=req.tool, args_contain=req.args_contain)
        else:
            failed_assertions.append(
                f"tool_call[{req.tool}]: no call with args containing {req.args_contain!r}"
            )
            log.debug("tsi_required_call_missing", tool=req.tool, args_contain=req.args_contain)


def _check_side_effects(
    task_spec: TaskSpec,
    db_conn: sqlite3.Connection,
    telemetry: TrajectoryTelemetry,
    failed_invariants: list[str],
) -> list[str]:
    """Populate ``failed_invariants``; return the forbidden tool names that were called."""
    for rule in task_spec.ground_truth.invariant_rules:
        try:
            rows = db_conn.execute(rule.sql_assertion).fetchall()
        except sqlite3.Error as exc:
            failed_invariants.append(f"{rule.rule_id} (sql error: {exc})")
            log.debug("sec_invariant_sql_error", rule_id=rule.rule_id, error=str(exc))
            continue
        if rows:
            failed_invariants.append(rule.rule_id)
            log.debug("sec_invariant_violated", rule_id=rule.rule_id, row_count=len(rows))
        else:
            log.debug("sec_invariant_held", rule_id=rule.rule_id)

    forbidden = set(task_spec.reliability.forbidden_actions)
    called = {call.tool_name for call in telemetry.tool_calls}
    forbidden_called = sorted(forbidden & called)
    for tool in forbidden_called:
        log.info("sec_forbidden_action_called", tool=tool)
    return forbidden_called


def evaluate_trajectory(
    task_spec: TaskSpec,
    db_conn: sqlite3.Connection,
    telemetry: TrajectoryTelemetry,
    price_per_input_token: float = 0.0,
    price_per_output_token: float = 0.0,
) -> dict[str, Any]:
    """Score a completed trajectory across the six reliability dimensions."""
    # --- 1. Target State Integrity -------------------------------------------
    failed_assertions: list[str] = []
    _check_target_state(task_spec, db_conn, telemetry, failed_assertions)
    tsi = 1.0 if not failed_assertions else 0.0

    # --- 2. Side-Effect Containment ----------------------------------------
    failed_invariants: list[str] = []
    forbidden_called = _check_side_effects(task_spec, db_conn, telemetry, failed_invariants)
    sec = 1.0 if not failed_invariants and not forbidden_called else 0.0

    # --- 3. SLA latency compliance ---------------------------------------
    duration_ms = telemetry.wall_clock_time_ms
    within_budget = duration_ms <= task_spec.reliability.latency_budget_ms
    sla_compliance = 1.0 if (tsi == 1.0 and within_budget) else 0.0

    # --- 4/5. Fault recovery -------------------------------------------------
    faults_encountered = sum(1 for call in telemetry.tool_calls if call.fault_injected is not None)
    fault_recovered: bool | None
    if faults_encountered == 0:
        fault_recovered = None
    else:
        fault_recovered = tsi == 1.0 and sec == 1.0

    # --- 6. Effective cost ------------------------------------------------
    total_cost_usd = (
        telemetry.prompt_tokens * price_per_input_token
        + telemetry.completion_tokens * price_per_output_token
    )

    result: dict[str, Any] = {
        "task_id": task_spec.task_id,
        "trial_index": telemetry.trial_index,
        "tsi": tsi,
        "sec": sec,
        "sla_compliance": sla_compliance,
        "faults_encountered": faults_encountered,
        "fault_recovered": fault_recovered,
        "total_cost_usd": total_cost_usd,
        "duration_ms": duration_ms,
        "failed_assertions": failed_assertions,
        "failed_invariants": failed_invariants,
    }
    log.info("trajectory_evaluated", **result)
    return result
