"""Adapter-facing telemetry models and the abstract agent adapter interface.

Every LangGraph-backed adapter (Gemini, Groq) records its trajectory into a
``TrajectoryTelemetry`` instance, appending one ``ToolCallRecord`` per tool
invocation. The evaluator and trace writer consume this telemetry after the
run completes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any]
    output: Any
    latency_ms: float
    is_error: bool
    fault_injected: str | None = None


class TrajectoryTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    trial_index: int
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0
    wall_clock_time_ms: float = 0.0
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    state_diffs: dict[str, Any] = Field(default_factory=dict)
    success: bool = False
    invariants_passed: bool = False
    unauthorized_side_effects: list[str] = Field(default_factory=list)

    def add_tool_call(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class BaseAgentAdapter(ABC):
    """Common interface implemented by every LLM/orchestration adapter."""

    def __init__(self, model_name: str, temperature: float = 0.0) -> None:
        self.model_name = model_name
        self.temperature = temperature

    @abstractmethod
    def run(
        self,
        task_prompt: str,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> str:
        """Run the agent to completion on a single task, mutating ``telemetry`` in place.

        Returns the agent's final response text.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model_name={self.model_name!r})"
