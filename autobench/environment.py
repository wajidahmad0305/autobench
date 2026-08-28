"""The fault-injecting mock backend (thesis Ch. 4 §4.4, Listing 4.4).

``FaultInjectingEnvironment`` sits between the agent adapter and the per-category
mock backends. For every tool call it:

1. normalises the arguments (some models wrap scalars in single-element lists),
2. consults the task's ``fault_injection_rules`` and, using a *pre-seeded* RNG,
   decides whether to inject a fault this call,
3. either returns a structured fault response / raises, or dispatches to the
   real mock backend,
4. records a :class:`ToolCallRecord` into the trajectory telemetry either way.

Determinism contract (Ch. 4 §4.3): the RNG is created once by the runner from
``(task_id, trial_index, master_seed)`` and handed in. This class must never
call ``random.random()`` directly — only ``self.rng`` — and must consume
exactly one draw per fault-eligible call so replays line up.
"""

from __future__ import annotations

import concurrent.futures
import random
import sqlite3
import time
from typing import Any

import structlog

from autobench.adapters.base import ToolCallRecord, TrajectoryTelemetry
from autobench.backends import (
    crm_order_fulfilment,
    financial_reconciliation,
    hr_employee_lifecycle,
    it_access_provisioning,
)
from autobench.schema import FaultInjectionRule, TaskSpec

log = structlog.get_logger(__name__)

# A TIMEOUT fault sleeps briefly before raising, so the trajectory sees a
# non-zero latency the way a real hung call would.
_TIMEOUT_SIMULATED_DELAY_S = 0.01

# Category -> backend module (each exposes initialize() and dispatch()).
_BACKENDS: dict[str, Any] = {
    "crm_order_fulfilment": crm_order_fulfilment,
    "financial_reconciliation": financial_reconciliation,
    "it_access_provisioning": it_access_provisioning,
    "hr_employee_lifecycle": hr_employee_lifecycle,
}


class FaultInjectingEnvironment:
    """Route tool calls through fault injection to the per-category mock backends."""

    def __init__(
        self,
        task_spec: TaskSpec,
        db_conn: sqlite3.Connection,
        telemetry: TrajectoryTelemetry,
        rng: random.Random,
    ) -> None:
        self.task_spec = task_spec
        self.db_conn = db_conn
        self.telemetry = telemetry
        self.rng = rng

        # Index rules by target tool for O(1) lookup. If a task lists more than
        # one rule for the same tool, the first one wins (deterministic).
        self._rules_by_tool: dict[str, FaultInjectionRule] = {}
        for rule in task_spec.reliability.fault_injection_rules:
            self._rules_by_tool.setdefault(rule.tool_target, rule)

        # Seed the in-memory DB for this task's category via its mock backend.
        self._backend = _BACKENDS[task_spec.category]
        self._backend.initialize(db_conn, task_spec)

    # ------------------------------------------------------------------ helpers

    def _normalize_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Unwrap any single-element list argument into its scalar.

        e.g. ``{"email": ["a@b.com"]}`` -> ``{"email": "a@b.com"}``. Some models
        (notably ``qwen/qwen3.8-27b``) emit tool arguments this way.
        """
        normalized: dict[str, Any] = {}
        for key, value in arguments.items():
            if isinstance(value, list) and len(value) == 1:
                log.debug(
                    "unwrap_single_element_list",
                    key=key,
                    original=value,
                    unwrapped=value[0],
                )
                normalized[key] = value[0]
            else:
                normalized[key] = value
        return normalized

    # --------------------------------------------------------------- public API

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute one tool call, possibly injecting a fault, recording telemetry."""
        args = self._normalize_arguments(arguments)
        rule = self._rules_by_tool.get(tool_name)

        if rule is not None:
            roll = self.rng.random()  # exactly one draw per fault-eligible call
            if roll < rule.trigger_probability:
                return self._apply_fault(tool_name, args, rule)
            log.debug(
                "fault_roll_passed",
                tool=tool_name,
                roll=roll,
                threshold=rule.trigger_probability,
            )

        start = time.perf_counter()
        result = self._dispatch_to_db(tool_name, args)
        latency_ms = (time.perf_counter() - start) * 1000.0
        self.telemetry.add_tool_call(
            ToolCallRecord(
                tool_name=tool_name,
                arguments=args,
                output=result,
                latency_ms=latency_ms,
                is_error=False,
                fault_injected=None,
            )
        )
        return result

    # -------------------------------------------------------------- fault paths

    def _apply_fault(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        rule: FaultInjectionRule,
    ) -> Any:
        """Produce the fault response for ``rule.fault_type`` and record it."""
        fault_type = rule.fault_type
        log.info("fault_injected", tool=tool_name, fault_type=fault_type)

        if fault_type == "TIMEOUT":
            time.sleep(_TIMEOUT_SIMULATED_DELAY_S)
            self._record_fault(
                tool_name,
                arguments,
                {"error": "TIMEOUT: simulated tool timeout"},
                fault_type,
                latency_ms=_TIMEOUT_SIMULATED_DELAY_S * 1000.0,
            )
            raise concurrent.futures.TimeoutError(
                f"Simulated timeout for tool {tool_name!r}"
            )

        response: Any
        latency_ms = 0.0
        if fault_type == "HTTP_429":
            response = {
                "error": "HTTP 429: Rate limit exceeded",
                "retry_after_ms": rule.retry_after_ms,
            }
        elif fault_type == "HTTP_500":
            response = {"error": "HTTP 500: Internal Server Error"}
        elif fault_type == "HTTP_409":
            response = {"error": "HTTP 409: Conflict — resource locked"}
        elif fault_type == "SCHEMA_DRIFT":
            start = time.perf_counter()
            response = self._schema_drift(tool_name, arguments)
            latency_ms = (time.perf_counter() - start) * 1000.0
        else:  # pragma: no cover - FaultType Literal is exhaustive above
            response = {"error": f"Unknown fault type: {fault_type}"}

        self._record_fault(tool_name, arguments, response, fault_type, latency_ms=latency_ms)
        return response

    def _record_fault(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        output: Any,
        fault_type: str,
        *,
        latency_ms: float,
    ) -> None:
        self.telemetry.add_tool_call(
            ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                output=output,
                latency_ms=latency_ms,
                is_error=True,
                fault_injected=fault_type,
            )
        )

    def _schema_drift(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Return the normal response with exactly one field renamed."""
        normal = self._dispatch_to_db(tool_name, arguments)
        if not isinstance(normal, dict) or not normal:
            return {"identifier": normal}

        drifted = dict(normal)
        if "id" in drifted:
            drifted["identifier"] = drifted.pop("id")
        else:
            first_key = next(iter(drifted))
            drifted[f"{first_key}_renamed"] = drifted.pop(first_key)
        log.debug(
            "schema_drift_applied",
            tool=tool_name,
            before=list(normal),
            after=list(drifted),
        )
        return drifted

    # --------------------------------------------------------------- dispatch

    def _dispatch_to_db(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Route the tool call to this task's per-category mock backend.

        Raises ``ValueError`` (from the backend) if the tool is unknown to the
        category.
        """
        return self._backend.dispatch(self.db_conn, tool_name, arguments)
