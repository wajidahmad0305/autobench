from __future__ import annotations

import pytest

from autobench.adapters.base import BaseAgentAdapter, ToolCallRecord, TrajectoryTelemetry


def test_trajectory_telemetry_minimal_construction() -> None:
    telemetry = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)

    assert telemetry.task_id == "crm_order_fulfilment.001"
    assert telemetry.trial_index == 0
    assert telemetry.tool_calls == []
    assert telemetry.success is False


def test_add_tool_call_appends_and_to_json_dict_serializes() -> None:
    telemetry = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)
    record = ToolCallRecord(
        tool_name="get_order",
        arguments={"order_id": "A123"},
        output={"status": "pending"},
        latency_ms=42.5,
        is_error=False,
    )

    telemetry.add_tool_call(record)

    assert len(telemetry.tool_calls) == 1
    assert telemetry.tool_calls[0] is record

    as_dict = telemetry.to_json_dict()
    assert isinstance(as_dict, dict)
    assert as_dict["task_id"] == "crm_order_fulfilment.001"
    assert as_dict["tool_calls"][0]["tool_name"] == "get_order"
    assert as_dict["tool_calls"][0]["arguments"] == {"order_id": "A123"}


def test_subclassing_without_run_raises_type_error() -> None:
    class IncompleteAdapter(BaseAgentAdapter):
        pass

    with pytest.raises(TypeError):
        IncompleteAdapter(model_name="gemini-2.5-flash")  # type: ignore[abstract]

