from __future__ import annotations

import random
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from autobench.adapters.base import ToolCallRecord, TrajectoryTelemetry
from autobench.adapters.langgraph_adapter import LangGraphAdapter
from autobench.backends import crm_order_fulfilment
from autobench.environment import FaultInjectingEnvironment
from autobench.evaluator import evaluate_trajectory
from autobench.schema import (
    EnvironmentSpec,
    GroundTruth,
    InvariantRule,
    Provenance,
    Reliability,
    RequiredToolCall,
    TaskSpec,
    load_task,
)

_TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"


def _crm_001() -> TaskSpec:
    return load_task(str(_TASKS_DIR / "crm_order_fulfilment" / "task_001.json"))


def _spec(
    *,
    expected_final_state: dict[str, Any] | None = None,
    required_tool_calls: list[RequiredToolCall] | None = None,
    invariant_rules: list[InvariantRule] | None = None,
    forbidden_actions: list[str] | None = None,
    latency_budget_ms: int = 30_000,
) -> TaskSpec:
    return TaskSpec(
        task_id="crm_order_fulfilment.001",
        category="crm_order_fulfilment",
        difficulty="easy",
        description="synthetic",
        user_message="do it",
        context=EnvironmentSpec(system_prompt="x", available_tools=["a"], initial_state={}),
        ground_truth=GroundTruth(
            expected_final_state=expected_final_state or {},
            required_tool_calls=required_tool_calls or [],
            invariant_rules=invariant_rules or [],
        ),
        reliability=Reliability(
            k_trials=3,
            cost_budget_usd=0.05,
            latency_budget_ms=latency_budget_ms,
            forbidden_actions=forbidden_actions or [],
        ),
        provenance=Provenance(author="t", created=date(2026, 8, 28), domain_source="synthetic"),
    )


def _tc(
    tool: str,
    args: dict[str, Any],
    *,
    fault: str | None = None,
    is_error: bool = False,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool,
        arguments=args,
        output={"ok": True},
        latency_ms=1.0,
        is_error=is_error,
        fault_injected=fault,
    )


# --- offline scripted LLM (same technique as test_run_with_mock_llm) ----------

_CRM_SCRIPT: list[tuple[str, dict[str, Any]]] = [
    ("get_hubspot_contact_by_email", {"email": "jordan.lee@example.com"}),
    ("create_hubspot_contact", {"email": "jordan.lee@example.com"}),
    ("tag_hubspot_contact", {"email": "jordan.lee@example.com", "tag": "WGT-100-BLU"}),
    (
        "add_to_fulfillment_queue",
        {
            "order_id": "SHOP-10432",
            "email": "jordan.lee@example.com",
            "sku": "WGT-100-BLU",
            "qty": 2,
        },
    ),
]


