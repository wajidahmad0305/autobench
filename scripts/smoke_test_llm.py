"""End-to-end smoke test: drive real LLMs through a real tool-calling loop.

Proves that :class:`LangGraphAdapter` can take a real AutoBench task, talk to a
live OpenAI-compatible endpoint, and run a tool-calling loop against a mock
executor (no real backend, no fault injection, no database).

By default this runs EVERY configuration in
``experiments/thesis_pilot/config.json`` and requires each to reach
``[SMOKE TEST PASSED]``. A single ad-hoc model can be run instead via env vars::

    LLM_MODEL=openai/gpt-oss-20b python scripts/smoke_test_llm.py
    LLM_MODEL=... LLM_BASE_URL=... LLM_KEY_ENV=... python scripts/smoke_test_llm.py

Note (2026-08): CLAUDE.md originally named ``gemini-2.5-flash`` and
``llama-3.3-70b-versatile``; both were retired from their free tiers before the
pilot ran. The pilot now uses two Groq models (see the config file).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from autobench.adapters.base import TrajectoryTelemetry
from autobench.adapters.langgraph_adapter import LangGraphAdapter
from autobench.backends import tool_registry
from autobench.schema import TaskSpec, load_task

REPO_ROOT = Path(__file__).resolve().parent.parent
TASK_PATH = REPO_ROOT / "tasks" / "crm_order_fulfilment" / "task_001.json"
PILOT_CONFIG_PATH = REPO_ROOT / "experiments" / "thesis_pilot" / "config.json"

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_KEY_ENV = "GROQ_API_KEY"


def _load_env() -> None:
    """Load .env from the repo root or the package dir (whichever exists)."""
    for candidate in (REPO_ROOT / ".env", REPO_ROOT / "autobench" / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            print(f"[env]    loaded {candidate}")
            return
    load_dotenv()  # fall back to default upward search
    print("[env]    no .env file found in repo root or autobench/; used default search")


def _tool_specs_from_task(task: TaskSpec) -> list[dict[str, Any]]:
    """Full JSON Schema for every tool the task exposes, from the tool registry."""
    return [
        tool_registry.get_tool_schema(task.category, tool_name)
        for tool_name in task.context.available_tools
    ]


def _make_mock_executor() -> Any:
    def mock_executor(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        print(f"[tool>]  {tool_name}  args={arguments}")
        response = {"status": "ok", "mock": True, "tool": tool_name}
        print(f"[tool<]  {tool_name}  -> {response}")
        return response

    return mock_executor


def _run_one_config(
    config_id: str,
    model_name: str,
    base_url: str,
    key_env: str,
    task: TaskSpec,
) -> bool:
    """Run the 6-stage smoke flow for one configuration. Returns True on PASS."""
    banner = f"  CONFIG {config_id}:  {model_name}  "
    print("\n" + "#" * 78)
    print("#" + banner.center(76) + "#")
    print("#" * 78)

    print("=" * 70)
    print(f"STAGE 1  Environment  (model={model_name}, base_url={base_url})")
    print("=" * 70)
    try:
        api_key = os.environ[key_env]
    except KeyError:
        print(f"[error]  {key_env} is not set (checked .env and process env).")
        return False
    print(f"[env]    {key_env} present (length {len(api_key)})")

    print()
    print("=" * 70)
    print("STAGE 2  Task specification")
    print("=" * 70)
    print(f"[task]   {task.task_id}  ({task.category}, {task.difficulty})")
    print(f"[task]   description : {task.description}")
    print(f"[task]   user_message: {task.user_message}")
    print(f"[task]   available_tools: {task.context.available_tools}")

    print()
    print("=" * 70)
    print("STAGE 3  Build adapter + mock tool executor")
    print("=" * 70)
    adapter = LangGraphAdapter(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
    )
    print(f"[adapter] {adapter!r}  base_url={base_url}")

    tool_specs = _tool_specs_from_task(task)
    for spec in tool_specs:
        print(f"[tools]  {spec['name']}  params={list(spec['parameters']['properties'])}")
    mock_executor = _make_mock_executor()

    telemetry = TrajectoryTelemetry(task_id="crm_order_fulfilment.001", trial_index=0)

    # NOTE: the schema has no `task.prompt`; the closest field is `user_message`.
    # We prepend the task's system_prompt so the agent has enough context to
    # actually exercise a tool-calling loop.
    task_prompt = f"{task.context.system_prompt}\n\n{task.user_message}"

    print()
    print("=" * 70)
    print("STAGE 4  Run trajectory against live LLM")
    print("=" * 70)
    try:
        final_response = adapter.run(
            task_prompt=task_prompt,
            tools=tool_specs,
            tool_executor=mock_executor,
            telemetry=telemetry,
        )
    except Exception as exc:  # noqa: BLE001 - smoke test: surface any failure and fail loud
        print(f"[FAIL]   adapter.run() raised {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False

    print()
    print("=" * 70)
    print("STAGE 5  Results")
    print("=" * 70)
    print(f"[result] final response:\n{final_response}\n")
    print(f"[result] tool calls made: {len(telemetry.tool_calls)}")
    for i, call in enumerate(telemetry.tool_calls):
        print(f"[result]   ({i}) {call.tool_name}  args={call.arguments}  output={call.output}")
    print(f"[result] wall_clock_time_ms: {telemetry.wall_clock_time_ms:.1f}")
    if telemetry.total_tokens:
        print(
            f"[result] tokens: total={telemetry.total_tokens} "
            f"prompt={telemetry.prompt_tokens} completion={telemetry.completion_tokens}"
        )
    else:
        print("[result] tokens: not reported by endpoint")

    print()
    print("=" * 70)
    print("STAGE 6  Success criteria")
    print("=" * 70)
    checks = {
        "no exception": True,
        "at least one tool call": len(telemetry.tool_calls) >= 1,
        "non-empty final response": bool(final_response and final_response.strip()),
        "wall_clock_time_ms > 0": telemetry.wall_clock_time_ms > 0,
    }
    for label, passed in checks.items():
        print(f"[check]  {'PASS' if passed else 'FAIL'}  {label}")

    if not all(checks.values()):
        print(f"\n[SMOKE TEST FAILED]  (config {config_id}: {model_name})")
        return False
    print(f"\n[SMOKE TEST PASSED]  (config {config_id}: {model_name})")
    return True


def _configs_to_run() -> list[tuple[str, str, str, str]]:
    """(config_id, model_name, base_url, key_env) tuples to smoke-test."""
    override_model = os.environ.get("LLM_MODEL")
    if override_model:
        return [
            (
                "ENV",
                override_model,
                os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
                os.environ.get("LLM_KEY_ENV", DEFAULT_KEY_ENV),
            )
        ]

    pilot = json.loads(PILOT_CONFIG_PATH.read_text(encoding="utf-8"))
    out: list[tuple[str, str, str, str]] = []
    for entry in pilot["configurations"]:
        out.append(
            (
                entry["config_id"],
                entry["model_name"],
                entry.get("base_url", DEFAULT_BASE_URL),
                entry.get("api_key_env", DEFAULT_KEY_ENV),
            )
        )
    return out


def main() -> int:
    print("=" * 70)
    print("Load environment")
    print("=" * 70)
    _load_env()

    task = load_task(str(TASK_PATH))
    configs = _configs_to_run()
    print(f"[plan]   {len(configs)} configuration(s): {[c[0] for c in configs]}")

    results: dict[str, bool] = {}
    for config_id, model_name, base_url, key_env in configs:
        results[f"{config_id} ({model_name})"] = _run_one_config(
            config_id, model_name, base_url, key_env, task
        )

    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)
    for label, passed in results.items():
        print(f"[{'PASS' if passed else 'FAIL'}]  {label}")

    if all(results.values()):
        print("\n[ALL CONFIGS PASSED]")
        return 0
    print("\n[SOME CONFIGS FAILED]")
    return 1


if __name__ == "__main__":
    sys.exit(main())

