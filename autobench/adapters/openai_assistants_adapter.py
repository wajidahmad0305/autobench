"""Concrete :class:`BaseAgentAdapter` backed by the OpenAI Assistants API (v2).

Unlike the LangGraph and CrewAI adapters, this one **cannot** run through Groq:
Groq is OpenAI-compatible for chat completions but not for
``client.beta.assistants`` / threads / runs. A real ``OPENAI_API_KEY`` is
required, and the constructor fails fast if one is not available.

Delivered for the Chapter 4 v1.0 milestone as a tested code artifact; it is not
part of the empirically-evaluated pilot.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

import structlog

from autobench.adapters.base import BaseAgentAdapter, ToolCallRecord, TrajectoryTelemetry

log = structlog.get_logger(__name__)

_DEFAULT_INSTRUCTIONS = (
    "You are a BPA automation specialist. Complete the given business process "
    "accurately by invoking appropriate tools."
)
_POLL_INTERVAL_S = 0.5
_RUN_TIMEOUT_S = 120.0
_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "expired", "incomplete"}
)


# ------------------------------------------------------------------- tool specs
# Mirrors the helper in ``langgraph_adapter`` / ``crewai_adapter``; kept local so
# each adapter stays self-contained.


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


def _to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert AutoBench tool specs into OpenAI function-tool dicts."""
    out: list[dict[str, Any]] = []
    for raw in tools:
        spec = _normalize_tool_spec(raw)
        out.append(
            {
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                },
            }
        )
    return out


def _assistant_message_text(messages_page: Any) -> str:
    """Concatenate the text blocks of the most recent assistant message."""
    for message in getattr(messages_page, "data", []) or []:
        if getattr(message, "role", None) != "assistant":
            continue
        parts: list[str] = []
        for block in getattr(message, "content", []) or []:
            text_obj = getattr(block, "text", None)
            if text_obj is not None:
                parts.append(str(getattr(text_obj, "value", "")))
        return "".join(parts)
    return ""


class OpenAIAssistantsAdapter(BaseAgentAdapter):
    """Run a task through one OpenAI Assistant + Thread + Run, polling to completion."""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: str = "",
        temperature: float = 0.0,
        max_iterations: int = 12,
        assistant_instructions: str = _DEFAULT_INSTRUCTIONS,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature)
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key:
            raise RuntimeError(
                "OpenAIAssistantsAdapter needs a real OpenAI API key: set "
                "OPENAI_API_KEY in your .env. Groq is NOT OpenAI-compatible for "
                "the Assistants API, so this adapter cannot run through Groq."
            )
        self.api_key = resolved_key
        self.max_iterations = max_iterations
        self.assistant_instructions = assistant_instructions

        import openai

        # Typed loosely on purpose: the beta Assistants surface is a deep tree of
        # optionals that adds no safety here.
        self._client: Any = openai.OpenAI(api_key=self.api_key)

    # ------------------------------------------------------------------ helpers

    def _dispatch_tool(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> Any:
        """Route one Assistants tool call through the harness executor; record telemetry."""
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

    def _handle_required_action(
        self,
        run: Any,
        thread_id: str,
        tool_executor: Callable[[str, dict[str, Any]], Any],
        telemetry: TrajectoryTelemetry,
    ) -> Any:
        """Execute every pending tool call and submit the outputs; return the new run."""
        action = getattr(run, "required_action", None)
        submit = getattr(action, "submit_tool_outputs", None)
        tool_calls = getattr(submit, "tool_calls", []) or []

        outputs: list[dict[str, str]] = []
        for call in tool_calls:
            fn = getattr(call, "function", None)
            name = str(getattr(fn, "name", ""))
            raw_args = getattr(fn, "arguments", "") or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            result = self._dispatch_tool(name, args, tool_executor, telemetry)
            outputs.append(
                {
                    "tool_call_id": str(getattr(call, "id", "")),
                    "output": json.dumps(result, default=str),
                }
            )

        return self._client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id, run_id=run.id, tool_outputs=outputs
        )

    @staticmethod
    def _record_token_usage(run: Any, telemetry: TrajectoryTelemetry) -> None:
        usage = getattr(run, "usage", None)
        if usage is None:
            return
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", 0) or 0)
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
        log.info(
            "adapter_run_start",
            adapter="openai_assistants",
            model=self.model_name,
            task_id=telemetry.task_id,
            trial_index=telemetry.trial_index,
            n_tools=len(tools),
            max_iterations=self.max_iterations,
        )

        client = self._client
        assistant = client.beta.assistants.create(
            name="autobench-bpa",
            model=self.model_name,
            instructions=self.assistant_instructions,
            tools=_to_openai_tools(tools),
        )

        start = time.perf_counter()
        hit_limit = False
        try:
            thread = client.beta.threads.create(
                messages=[{"role": "user", "content": task_prompt}]
            )
            run = client.beta.threads.runs.create(
                thread_id=thread.id, assistant_id=assistant.id
            )

            tool_rounds = 0
            while True:
                status = getattr(run, "status", None)
                if status == "requires_action":
                    if tool_rounds >= self.max_iterations:
                        hit_limit = True
                        _try_cancel(client, thread.id, run.id)
                        break
                    run = self._handle_required_action(
                        run, thread.id, tool_executor, telemetry
                    )
                    tool_rounds += 1
                    continue
                if status in _TERMINAL_STATUSES:
                    break
                if time.perf_counter() - start > _RUN_TIMEOUT_S:
                    hit_limit = True
                    _try_cancel(client, thread.id, run.id)
                    break
                time.sleep(_POLL_INTERVAL_S)
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run.id
                )

            telemetry.wall_clock_time_ms = (time.perf_counter() - start) * 1000.0
            self._record_token_usage(run, telemetry)
            messages_page = client.beta.threads.messages.list(
                thread_id=thread.id, order="desc", limit=10
            )
            final_text = _assistant_message_text(messages_page)
        finally:
            try:
                client.beta.assistants.delete(assistant.id)
            except Exception as exc:  # noqa: BLE001 - cleanup must not mask results
                log.debug("assistant_cleanup_failed", error=str(exc))

        if hit_limit:
            log.warning(
                "adapter_max_iterations",
                model=self.model_name,
                task_id=telemetry.task_id,
                max_iterations=self.max_iterations,
            )

        log.info(
            "adapter_run_end",
            adapter="openai_assistants",
            model=self.model_name,
            task_id=telemetry.task_id,
            wall_clock_time_ms=round(telemetry.wall_clock_time_ms, 2),
            n_tool_calls=len(telemetry.tool_calls),
            total_tokens=telemetry.total_tokens,
            hit_max_iterations=hit_limit,
        )
        return final_text


def _try_cancel(client: Any, thread_id: str, run_id: str) -> None:
    try:
        client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
    except Exception as exc:  # noqa: BLE001 - best-effort
        log.debug("run_cancel_failed", error=str(exc))

