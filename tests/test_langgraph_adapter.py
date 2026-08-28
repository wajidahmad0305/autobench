from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from autobench.adapters.base import TrajectoryTelemetry
from autobench.adapters.langgraph_adapter import LangGraphAdapter

DUMMY_KW = {
    "model_name": "gemini-2.5-flash",
    "api_key": "dummy-key",
    "base_url": "https://example.invalid/v1",
}


def _tool_executor(name: str, args: dict[str, Any]) -> Any:
    return {"ok": True, "tool": name, "args": args}


def test_adapter_instantiates() -> None:
    adapter = LangGraphAdapter(**DUMMY_KW)

    assert adapter.model_name == "gemini-2.5-flash"
    assert adapter.temperature == 0.0
    assert adapter.max_iterations == 20
    assert repr(adapter) == "LangGraphAdapter(model_name='gemini-2.5-flash')"


def test_tool_spec_conversion() -> None:
    adapter = LangGraphAdapter(**DUMMY_KW)
    telemetry = TrajectoryTelemetry(task_id="t", trial_index=0)
    specs: list[dict[str, Any]] = [
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

    lc_tools = adapter._build_structured_tools(specs, _tool_executor, telemetry)

    assert [t.name for t in lc_tools] == ["get_order", "cancel_order"]
    # the closure routes through the harness-provided executor
    assert lc_tools[0].invoke({"order_id": "A1"}) == {
        "ok": True,
        "tool": "get_order",
        "args": {"order_id": "A1"},
    }
    assert len(telemetry.tool_calls) == 1
    assert telemetry.tool_calls[0].tool_name == "get_order"


class _FakeLLM(GenericFakeChatModel):
    """Fake chat model that returns a canned final answer and never calls tools."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> _FakeLLM:
        return self


def test_run_with_mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = "FINAL ANSWER: order A1 shipped"

    def _fake_ctor(*args: Any, **kwargs: Any) -> _FakeLLM:
        return _FakeLLM(messages=iter([AIMessage(content=answer)]))

    monkeypatch.setattr("langchain_openai.ChatOpenAI", _fake_ctor)

    adapter = LangGraphAdapter(**DUMMY_KW)
    telemetry = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)

    result = adapter.run(
        task_prompt="Ship order A1.",
        tools=[
            {
                "name": "get_order",
                "description": "Fetch an order",
                "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}},
            }
        ],
        tool_executor=_tool_executor,
        telemetry=telemetry,
    )

    assert result == answer
    assert telemetry.wall_clock_time_ms > 0
    assert telemetry.tool_calls == []  # LLM answered without invoking any tool
