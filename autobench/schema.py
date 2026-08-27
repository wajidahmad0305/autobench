"""Pydantic models mirroring the authoritative ``tasks/schema.json``.

Any change to ``tasks/schema.json`` must be reflected here. This module also
provides the task-loading entry points used by ``scripts/validate_tasks.py``
and, later, by the runner.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

Category = Literal[
    "crm_order_fulfilment",
    "financial_reconciliation",
    "it_access_provisioning",
    "hr_employee_lifecycle",
]

Difficulty = Literal["easy", "medium", "hard"]

FaultType = Literal["HTTP_429", "HTTP_500", "HTTP_409", "SCHEMA_DRIFT", "TIMEOUT"]


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: str
    created: date
    domain_source: str
    notes: str | None = None


class EnvironmentSpec(BaseModel):
    """Mirrors the task's ``context`` object: the environment the agent starts in."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str
    available_tools: list[str]
    initial_state: dict[str, Any]


class RequiredToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    args_contain: dict[str, Any]
    order_sensitive: bool = False


class GroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_final_state: dict[str, Any]
    required_tool_calls: list[RequiredToolCall] = Field(default_factory=list)
    acceptable_responses: list[str] = Field(default_factory=list)


class HallucinationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forbidden_claims: list[str] = Field(default_factory=list)
    required_disclosures: list[str] = Field(default_factory=list)


class FaultInjectionRule(BaseModel):
    """Mirrors an item of ``reliability.fault_injection_rules``."""

    model_config = ConfigDict(extra="forbid")

    tool_target: str
    fault_type: FaultType
    trigger_probability: float = Field(ge=0.0, le=1.0)
    retry_after_ms: int | None = Field(default=None, ge=0)


class Reliability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hallucination_check: HallucinationCheck | None = None
    policy_rules: list[str] = Field(default_factory=list)
    max_tool_calls: int | None = Field(default=None, ge=1)
    expected_cost_range_usd: tuple[float, float] | None = None
    expected_latency_seconds: tuple[float, float] | None = None
    fault_injection_rules: list[FaultInjectionRule] = Field(default_factory=list)


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[a-z_]+\.[0-9]{3}$")
    category: Category
    difficulty: Difficulty
    description: str
    user_message: str
    context: EnvironmentSpec
    ground_truth: GroundTruth
    reliability: Reliability
    provenance: Provenance


def load_task(path: str) -> TaskSpec:
    """Load and validate a single task JSON file, raising a clear error on failure."""
    task_path = Path(path)
    try:
        raw = json.loads(task_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read task file {task_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Task file {task_path} is not valid JSON: {exc}") from exc

    try:
        return TaskSpec.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Task file {task_path} failed schema validation:\n{exc}") from exc


def validate_all_tasks(tasks_dir: str = "tasks") -> list[TaskSpec]:
    """Find every ``task_*.json`` under ``tasks_dir``, load and validate each.

    Excludes ``legacy_seed/``, which holds old-format reference tasks that are
    not expected to validate against the current schema. Prints progress to
    stderr. Raises on the first invalid file.
    """
    root = Path(tasks_dir)
    task_files = sorted(
        p for p in root.rglob("task_*.json") if "legacy_seed" not in p.parts
    )

    if not task_files:
        print(f"No task_*.json files found under {root}", file=sys.stderr)

    specs: list[TaskSpec] = []
    for task_file in task_files:
        print(f"Validating {task_file} ... ", file=sys.stderr, end="")
        spec = load_task(str(task_file))
        print("OK", file=sys.stderr)
        specs.append(spec)

    return specs
