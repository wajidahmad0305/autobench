"""Concrete :class:`BaseAgentAdapter` backed by CrewAI.

A single :class:`CrewAIAdapter` drives any OpenAI-compatible chat endpoint
through a one-agent / one-task sequential CrewAI crew. Like
:mod:`autobench.adapters.langgraph_adapter`, the Groq configs (C1/C2/C3) differ
only in ``(model_name, base_url, api_key)``.

The heavy CrewAI / LangChain imports are deferred into the methods that need
them so importing this module (and constructing the adapter) stays cheap and
does not require the LLM stack to be installed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel, SecretStr, create_model

from autobench.adapters.base import BaseAgentAdapter, ToolCallRecord, TrajectoryTelemetry

log = structlog.get_logger(__name__)

_DEFAULT_ROLE = "BPA Automation Specialist"
_DEFAULT_GOAL = (
    "Complete the business process accurately by invoking the appropriate tools "
    "in the correct order"
)
_BACKSTORY = (
    "You are a meticulous operations specialist. You execute enterprise business "
    "processes by calling the tools you are given, in the right sequence, and you "
    "never skip a required step or invent data."
)
_EXPECTED_OUTPUT = (
    "A short confirmation that the business process was completed, noting the key "
    "tool calls that were made."
)


# ------------------------------------------------------------------- tool specs
# These two helpers are deliberately duplicated from ``langgraph_adapter`` to
# keep this adapter self-contained; both are pure and version-independent.


def _normalize_tool_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Reduce the accepted tool-dict shapes to ``{name, description, parameters}``."""
    if "function" in spec and isinstance(spec["function"], dict):
        spec = spec["function"]
    name = spec.get("name")
    if not name:
        raise ValueError(f"tool spec is missing a 'name': {spec!r}")
    description = spec.get("description", "") or ""
    parameters = (
        spec.get("parameters")
        or spec.get("args")
        or spec.get("input_schema")
        or {"type": "object", "properties": {}}
    )
    return {"name": name, "description": description, "parameters": parameters}


def _args_model(name: str, parameters: dict[str, Any]) -> type[BaseModel]:
    """Build a permissive Pydantic args schema from a JSON-Schema ``parameters`` block."""
    properties: dict[str, Any] = parameters.get("properties", {}) or {}
    required = set(parameters.get("required", []) or [])
    fields: dict[str, Any] = {}
    for field_name in properties:
        default = ... if field_name in required else None
        # Loose typing: the fault-injection layer validates real semantics.
        fields[field_name] = (Any, default)
    model_name = f"{name.strip().replace(' ', '_') or 'tool'}_Args"
    return create_model(model_name, **fields)


# ---------------------------------------------------------------- output helpers


def _looks_like_max_iter(exc: BaseException) -> bool:
    """True when an exception text indicates CrewAI stopped on its iteration cap."""
    text = str(exc).lower()
    return (
        "maximum iterations" in text
        or "max_iter" in text
        or "iteration limit" in text
    )


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def _final_text(result: object) -> str:
    """Pull the final response string out of whatever ``crew.kickoff`` returned."""
    if isinstance(result, str):
        return result
    for attr in ("raw", "output", "result"):
        value = getattr(result, attr, None)
        if isinstance(value, str):
            return value
    return str(result)


def _partial_text(source: object) -> str:
    """Best-effort content to salvage from a soft (max-iterations) stop."""
    for attr in ("raw", "output", "result"):
        value = getattr(source, attr, None)
        if isinstance(value, str) and value:
            return value
    return ""


