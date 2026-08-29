from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from scripts.run_pilot import run_pilot
from tests.test_evaluator import _CRM_SCRIPT, _scripted_llm, _tool_specs

_REPO = Path(__file__).resolve().parents[1]
_TRACE_NAME = "C1__crm_order_fulfilment.001__trial0.json"


def _mini_pilot(tmp_path: Path) -> tuple[dict[str, Any], Path, Path]:
    category = "crm_order_fulfilment"
    tasks_root = tmp_path / "tasks"
    (tasks_root / category).mkdir(parents=True)
    shutil.copy(
        _REPO / "tasks" / category / "task_001.json",
        tasks_root / category / "task_001.json",
    )
    config: dict[str, Any] = {
        "master_seed": 20260827,
        "configurations": [
            {
                "config_id": "C1",
                "model_name": "fake",
                "base_url": "http://x",
                "api_key_env": "TEST_API_KEY",
                "temperature": 0.0,
                "framework": "LangGraph",
            }
        ],
        "task_categories": [category],
        "trials_per_task": 1,
    }
    return config, tmp_path / "traces", tasks_root


def test_resume_skips_existing_traces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, traces_dir, tasks_root = _mini_pilot(tmp_path)
    monkeypatch.setenv("TEST_API_KEY", "x")
    traces_dir.mkdir(parents=True)
    existing = traces_dir / _TRACE_NAME
    existing.write_text('{"status": "PASS", "preexisting": true}', encoding="utf-8")

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("adapter.run must not be called for an existing trace")

    monkeypatch.setattr("scripts.run_pilot.LangGraphAdapter.run", _boom)

    counts = run_pilot(config, traces_dir, tasks_root, between_trial_sleep_s=0.0)

    assert counts["SKIP"] == 1
    assert json.loads(existing.read_text(encoding="utf-8")) == {
        "status": "PASS",
        "preexisting": True,
    }


def test_error_trajectory_gets_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, traces_dir, tasks_root = _mini_pilot(tmp_path)
    monkeypatch.setenv("TEST_API_KEY", "x")

    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated adapter failure")

    monkeypatch.setattr("scripts.run_pilot.LangGraphAdapter.run", _raise)

    counts = run_pilot(config, traces_dir, tasks_root, between_trial_sleep_s=0.0)

    trace = traces_dir / _TRACE_NAME
    assert trace.exists()
    record = json.loads(trace.read_text(encoding="utf-8"))
    assert record["status"] == "ERROR"
    assert "simulated adapter failure" in record["error"]
    assert counts["ERROR"] == 1


def test_single_trajectory_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, traces_dir, tasks_root = _mini_pilot(tmp_path)
    monkeypatch.setenv("TEST_API_KEY", "x")
    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI", lambda *a, **k: _scripted_llm(_CRM_SCRIPT)
    )
    # The runner's tool-spec synthesis is a lower bound (see _tool_specs_from_task);
    # give the scripted model a schema that covers every field it sends.
    monkeypatch.setattr(
        "scripts.run_pilot._tool_specs_from_task",
        lambda task: _tool_specs(task, _CRM_SCRIPT),
    )

    counts = run_pilot(config, traces_dir, tasks_root, between_trial_sleep_s=0.0)

    trace = traces_dir / _TRACE_NAME
    assert trace.exists()
    record = json.loads(trace.read_text(encoding="utf-8"))

    assert record["status"] == "PASS"
    assert record["config_id"] == "C1"
    assert record["task_id"] == "crm_order_fulfilment.001"
    assert record["trial_index"] == 0
    assert record["seed"] == "crm_order_fulfilment.001-0-20260827"
    assert record["metrics"]["tsi"] == 1.0
    assert record["metrics"]["sec"] == 1.0
    assert record["metrics"]["sla_compliance"] == 1.0
    assert record["metrics"]["fault_recovered"] is None
    assert record["telemetry"]["task_id"] == "crm_order_fulfilment.001"
    assert record["telemetry"]["tool_calls"]
    assert counts["PASS"] == 1
