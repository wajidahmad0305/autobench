# Reproducing the AutoBench results

This guide covers setup, the test suite, one benchmark task, and the pilot results reported in the thesis. The reported results cover two configurations, C1 and C2.

> **Status: draft, not for publication.** Script and test file names were checked against the local project listing. Command flags, the test count, the model IDs, and the root-level files (README, pyproject, LICENSE, requirements) are not yet verified. Every [CONFIRM] must be resolved before this file is uploaded.

## 1. Repository layout (relevant parts)

```
autobench/
├── autobench/              # harness: environment, evaluator, schema, backends, adapters
│   ├── adapters/           # LangGraph, CrewAI, OpenAI Assistants
│   └── backends/           # four mock enterprise backends
├── tasks/
│   ├── crm_order_fulfilment/           # 15 tasks
│   ├── financial_reconciliation/       # 15 tasks
│   ├── hr_employee_lifecycle/          # 15 tasks
│   ├── it_access_provisioning/         # 15 tasks
│   ├── schema.json
│   └── legacy_seed/                    # earlier draft tasks, not used in the pilot [CONFIRM: remove or label]
├── scripts/
│   ├── run_pilot.py        # runs the pilot
│   ├── analyse_pilot.py    # regenerates the analysis
│   └── validate_tasks.py   # checks task files against the schema
├── tests/                  # pytest suite
└── experiments/
    ├── thesis_pilot/       # pilot for C1 and C2: config.json, traces/, analysis/summary.md
    └── excluded/           # partial third-configuration run, excluded from all results [CONFIRM: folder created and not read by analyse_pilot.py]
```

## 2. Environment

- Python 3.10 (the pilot was run with Python 3.10.7).
- Create and activate a virtual environment, then install the project. [CONFIRM: install command, e.g. `pip install -e .` or `pip install -r requirements.txt`]
- Set your provider key as an environment variable. Never commit it. [CONFIRM: variable name]

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install [CONFIRM]
$env:GROQ_API_KEY = "your_key_here"   # [CONFIRM variable name]
```

## 3. Run the tests

```bash
pytest
```

Expected: all tests in `tests/` pass. [CONFIRM: number of tests]

Optional checks:

```bash
python scripts/validate_tasks.py      # every task file matches tasks/schema.json
python scripts/verify_invariant_rules.py
```

## 4. Run one benchmark task

```bash
python scripts/run_pilot.py --help    # [CONFIRM: flags for a single task and a single trial]
```

Expected output: the trajectory, the six metric values for that trial, and a pass or fail verdict. [CONFIRM: where the output is written]

To see fault injection, enable a fault rule for the same task. [CONFIRM: flag or config key]

## 5. Reproduce the pilot results

The pilot ran 60 tasks, three trials each, for each of two configurations (C1 and C2).

```bash
python scripts/run_pilot.py --help    # [CONFIRM: config flag for C1 and C2]
python scripts/analyse_pilot.py --help  # [CONFIRM: input and output paths]
```

The analysis writes `experiments/thesis_pilot/analysis/summary.md`. [CONFIRM output path]

### Expected headline values

Compare your regenerated `summary.md` with these. Small differences are expected because provider models are not deterministic.

| Item | Expected |
|---|---|
| Completed trajectories | 360 (C1: 180, C2: 180) |
| C1 pass rate | 31.7% |
| C2 pass rate | 41.7% |
| Injected faults | 60 (C1: 28, C2: 32) |
| Faults recovered | 0 |

Pass rate is the share of trials where TSI and SEC both hold. Errors count as non-passes.

### Known differences

- Provider model outputs can change over time, so trajectories will not match the thesis exactly.
- [CONFIRM] Model names per configuration. Check `experiments/thesis_pilot/config.json` against the final run. An older config lists C1 as qwen, but the final pilot lists C1 as openai/gpt-oss-20b.

## 6. Record your run

Note the commit hash, the date, and the provider model IDs you used.