class CrewAIAdapter(BaseAgentAdapter):
    """Run a task through a sequential CrewAI crew against an OpenAI-compatible LLM."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.0,
        max_iterations: int = 12,
        agent_role: str = _DEFAULT_ROLE,
        agent_goal: str = _DEFAULT_GOAL,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature)
        self.api_key = api_key
        self.base_url = base_url
        self.max_iterations = max_iterations
        self.agent_role = agent_role
        self.agent_goal = agent_goal

    # ------------------------------------------------------------------ helpers

    def _dispatch_tool(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> Any:
        """Route one CrewAI tool call through the harness executor; record telemetry."""
        start = time.perf_counter()
        is_error = False
        try:
            output = tool_executor(tool_name, kwargs)
        except Exception as exc:  # noqa: BLE001 - hand the error back to the model
            is_error = True
            output = f"ERROR: {exc}"
            log.debug("tool_call_exception", tool=tool_name, error=str(exc))
        latency_ms = (time.perf_counter() - start) * 1000.0

        fault_injected: str | None = None
        if isinstance(output, dict):
            fault_val = output.get("fault_injected")
            fault_injected = fault_val if isinstance(fault_val, str) else None
            if output.get("is_error"):
                is_error = True

        telemetry.add_tool_call(
            ToolCallRecord(
                tool_name=tool_name,
                arguments=dict(kwargs),
                output=output,
                latency_ms=latency_ms,
                is_error=is_error,
                fault_injected=fault_injected,
            )
        )
        log.debug(
            "tool_call",
            tool=tool_name,
            arguments=kwargs,
            latency_ms=round(latency_ms, 2),
            is_error=is_error,
            fault_injected=fault_injected,
        )
        return output

    def _wrap_tool(
        self,
        base_tool_cls: Any,
        name: str,
        description: str,
        args_model: type[BaseModel],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> Any:
        """One CrewAI ``BaseTool`` instance whose ``_run`` closes over the executor."""
        adapter = self

        class _WrappedTool(base_tool_cls):  # type: ignore[misc]  # base_tool_cls is Any
            def _run(self, **kwargs: Any) -> Any:
                return adapter._dispatch_tool(name, kwargs, tool_executor, telemetry)

        return _WrappedTool(name=name, description=description, args_schema=args_model)

    def _build_crewai_tools(
        self,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> list[Any]:
        """Convert AutoBench tool specs into CrewAI ``BaseTool`` instances."""
        from crewai.tools import BaseTool

        built: list[Any] = []
        for raw in tools:
            spec = _normalize_tool_spec(raw)
            built.append(
                self._wrap_tool(
                    BaseTool,
                    spec["name"],
                    spec["description"],
                    _args_model(spec["name"], spec["parameters"]),
                    tool_executor,
                    telemetry,
                )
            )
        return built

    @staticmethod
    def _record_token_usage(
        result: object, crew: object, telemetry: TrajectoryTelemetry
    ) -> None:
        """Record CrewAI token accounting if the crew exposed any."""
        usage = getattr(result, "token_usage", None)
        if usage is None:
            usage = getattr(crew, "usage_metrics", None)
        if usage is None:
            return
        prompt = _as_int(getattr(usage, "prompt_tokens", 0))
        completion = _as_int(getattr(usage, "completion_tokens", 0))
        total = _as_int(getattr(usage, "total_tokens", 0))
        if prompt or completion or total:
            telemetry.prompt_tokens = prompt
            telemetry.completion_tokens = completion
            telemetry.total_tokens = total or (prompt + completion)

    # --------------------------------------------------------------------- run

    def run(
        self,
        task_prompt: str,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> str:
        from crewai import Agent, Crew, Process, Task
        from langchain_openai import ChatOpenAI

        log.info(
            "adapter_run_start",
            adapter="crewai",
            model=self.model_name,
            task_id=telemetry.task_id,
            trial_index=telemetry.trial_index,
            n_tools=len(tools),
            max_iterations=self.max_iterations,
        )

        crew_tools = self._build_crewai_tools(tools, tool_executor, telemetry)

        try:
            llm = ChatOpenAI(
                model=self.model_name,
                api_key=SecretStr(self.api_key),
                base_url=self.base_url,
                temperature=self.temperature,
            )
        except Exception as exc:
            log.error("llm_init_failed", model=self.model_name, error=str(exc))
            raise

        agent = Agent(
            role=self.agent_role,
            goal=self.agent_goal,
            backstory=_BACKSTORY,
            tools=crew_tools,
            llm=llm,
            max_iter=self.max_iterations,
            verbose=False,
        )
        task = Task(description=task_prompt, expected_output=_EXPECTED_OUTPUT, agent=agent)
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        start = time.perf_counter()
        try:
            result: Any = crew.kickoff()
        except Exception as exc:
            telemetry.wall_clock_time_ms = (time.perf_counter() - start) * 1000.0
            if _looks_like_max_iter(exc):
                log.warning(
                    "adapter_max_iterations",
                    model=self.model_name,
                    task_id=telemetry.task_id,
                    max_iterations=self.max_iterations,
                    error=str(exc),
                )
                return _partial_text(exc)
            log.error("adapter_run_failed", model=self.model_name, error=str(exc))
            raise

        telemetry.wall_clock_time_ms = (time.perf_counter() - start) * 1000.0
        self._record_token_usage(result, crew, telemetry)
        final_text = _final_text(result)

        log.info(
            "adapter_run_end",
            adapter="crewai",
            model=self.model_name,
            task_id=telemetry.task_id,
            wall_clock_time_ms=round(telemetry.wall_clock_time_ms, 2),
            n_tool_calls=len(telemetry.tool_calls),
            total_tokens=telemetry.total_tokens,
        )
        return final_text

