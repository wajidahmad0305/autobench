"""Concrete :class:`BaseAgentAdapter` backed by LangChain's ``create_agent``.

A single :class:`LangGraphAdapter` drives *any* OpenAI-compatible chat
endpoint. Gemini 2.5 Flash (via Google's OpenAI-compat layer) and Llama 3.3
70B (via Groq) differ only in ``(model_name, base_url, api_key)``.

The heavy LangChain / LangGraph imports are deferred into :meth:`run` so that
importing this module (and constructing the adapter) stays cheap and does not
require the LLM stack to be installed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, SecretStr, create_model

from autobench.adapters.base import BaseAgentAdapter, ToolCallRecord, TrajectoryTelemetry

log = structlog.get_logger(__name__)


class LangGraphAdapter(BaseAgentAdapter):
    """Run a task through ``langchain.agents.create_agent`` against an OpenAI-compatible LLM."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.0,
        max_iterations: int = 12,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature)
        self.api_key = api_key
        self.base_url = base_url
        self.max_iterations = max_iterations

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _normalize_tool_spec(spec: dict[str, Any]) -> dict[str, Any]:
        """Reduce the various accepted tool-dict shapes to ``{name, description, parameters}``."""
        # OpenAI function-calling shape: {"type": "function", "function": {...}}
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

    @staticmethod
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

    def _make_tool_fn(
        self,
        tool_name: str,
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> Callable[..., Any]:
        """Closure invoked by LangGraph for one tool call; records telemetry per call."""

        def _call(**kwargs: Any) -> Any:
            start = time.perf_counter()
            is_error = False
            output: Any
            # A failing tool must not abort the run: catch anything, hand the
            # error text back to the model, and let the trajectory continue.
            try:
                output = tool_executor(tool_name, kwargs)
            except Exception as exc:  # noqa: BLE001
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

        return _call

    def _build_structured_tools(
        self,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> list[StructuredTool]:
        """Convert AutoBench tool specs into LangChain ``StructuredTool`` objects."""
        built: list[StructuredTool] = []
        for raw in tools:
            spec = self._normalize_tool_spec(raw)
            args_model = self._args_model(spec["name"], spec["parameters"])
            built.append(
                StructuredTool.from_function(
                    func=self._make_tool_fn(spec["name"], tool_executor, telemetry),
                    name=spec["name"],
                    description=spec["description"],
                    args_schema=args_model,
                )
            )
        return built

    def _recursion_limit(self) -> int:
        """LangGraph counts super-steps; a ReAct turn is ~2 (agent + tools)."""
        return max(2 * self.max_iterations + 1, 2)

    @staticmethod
    def _final_text(state: dict[str, Any] | None) -> str:
        if not isinstance(state, dict):
            return ""
        messages = state.get("messages") or []
        if not messages:
            return ""
        content = getattr(messages[-1], "content", messages[-1])
        if isinstance(content, str):
            return content
        if isinstance(content, list):  # content-block form
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(str(block.get("text", "")))
                else:
                    parts.append(str(block))
            return "".join(parts)
        return str(content)

    @staticmethod
    def _record_token_usage(state: dict[str, Any] | None, telemetry: TrajectoryTelemetry) -> None:
        if not isinstance(state, dict):
            return
        prompt = completion = total = 0
        for message in state.get("messages") or []:
            usage = getattr(message, "usage_metadata", None)
            if not isinstance(usage, dict):
                continue
            prompt += int(usage.get("input_tokens") or 0)
            completion += int(usage.get("output_tokens") or 0)
            total += int(usage.get("total_tokens") or 0)
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
        from langchain.agents import create_agent
        from langchain_core.messages import HumanMessage
        from langchain_core.runnables import RunnableConfig
        from langchain_openai import ChatOpenAI
        from langgraph.errors import GraphRecursionError

        log.info(
            "adapter_run_start",
            model=self.model_name,
            task_id=telemetry.task_id,
            trial_index=telemetry.trial_index,
            n_tools=len(tools),
            max_iterations=self.max_iterations,
        )

        lc_tools = self._build_structured_tools(tools, tool_executor, telemetry)

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

        agent = create_agent(llm, lc_tools)

        last_state: dict[str, Any] | None = None
        hit_limit = False
        agent_input = {"messages": [HumanMessage(content=task_prompt)]}
        config = RunnableConfig(recursion_limit=self._recursion_limit())
        start = time.perf_counter()
        try:
            # langchain types `stream`'s input as the internal InputAgentState
            # TypedDict; the {"messages": [...]} form is the documented public
            # contract and works at runtime.
            stream = agent.stream(  # type: ignore[call-overload]
                agent_input, config=config, stream_mode="values"
            )
            for chunk in stream:
                last_state = chunk
                # Update token usage live so a runner can enforce a token cap
                # mid-trajectory.
                self._record_token_usage(last_state, telemetry)
        except GraphRecursionError:
            hit_limit = True
            log.warning(
                "adapter_max_iterations",
                model=self.model_name,
                task_id=telemetry.task_id,
                max_iterations=self.max_iterations,
            )
        except Exception as exc:
            telemetry.wall_clock_time_ms = (time.perf_counter() - start) * 1000.0
            log.error("adapter_run_failed", model=self.model_name, error=str(exc))
            raise

        telemetry.wall_clock_time_ms = (time.perf_counter() - start) * 1000.0
        self._record_token_usage(last_state, telemetry)
        final = self._final_text(last_state)

        log.info(
            "adapter_run_end",
            model=self.model_name,
            task_id=telemetry.task_id,
            wall_clock_time_ms=round(telemetry.wall_clock_time_ms, 2),
            n_tool_calls=len(telemetry.tool_calls),
            total_tokens=telemetry.total_tokens,
            hit_max_iterations=hit_limit,
        )
        return final
