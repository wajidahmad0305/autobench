# CLAUDE.md — AutoBench Repository Context

You are helping build **AutoBench**, a multi-dimensional reliability benchmark for LLM agents in Business Process Automation (BPA). This file gives you the context you need to be immediately productive on this codebase.

## Project purpose

AutoBench evaluates LLM-based agents across six reliability dimensions that existing benchmarks (τ-bench, WorkBench, AgentBench, SWE-bench) do not cover: Target State Integrity, pass^k Stochastic Repeatability, Fault Recovery, Side-Effect Containment, Effective Cost, and SLA Latency Compliance.

This work is an MS thesis (Riga Nordic University). **Defense: Wed 2 Sept 18:00 Riga; thesis submission the same day. Functional submission cutoff Tue 1 Sept afternoon Pakistan time, before the flight.** Speed and correctness are the priorities; polish is secondary.

## Progress log

- Day 1 complete: 20 task specifications validated (5 per category × 4 categories), schema formalized to match Ch 4 §4.1.
- Day 2 complete: full harness — BaseAgentAdapter interface, LangGraphAdapter for OpenAI-compatible endpoints (both Groq configs verified via smoke test), FaultInjectingEnvironment with 5 fault types, deterministic mock backends for all 4 categories, evaluator computing all 6 reliability metrics. 30 unit tests all passing, mypy --strict clean, ruff clean.
- Next: Day 3 Session 7 — benchmark runner (loops tasks × configs × trials, handles rate limits with exponential backoff and resume-from-checkpoint). Then kick off the 120-trajectory pilot run.
- Tier 3 expansion (Sunday afternoon): entering Tier 3 scope — the full original v1.0 milestones except the NeurIPS submission, which is calendar-blocked. Adding the CrewAI adapter (Session 8), the OpenAI Assistants adapter (Session 9), 40 more tasks (Monday), the C3 `qwen/qwen3.8-27b` config, and an expanded leaderboard rerun on the paid Groq tier.
- Session 8 complete: CrewAI adapter with 3 unit tests, all green.
- Session 9 complete: OpenAI Assistants adapter with 3 unit tests, all green (requires `OPENAI_API_KEY` for real runs; not needed for pilot).
- C3 config added: `qwen/qwen3.8-27b` via Groq. Single-trajectory diagnostic: harness wiring is correct, but qwen still mis-formats tool arguments (`email=True` instead of the address) and loops to max_iterations — the same tool-schema failure that dropped it as C1. Full N=120 pilot (C1+C2, LangGraph) unaffected and complete.

## Current scope (pilot)

- **60 tasks**, 15 per category × 4 categories: `crm_order_fulfilment`, `financial_reconciliation`, `it_access_provisioning`, `hr_employee_lifecycle`. (Supply chain category is deferred to future work.)
- **3 configurations**, all via Groq + LangGraph: C1 `openai/gpt-oss-20b`, C2 `openai/gpt-oss-120b` (a within-family 20B-vs-120B capability comparison), and C3 `qwen/qwen3.8-27b`. (Originally scoped as Gemini 2.5 Flash + Llama 3.3 70B; the Gemini/Llama free tiers were retired. qwen was tried as C1 early on and dropped after it failed to follow tool schemas — truncated ID prefixes, looped to max_iterations — and is being re-introduced as C3 for the Tier 3 rerun, to be re-evaluated on the paid Groq tier. No non-qwen frontier model — Kimi, DeepSeek, Llama-70B+ — is available on the Groq free tier; `groq/compound` rejects function calling. See git history.)
- **K = 3 trials** per (task × configuration) pair. Total: 540 trajectories.
- **Paid Groq Dev tier** — the Tier 3 rerun runs on the paid tier (the free-tier 200K tokens-per-day cap bottlenecked the pilot). Requires `GROQ_API_KEY`; no `GOOGLE_API_KEY` needed.

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
│   │   ├── langgraph_adapter.py  # LangGraph adapter (any OpenAI-compatible endpoint)
│   │   ├── crewai_adapter.py     # CrewAI adapter (same (model, base_url, api_key) contract)
│   │   └── openai_assistants_adapter.py  # OpenAI Assistants adapter (Session 9)
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

## The three configurations

All three hit the same Groq OpenAI-compatible endpoint; only `model` differs.
Each is run through **every** adapter (LangGraph, CrewAI, OpenAI Assistants), so
"configuration" here means the model, not the orchestrator.

```python
# C1 — small:
llm = ChatOpenAI(
    model="openai/gpt-oss-20b",
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    temperature=0.0,
)

# C2 — large:
llm = ChatOpenAI(
    model="openai/gpt-oss-120b",
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    temperature=0.0,
)

# C3 — mid, cross-family:
llm = ChatOpenAI(
    model="qwen/qwen3.8-27b",
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    temperature=0.0,
)
```

Because all three are OpenAI-compatible, a **single** `LangGraphAdapter` class
parameterised on `(model, base_url, api_key)` handles every one; the CrewAI and
OpenAI Assistants adapters follow the same `(model, base_url, api_key)` contract.

## Rate-limit awareness

Free-tier rate limits will bind before financial cost does:
- **Groq free tier**: ~30 RPM and a shared daily token cap across all models. C1, C2, and C3 all draw on the same `GROQ_API_KEY` quota, so the runner must pace all 540 trajectories against one budget. (The Tier 3 rerun moves to the paid Groq Dev tier to clear the 200K tokens-per-day cap that bottlenecked the pilot.)

The runner must implement:
- **Exponential backoff** on HTTP 429 responses from providers (with jitter).
- **Between-trial sleep** to keep RPM under limits.
- **Daily quota tracking** with a `--resume-from` flag on `run_pilot.py` so the runner can be stopped and restarted across days.

## Development priorities (in this order)

1. `schema.py` + `loader.py` + `scripts/validate_tasks.py` — sanity-check task files load.
2. `adapters/base.py` + `adapters/langgraph.py` — get one trajectory running end-to-end against Groq on one task.
3. `environment.py` — mock backends for the four categories.
4. `evaluator.py` — compute TSI, SEC, SLA on a finished trajectory.
5. `runner.py` + `scripts/run_pilot.py` — orchestrate 540 trajectories.
6. `experiments/thesis_pilot/analysis/*.py` — produce the leaderboard tables.

## What NOT to build

Under the deadline, deliberately skip:
- Supply-chain category mock backend — deferred.
- Sophisticated retry policies beyond exponential backoff.
- Web UI / dashboard.
- Anything that isn't on the direct path to running 540 trajectories and computing the six metrics.

## When you're unsure

Prefer the simplest working implementation over an elegant one. There is no time for premature abstraction. When in doubt, **make it run first, refactor never**.

## Meta-note about pair programming

Approach each session as follows: **read the current state of the relevant module → propose the smallest change that makes the next test pass → apply → verify → move on.** Do not rewrite files. Do not add features not on the priority list.