class _ScriptedFakeLLM(GenericFakeChatModel):
    """Yields a fixed queue of AIMessages verbatim; never calls a real endpoint."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> _ScriptedFakeLLM:
        return self


def _scripted_llm(script: list[tuple[str, dict[str, Any]]]) -> _ScriptedFakeLLM:
    msgs: list[Any] = [
        AIMessage(content="", tool_calls=[{"name": tool, "args": args, "id": f"call_{i}"}])
        for i, (tool, args) in enumerate(script)
    ]
    # trailing no-tool-call messages end the graph (extras are harmless padding)
    msgs += [AIMessage(content="All steps completed.") for _ in range(3)]
    return _ScriptedFakeLLM(messages=iter(msgs))


def _tool_specs(
    spec: TaskSpec, script: list[tuple[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    keys_by_tool: dict[str, set[str]] = {}
    for call in spec.ground_truth.required_tool_calls:
        keys_by_tool.setdefault(call.tool, set()).update(call.args_contain)
    for tool, args in script:
        keys_by_tool.setdefault(tool, set()).update(args)
    specs: list[dict[str, Any]] = []
    for name in spec.context.available_tools:
        props = {key: {"type": "string"} for key in sorted(keys_by_tool.get(name, set()))}
        specs.append(
            {
                "name": name,
                "description": f"{name} (mock)",
                "parameters": {"type": "object", "properties": props},
            }
        )
    return specs


# --- tests ------------------------------------------------------------------


def test_all_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _crm_001()
    # LangGraph runs tool nodes on worker threads, so the shared connection
    # must permit cross-thread use (the runner will do the same in Session 7).
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)
    env = FaultInjectingEnvironment(
        task_spec=spec, db_conn=conn, telemetry=telemetry, rng=random.Random(0)
    )

    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI", lambda *a, **k: _scripted_llm(_CRM_SCRIPT)
    )
    adapter = LangGraphAdapter(
        model_name="fake", api_key="x", base_url="http://x", temperature=0.0
    )
    adapter.run(
        task_prompt=spec.user_message,
        tools=_tool_specs(spec, _CRM_SCRIPT),
        tool_executor=env.execute_tool,
        telemetry=telemetry,
    )

    result = evaluate_trajectory(spec, conn, telemetry)

    assert result["tsi"] == 1.0
    assert result["sec"] == 1.0
    assert result["sla_compliance"] == 1.0
    assert result["fault_recovered"] is None
    assert result["total_cost_usd"] == 0.0
    assert result["failed_assertions"] == []


def test_tsi_fails_when_state_wrong() -> None:
    spec = _crm_001()
    conn = sqlite3.connect(":memory:")
    crm_order_fulfilment.initialize(conn, spec)  # seeds empty containers, nothing written
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)

    result = evaluate_trajectory(spec, conn, telemetry)

    assert result["tsi"] == 0.0
    assert result["failed_assertions"]


def test_sec_fails_on_invariant_violation() -> None:
    spec = _spec(
        invariant_rules=[InvariantRule(rule_id="R1", sql_assertion="SELECT 1 WHERE 1=1")]
    )
    conn = sqlite3.connect(":memory:")
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)

    result = evaluate_trajectory(spec, conn, telemetry)

    assert result["sec"] == 0.0
    assert "R1" in result["failed_invariants"]


def test_sec_fails_on_forbidden_action() -> None:
    spec = _spec(forbidden_actions=["charge_customer_card"])
    conn = sqlite3.connect(":memory:")
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)
    telemetry.add_tool_call(_tc("charge_customer_card", {"amount": 100}))

    result = evaluate_trajectory(spec, conn, telemetry)

    assert result["sec"] == 0.0


def test_sla_fails_when_over_budget() -> None:
    spec = _spec(latency_budget_ms=100)  # empty expected_final_state -> tsi == 1.0
    conn = sqlite3.connect(":memory:")
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)
    telemetry.wall_clock_time_ms = 5_000.0

    result = evaluate_trajectory(spec, conn, telemetry)

    assert result["tsi"] == 1.0
    assert result["sla_compliance"] == 0.0


def test_fault_recovery_when_faulted_and_succeeded() -> None:
    spec = _spec()
    conn = sqlite3.connect(":memory:")
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)
    telemetry.add_tool_call(_tc("get_thing", {}, fault="HTTP_429", is_error=True))
    telemetry.add_tool_call(_tc("get_thing", {}))

    result = evaluate_trajectory(spec, conn, telemetry)

    assert result["faults_encountered"] > 0
    assert result["fault_recovered"] is True


def test_fault_recovery_none_when_no_faults() -> None:
    spec = _spec()
    conn = sqlite3.connect(":memory:")
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)
    telemetry.add_tool_call(_tc("get_thing", {}))

    result = evaluate_trajectory(spec, conn, telemetry)

    assert result["faults_encountered"] == 0
    assert result["fault_recovered"] is None


def test_cost_computation() -> None:
    spec = _spec()
    conn = sqlite3.connect(":memory:")
    telemetry = TrajectoryTelemetry(task_id=spec.task_id, trial_index=0)
    telemetry.prompt_tokens = 1000
    telemetry.completion_tokens = 500

    result = evaluate_trajectory(
        spec,
        conn,
        telemetry,
        price_per_input_token=1e-6,
        price_per_output_token=2e-6,
    )

    assert result["total_cost_usd"] == pytest.approx(0.002)
