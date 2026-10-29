from __future__ import annotations

import types
from typing import Any

import pytest

from autobench.adapters.base import TrajectoryTelemetry
from autobench.adapters.openai_assistants_adapter import (
    OpenAIAssistantsAdapter,
    _to_openai_tools,
)

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
def _dummy_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-not-used")


def _fake_openai_client(answer: str, usage: tuple[int, int, int]) -> Any:
    """A minimal stand-in for ``openai.OpenAI()`` whose run completes at once."""
    run = types.SimpleNamespace(
        id="run_1",
        status="completed",
        required_action=None,
        usage=types.SimpleNamespace(
            prompt_tokens=usage[0],
            completion_tokens=usage[1],
            total_tokens=usage[2],
        ),
    )
    message = types.SimpleNamespace(
        role="assistant",
        content=[types.SimpleNamespace(text=types.SimpleNamespace(value=answer))],
    )
    runs = types.SimpleNamespace(
        create=lambda **kw: run,
        retrieve=lambda **kw: run,
        submit_tool_outputs=lambda **kw: run,
        cancel=lambda **kw: None,
    )
    threads = types.SimpleNamespace(
        create=lambda **kw: types.SimpleNamespace(id="thread_1"),
        runs=runs,
        messages=types.SimpleNamespace(
            list=lambda **kw: types.SimpleNamespace(data=[message])
        ),
    )
    assistants = types.SimpleNamespace(
        create=lambda **kw: types.SimpleNamespace(id="asst_1"),
        delete=lambda *a, **kw: None,
    )
    return types.SimpleNamespace(
        beta=types.SimpleNamespace(assistants=assistants, threads=threads)
    )


def test_openai_assistants_instantiates(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenAIAssistantsAdapter()

    assert adapter.model_name == "gpt-4o-mini"
    assert adapter.temperature == 0.0
    assert adapter.max_iterations == 12
    assert "gpt-4o-mini" in repr(adapter)
    assert repr(adapter) == "OpenAIAssistantsAdapter(model_name='gpt-4o-mini')"

    # No key anywhere -> fail fast at construction with a clear message.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIAssistantsAdapter()


def test_openai_tool_conversion() -> None:
    oai_tools = _to_openai_tools(TWO_TOOLS)

    assert [t["type"] for t in oai_tools] == ["function", "function"]
    assert [t["function"]["name"] for t in oai_tools] == ["get_order", "cancel_order"]
    assert oai_tools[0]["function"]["parameters"]["properties"] == {
        "order_id": {"type": "string"}
    }


def test_run_with_mock_client(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = "FINAL ANSWER: order A1 cancelled"
    monkeypatch.setattr(
        "openai.OpenAI",
        lambda *a, **kw: _fake_openai_client(answer, usage=(31, 12, 43)),
    )

    adapter = OpenAIAssistantsAdapter(model_name="gpt-4o-mini")
    telemetry = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)

    result = adapter.run(
        task_prompt="Cancel order A1.",
        tools=TWO_TOOLS,
        tool_executor=_tool_executor,
        telemetry=telemetry,
    )

    assert result == answer
    assert telemetry.wall_clock_time_ms > 0
    assert telemetry.prompt_tokens == 31
    assert telemetry.completion_tokens == 12
    assert telemetry.total_tokens == 43
    assert telemetry.tool_calls == []  # run completed without requires_action

