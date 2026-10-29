from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from types import ModuleType

import pytest

from autobench.adapters.base import TrajectoryTelemetry
from autobench.backends import (
    _kvstore,
    crm_order_fulfilment,
    financial_reconciliation,
    hr_employee_lifecycle,
    it_access_provisioning,
)
from autobench.environment import FaultInjectingEnvironment
from autobench.schema import TaskSpec, load_task

_TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"

CATEGORIES: list[tuple[str, ModuleType]] = [
    ("crm_order_fulfilment", crm_order_fulfilment),
    ("financial_reconciliation", financial_reconciliation),
    ("it_access_provisioning", it_access_provisioning),
    ("hr_employee_lifecycle", hr_employee_lifecycle),
]


def _task_001(category: str) -> TaskSpec:
    return load_task(str(_TASKS_DIR / category / "task_001.json"))


@pytest.mark.parametrize("category,backend", CATEGORIES, ids=[c for c, _ in CATEGORIES])
def test_category_initializes_without_error(category: str, backend: ModuleType) -> None:
    conn = sqlite3.connect(":memory:")
    spec = _task_001(category)

    backend.initialize(conn, spec)

    assert "kv_state" in _kvstore.table_names(conn)
    # every top-level key of the task's initial_state round-trips out of the DB
    seed_keys = list(spec.context.initial_state)
    assert seed_keys
    for key in seed_keys:
        assert _kvstore.load(conn, key, "__missing__") != "__missing__"


@pytest.mark.parametrize("category,backend", CATEGORIES, ids=[c for c, _ in CATEGORIES])
def test_category_dispatch_smoke(category: str, backend: ModuleType) -> None:
    conn = sqlite3.connect(":memory:")
    spec = _task_001(category)
    backend.initialize(conn, spec)

    seen: set[str] = set()
    for call in spec.ground_truth.required_tool_calls:
        if call.tool in seen:
            continue
        seen.add(call.tool)
        result = backend.dispatch(conn, call.tool, dict(call.args_contain))
        assert isinstance(result, dict), f"{category}:{call.tool} returned {type(result)}"

    assert seen, f"{category} task_001 has no required_tool_calls"


def test_end_to_end_environment_with_real_backend() -> None:
    spec = _task_001("crm_order_fulfilment")
    conn = sqlite3.connect(":memory:")
    telemetry = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)

    env = FaultInjectingEnvironment(
        task_spec=spec,
        db_conn=conn,
        telemetry=telemetry,
        rng=random.Random(0),
    )

    for call in spec.ground_truth.required_tool_calls:
        out = env.execute_tool(call.tool, dict(call.args_contain))
        assert isinstance(out, dict) and out, f"{call.tool} -> {out!r}"

    assert len(telemetry.tool_calls) == len(spec.ground_truth.required_tool_calls)
    # the contact the agent 'created' is now retrievable, and it carries the tag
    contact = _kvstore.get_item(conn, "hubspot_contacts", "jordan.lee@example.com")
    assert contact is not None
    assert "WGT-100-BLU" in contact.get("tags", [])

