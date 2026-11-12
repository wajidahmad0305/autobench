# Reproducing the AutoBench results

This guide covers setup, the test suite, one benchmark trajectory, and the pilot results reported in the thesis. The reported results cover two configurations, C1 and C2.

> **Status: draft, not for publication.** Items marked [CONFIRM] are still unverified. Resolve them before uploading.

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
│   ├── run_pilot.py        # runs the pilot (option: --limit N)
│   ├── analyse_pilot.py    # regenerates analysis/summary.md (takes no options)
│   └── validate_tasks.py   # checks task files against the schema [CONFIRM: flags]
├── tests/                  # pytest suite (39 tests)
├── pyproject.toml
└── experiments/
    ├── thesis_pilot/       # pilot for C1 and C2: config.json, traces/, analysis/summary.md
    └── excluded/           # partial third-configuration run, excluded from all results
```

## 2. Environment

- Python 3.10 (the pilot was run with Python 3.10.7).
- The project is installed from `pyproject.toml`. There is no `requirements.txt`.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:GROQ_API_KEY = "your_key_here"
```

The provider key is read from the `GROQ_API_KEY` environment variable. Never commit it.

## 3. Run the tests

```powershell
pytest
```

Expected: 39 tests collected and passing.

## 4. Run one benchmark trajectory

`run_pilot.py` has no per-task option. To check one trajectory end to end, run the test that executes a single trajectory:

```powershell
pytest tests\test_run_pilot.py::test_single_trajectory_happy_path -v
```

This test does not call the Groq API. [CONFIRM: confirm with the test source]

To run one real trajectory against the provider, run the pilot with a limit of 1. This calls the Groq API and uses tokens:

```powershell
python scripts\run_pilot.py --limit 1
```

## 5. Reproduce the pilot results

The pilot ran 60 tasks, three trials each, for each of two configurations (C1 and C2). Configuration details are in `experiments\thesis_pilot\config.json`.

```powershell
python scripts\run_pilot.py
python scripts\analyse_pilot.py
```

`run_pilot.py` skips trajectories already saved in `experiments\thesis_pilot\traces\`, so a rerun resumes rather than repeats. `analyse_pilot.py` writes `experiments\thesis_pilot\analysis\summary.md`.

Note: `analyse_pilot.py` takes no options. Running it with `--help` runs the analysis and overwrites the summary.

### Expected headline values

Compare your regenerated `summary.md` with these. Provider model outputs are not deterministic, so small differences are expected.

| Item | Expected |
|---|---|
| Completed trajectories | 360 (C1: 180, C2: 180) |
| Outcomes | PASS 132, FAIL 211, ERROR 17 |
| C1 pass rate | 31.7% |
| C2 pass rate | 41.7% |
| Injected faults | 60 (C1: 28, C2: 32) |
| Faults recovered | 0 |
| Total tokens | 1,543,065 |

Pass rate is the share of trials where TSI and SEC both hold. Errors count as non-passes.

### Known differences

- Provider model outputs can change over time, so trajectories will not match the thesis exactly.
- Model names per configuration. The config file lists C1 as openai/gpt-oss-20b and C2 as openai/gpt-oss-120b.


