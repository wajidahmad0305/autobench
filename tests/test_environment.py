from __future__ import annotations

import concurrent.futures
import random
import sqlite3
from datetime import date

import pytest

from autobench.adapters.base import TrajectoryTelemetry
from autobench.environment import FaultInjectingEnvironment
from autobench.schema import (
    EnvironmentSpec,
    FaultInjectionRule,
    GroundTruth,
    Provenance,
    Reliability,
    TaskSpec,
)

# A real tool in the crm_order_fulfilment backend. The fault-injection tests
# only care that the non-fault path reaches *a* backend and returns a dict;
# with an empty seeded state this lookup deterministically finds nothing.
TOOL = "get_hubspot_contact_by_email"
ARGS = {"email": "a@b.com"}
NO_FAULT_RESULT = {"email": "a@b.com", "found": False, "contact": None}


def _make_task(fault_rules: list[FaultInjectionRule] | None = None) -> TaskSpec:
    return TaskSpec(
        task_id="crm_order_fulfilment.001",
        category="crm_order_fulfilment",
        difficulty="easy",
        description="test task",
        user_message="do the thing",
        context=EnvironmentSpec(
            system_prompt="you are a test agent",
            available_tools=[TOOL],
            initial_state={},
        ),
        ground_truth=GroundTruth(expected_final_state={}),
        reliability=Reliability(
            k_trials=3,
            cost_budget_usd=0.05,
            latency_budget_ms=30_000,
            fault_injection_rules=fault_rules or [],
        ),
        provenance=Provenance(
            author="test",
            created=date(2026, 8, 28),
            domain_source="synthetic",
        ),
    )


@pytest.fixture
def telemetry() -> TrajectoryTelemetry:
    return TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)


@pytest.fixture
def db_conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:")


def _make_env(
    telemetry: TrajectoryTelemetry,
    db_conn: sqlite3.Connection,
    fault_rules: list[FaultInjectionRule] | None = None,
    seed: int = 0,
) -> FaultInjectingEnvironment:
    return FaultInjectingEnvironment(
        task_spec=_make_task(fault_rules),
        db_conn=db_conn,
        telemetry=telemetry,
        rng=random.Random(seed),
    )


def test_no_fault_dispatches_to_backend(
    telemetry: TrajectoryTelemetry, db_conn: sqlite3.Connection
) -> None:
    env = _make_env(telemetry, db_conn, fault_rules=[])

    result = env.execute_tool(TOOL, ARGS)

    assert result == NO_FAULT_RESULT
    assert len(telemetry.tool_calls) == 1
    assert telemetry.tool_calls[0].is_error is False
    assert telemetry.tool_calls[0].fault_injected is None


def test_http_429_fault_triggers_deterministically(
    telemetry: TrajectoryTelemetry, db_conn: sqlite3.Connection
) -> None:
    rule = FaultInjectionRule(
        tool_target=TOOL,
        fault_type="HTTP_429",
        trigger_probability=1.0,
        retry_after_ms=500,
    )
    env = _make_env(telemetry, db_conn, fault_rules=[rule])

    result = env.execute_tool(TOOL, ARGS)

    assert result == {"error": "HTTP 429: Rate limit exceeded", "retry_after_ms": 500}
    assert telemetry.tool_calls[-1].fault_injected == "HTTP_429"
    assert telemetry.tool_calls[-1].is_error is True


def test_http_500_and_409(
    telemetry: TrajectoryTelemetry, db_conn: sqlite3.Connection
) -> None:
    rule_500 = FaultInjectionRule(
        tool_target=TOOL, fault_type="HTTP_500", trigger_probability=1.0
    )
    env_500 = _make_env(telemetry, db_conn, fault_rules=[rule_500])
    assert env_500.execute_tool(TOOL, ARGS) == {"error": "HTTP 500: Internal Server Error"}
    assert telemetry.tool_calls[-1].fault_injected == "HTTP_500"
    assert telemetry.tool_calls[-1].is_error is True

    telemetry_409 = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)
    rule_409 = FaultInjectionRule(
        tool_target=TOOL, fault_type="HTTP_409", trigger_probability=1.0
    )
    env_409 = _make_env(telemetry_409, db_conn, fault_rules=[rule_409])
    assert env_409.execute_tool(TOOL, ARGS) == {
        "error": "HTTP 409: Conflict — resource locked"
    }
    assert telemetry_409.tool_calls[-1].fault_injected == "HTTP_409"
    assert telemetry_409.tool_calls[-1].is_error is True


def test_schema_drift_renames_a_field(
    telemetry: TrajectoryTelemetry, db_conn: sqlite3.Connection
) -> None:
    rule = FaultInjectionRule(
        tool_target=TOOL, fault_type="SCHEMA_DRIFT", trigger_probability=1.0
    )
    env = _make_env(telemetry, db_conn, fault_rules=[rule])

    normal = env._dispatch_to_db(TOOL, ARGS)
    drifted = env.execute_tool(TOOL, ARGS)

    assert isinstance(normal, dict) and isinstance(drifted, dict)
    # at least one original key was renamed away
    renamed_keys = [k for k in normal if k not in drifted]
    assert renamed_keys, f"no field renamed: normal={normal} drifted={drifted}"
    # and its value survived under some new key
    assert normal[renamed_keys[0]] in drifted.values()
    assert telemetry.tool_calls[-1].fault_injected == "SCHEMA_DRIFT"


def test_timeout_raises_TimeoutError(
    telemetry: TrajectoryTelemetry, db_conn: sqlite3.Connection
) -> None:
    rule = FaultInjectionRule(
        tool_target=TOOL, fault_type="TIMEOUT", trigger_probability=1.0
    )
    env = _make_env(telemetry, db_conn, fault_rules=[rule])

    with pytest.raises(concurrent.futures.TimeoutError):
        env.execute_tool(TOOL, ARGS)

    # the fault is still recorded before the raise
    assert telemetry.tool_calls[-1].fault_injected == "TIMEOUT"
    assert telemetry.tool_calls[-1].is_error is True


def test_determinism_across_runs(db_conn: sqlite3.Connection) -> None:
    rule = FaultInjectionRule(
        tool_target=TOOL, fault_type="HTTP_500", trigger_probability=0.5
    )

    def run() -> list[str | None]:
        telem = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)
        env = _make_env(telem, db_conn, fault_rules=[rule], seed=20260827)
        for _ in range(25):
            env.execute_tool(TOOL, ARGS)
        return [tc.fault_injected for tc in telem.tool_calls]

    seq_a = run()
    seq_b = run()

    assert seq_a == seq_b
    # sanity: p=0.5 actually produced a mix, so the equality is meaningful
    assert any(x is not None for x in seq_a)
    assert any(x is None for x in seq_a)


def test_qwen_list_wrap_normalization(
    telemetry: TrajectoryTelemetry, db_conn: sqlite3.Connection
) -> None:
    env = _make_env(telemetry, db_conn, fault_rules=[])

    assert env._normalize_arguments({"email": ["a@b.com"]}) == {"email": "a@b.com"}
    # multi-element lists and scalars are left untouched
    assert env._normalize_arguments({"tags": ["x", "y"], "n": 2}) == {
        "tags": ["x", "y"],
        "n": 2,
    }
