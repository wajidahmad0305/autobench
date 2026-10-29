from __future__ import annotations

from typing import Any

import pytest

from autobench.adapters.base import TrajectoryTelemetry
from autobench.adapters.crewai_adapter import CrewAIAdapter

DUMMY_KW = {
    "model_name": "openai/gpt-oss-20b",
    "api_key": "dummy-key",
    "base_url": "https://example.invalid/v1",
}

TWO_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_order",
        "description": "Fetch an order by id",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "cancel_order",
        "description": "Cancel an order",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["order_id"],
        },
    },
]


def _tool_executor(name: str, args: dict[str, Any]) -> Any:
    return {"ok": True, "tool": name, "args": args}


@pytest.fixture(autouse=True)
def _no_crewai_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """CrewAI phones home anonymous usage stats by default; kill that in tests."""
    monkeypatch.setenv("CREWAI_TELEMETRY_OPT_OUT", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-not-used")


def test_crewai_adapter_instantiates() -> None:
    adapter = CrewAIAdapter(**DUMMY_KW)

    assert adapter.model_name == "openai/gpt-oss-20b"
    assert adapter.temperature == 0.0
    assert adapter.max_iterations == 12
    assert adapter.agent_role == "BPA Automation Specialist"
    assert "openai/gpt-oss-20b" in repr(adapter)
    assert repr(adapter) == "CrewAIAdapter(model_name='openai/gpt-oss-20b')"


def test_crewai_tool_conversion() -> None:
    adapter = CrewAIAdapter(**DUMMY_KW)
    telemetry = TrajectoryTelemetry(task_id="t", trial_index=0)

    crew_tools = adapter._build_crewai_tools(TWO_TOOLS, _tool_executor, telemetry)

    assert [t.name for t in crew_tools] == ["get_order", "cancel_order"]
    # the closure routes through the harness-provided executor
    assert crew_tools[0]._run(order_id="A1") == {
        "ok": True,
        "tool": "get_order",
        "args": {"order_id": "A1"},
    }
    assert len(telemetry.tool_calls) == 1
    assert telemetry.tool_calls[0].tool_name == "get_order"


def test_run_with_mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hand the adapter a crewai-native LLM bound to a *native* provider (no
    # litellm needed). It is constructed but never invoked, because Crew.kickoff
    # is stubbed below - so no network call happens.
    from crewai import LLM

    answer = "FINAL ANSWER: order A1 cancelled and customer notified"

    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI",
        lambda *args, **kwargs: LLM(model="gpt-4o-mini"),
    )

    class _FakeUsage:
        prompt_tokens = 120
        completion_tokens = 34
        total_tokens = 154

    class _FakeCrewOutput:
        raw = answer
        token_usage = _FakeUsage()

    monkeypatch.setattr(
        "crewai.Crew.kickoff",
        lambda self, *args, **kwargs: _FakeCrewOutput(),
    )

    adapter = CrewAIAdapter(**DUMMY_KW)
    telemetry = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)

    result = adapter.run(
        task_prompt="Cancel order A1.",
        tools=TWO_TOOLS,
        tool_executor=_tool_executor,
        telemetry=telemetry,
    )

    assert result == answer
    assert telemetry.wall_clock_time_ms > 0
    assert telemetry.prompt_tokens == 120
    assert telemetry.completion_tokens == 34
    assert telemetry.total_tokens == 154
    assert telemetry.tool_calls == []  # final answer came back without tool use

