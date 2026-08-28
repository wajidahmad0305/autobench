# CLAUDE.md — AutoBench Repository Context

You are helping build **AutoBench**, a multi-dimensional reliability benchmark for LLM agents in Business Process Automation (BPA). This file gives you the context you need to be immediately productive on this codebase.

## Project purpose

AutoBench evaluates LLM-based agents across six reliability dimensions that existing benchmarks (τ-bench, WorkBench, AgentBench, SWE-bench) do not cover: Target State Integrity, pass^k Stochastic Repeatability, Fault Recovery, Side-Effect Containment, Effective Cost, and SLA Latency Compliance.

This work is an MS thesis (Riga Nordic University) with a **hard submission deadline in 7 days**. Speed and correctness are the priorities; polish is secondary.

## Current scope (pilot)

- **20 tasks**, 5 per category × 4 categories: `crm_order_fulfilment`, `financial_reconciliation`, `it_access_provisioning`, `hr_employee_lifecycle`. (Supply chain category is deferred to future work.)
- **2 configurations**, both via Groq + LangGraph: `qwen/qwen3.8-27b` (frontier-tier) and `openai/gpt-oss-120b` (open-weight). (Originally scoped as Gemini 2.5 Flash + Llama 3.3 70B; both were retired from their free tiers before the pilot ran — see git history.)
- **K = 3 trials** per (task × configuration) pair. Total: 120 trajectories.
- **Zero API cost** — Groq free tier only. Requires `GROQ_API_KEY`; no `GOOGLE_API_KEY` needed.

## Repository layout

```
autobench/
├── README.md                  # project landing page
├── LICENSE                    # MIT
├── pyproject.toml             # dependencies, package config
├── .env.example               # template for API keys
├── tasks/
│   ├── schema.json            # AUTHORITATIVE task JSON Schema
│   ├── README.md              # task authoring guide
│   ├── crm_order_fulfilment/task_*.json
│   ├── financial_reconciliation/task_*.json
│   ├── it_access_provisioning/task_*.json
│   └── hr_employee_lifecycle/task_*.json
├── autobench/                 # main Python package
│   ├── __init__.py
│   ├── schema.py              # Pydantic models mirroring schema.json
│   ├── loader.py              # load + validate task files
│   ├── adapters/
│   │   ├── base.py            # BaseAgentAdapter, ToolCallRecord, TrajectoryTelemetry
│   │   └── langgraph.py       # LangGraph adapter (works with any OpenAI-compatible endpoint)
│   ├── environment.py         # FaultInjectingEnvironment + mock backends
│   ├── evaluator.py           # evaluate_trajectory function
│   └── runner.py              # BenchmarkRunner (loops tasks × configs × trials)
├── experiments/thesis_pilot/
│   ├── config.json            # experiment definition (master_seed, model IDs, etc.)
│   ├── traces/                # JSON telemetry per trajectory (gitignored on write)
│   └── analysis/
│       ├── leaderboard.py     # produces §5.2 tables
│       ├── failure_modes.py   # produces §5.3 taxonomy
│       └── latency.py         # produces §5.4 analysis
└── scripts/
    ├── run_pilot.py           # entry point: runs the full pilot experiment
    └── validate_tasks.py      # sanity-checks all task JSON files
```

## Coding conventions

- **Python 3.10+ with strict typing** (uses `from __future__ import annotations` so PEP 604 `X | None` syntax works via deferred evaluation). Every new .py file MUST begin with `from __future__ import annotations` as its first non-comment line.
- **Pydantic v2** for schema validation and dataclasses. Task specs load via `TaskSpec.model_validate(json.loads(...))`.
- **`ruff` + `mypy --strict`** — assume both run on save.
- **No hidden state.** Every function that mutates state takes it as an explicit parameter and returns it. Global mutable state is forbidden.
- **Deterministic-first.** Any randomness must be seeded from `(task_id, trial_index, master_seed)`. Never call `random.random()` without a seeded generator.
- **SQLite in-memory** for mock backends (`sqlite3.connect(":memory:")`), never disk-backed.
- **API keys via `.env`** — read with `python-dotenv`, never hardcoded.
- **Logging via `structlog`** at INFO level for run progress, DEBUG for tool-call detail.

## The two configurations

Both use LangGraph for orchestration and the same Groq OpenAI-compatible endpoint;
only `model` differs.

```python
# C1 — frontier-tier:
llm = ChatOpenAI(
    model="qwen/qwen3.8-27b",
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    temperature=0.0,
)

# C2 — open-weight:
llm = ChatOpenAI(
    model="openai/gpt-oss-120b",
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    temperature=0.0,
)
```

Because both are OpenAI-compatible, a **single** `LangGraphAdapter` class parameterised on `(model, base_url, api_key)` handles both.

## Rate-limit awareness

Free-tier rate limits will bind before financial cost does:
- **Groq free tier**: ~30 RPM and a shared daily token cap across both models. Both C1 and C2 draw on the same `GROQ_API_KEY` quota, so the runner must pace all 120 trajectories against one budget.

The runner must implement:
- **Exponential backoff** on HTTP 429 responses from providers (with jitter).
- **Between-trial sleep** to keep RPM under limits.
- **Daily quota tracking** with a `--resume-from` flag on `run_pilot.py` so the runner can be stopped and restarted across days.

## Development priorities (in this order)

1. `schema.py` + `loader.py` + `scripts/validate_tasks.py` — sanity-check task files load.
2. `adapters/base.py` + `adapters/langgraph.py` — get one trajectory running end-to-end against Groq on one task.
3. `environment.py` — mock backends for the four categories.
4. `evaluator.py` — compute TSI, SEC, SLA on a finished trajectory.
5. `runner.py` + `scripts/run_pilot.py` — orchestrate 120 trajectories.
6. `experiments/thesis_pilot/analysis/*.py` — produce the leaderboard tables.

## What NOT to build

Under the 7-day deadline, deliberately skip:
- CrewAI adapter, OpenAI Assistants adapter — deferred to future work.
- Supply-chain category mock backend — deferred.
- Sophisticated retry policies beyond exponential backoff.
- Web UI / dashboard.
- Anything that isn't on the direct path to running 120 trajectories and computing the six metrics.

## When you're unsure

Prefer the simplest working implementation over an elegant one. There is no time for premature abstraction. When in doubt, **make it run first, refactor never**.

## Meta-note about pair programming

Approach each session as follows: **read the current state of the relevant module → propose the smallest change that makes the next test pass → apply → verify → move on.** Do not rewrite files. Do not add features not on the priority list.
