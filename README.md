# AutoBench

A multi-dimensional reliability benchmark for LLM agents in Business Process Automation (BPA).

AutoBench is the practical component of an MS thesis in Computer Systems at Riga Nordic University (2026–2027). It evaluates LLM agents on realistic back-office workflows and reports six reliability dimensions, not task success alone.

## Status

- Task set: 60 tasks in four categories, 15 per category.
- Evaluation harness: framework-agnostic, with deterministic replay and fault injection.
- Adapters: LangGraph, CrewAI, OpenAI Assistants.
- Pilot: two agent configurations, 360 trajectories. Results are in the thesis, Chapter 5.
- Planned: a fuller leaderboard across more models, and the thesis defence and preprint.

## Why AutoBench

Agents are being deployed for enterprise tasks such as invoice reconciliation, HR lifecycle changes, and IT access provisioning. Existing benchmarks mostly measure whether an agent finishes a task under nominal conditions:

- τ-bench and τ²-bench evaluate customer-service dialogue in retail, airline, and telecom domains.
- WorkBench evaluates office tasks, and reports side effects but not the other dimensions below.
- AgentBench evaluates general reasoning across eight environments.
- SWE-bench evaluates repository issue resolution.

None of these measure, in one framework, the dimensions that decide whether a business-automation agent can run in production. AutoBench measures them together.

## What it measures

Each trajectory is scored on six dimensions:

| Dimension | Definition |
|---|---|
| Target State Integrity (TSI) | 1 if every ground-truth state assertion holds on the final state |
| Side-Effect Containment (SEC) | 1 if there is no global invariant violation and no forbidden action |
| Fault Recovery Rate (Rfault) | Share of faulted trajectories that still reach TSI |
| SLA Latency Compliance | 1 if TSI holds and the run finishes within the task's latency budget |
| Effective Cost (Ceff) | Dollar cost per successful outcome, from token counts |
| Stochastic repeatability (pass^k) | Probability that all k repeated trials of a task succeed |

The **pass rate** counts a trial as passing when TSI and SEC both hold. Formal definitions are in Section 4.5 of the thesis. The method follows Yao et al. (2024) for pass^k.

## Task set

Sixty tasks across four categories, 15 each:

| Category | Example workflow |
|---|---|
| `crm_order_fulfilment` | Process a customer order across CRM and fulfilment systems |
| `financial_reconciliation` | Match vendor invoices to purchase orders and post ledger entries |
| `it_access_provisioning` | Grant or revoke group memberships and write to a security audit log |
| `hr_employee_lifecycle` | Onboarding, offboarding, and compensation updates, with payroll and notifications |

Each task is a JSON file that follows `tasks/schema.json`. Tasks run against in-memory SQLite mock backends, not live enterprise systems.

## Fault injection

The harness can inject HTTP 409, HTTP 429, HTTP 500, timeouts, and schema drift. The pilot used HTTP 409, HTTP 500, and timeouts. HTTP 429 and schema drift are implemented but were not exercised in the pilot.

## Pilot results

| Configuration | Model | Trials | Pass rate |
|---|---|---|---|
| C1 | openai/gpt-oss-20b [CONFIRM] | 180 | 31.7% |
| C2 | openai/gpt-oss-120b [CONFIRM] | 180 | 41.7% |

360 trajectories across the two configurations. No injected fault was recovered from (0 of 60). Per-category results and the full analysis are in Chapter 5 of the thesis.

## Repository layout

```
autobench/
├── README.md
├── LICENSE                 # MIT [CONFIRM]
├── CITATION.cff            # [CONFIRM]
├── pyproject.toml          # [CONFIRM]
├── tasks/
│   ├── schema.json         # task specification
│   └── <category>/         # 60 task files in four categories
├── autobench/              # harness, evaluator, fault injection
│   └── adapters/           # LangGraph, CrewAI, OpenAI Assistants
├── tests/                  # unit tests
├── scripts/                # run_pilot.py, analyse_pilot.py, validate_tasks.py
└── experiments/
    ├── thesis_pilot/       # pilot outputs for C1 and C2: config.json, traces/, analysis/
    └── excluded/           # partial third-configuration run, excluded from all results [CONFIRM: folder created]
```

## Reproducing the results

See [REPRODUCE.md](REPRODUCE.md) for setup, the test suite, a single-task run, and the steps to regenerate the pilot results.

## Limitations

- Mock backends, not live systems.
- Synthetic faults.
- The pilot is descriptive.
- No human baseline.
- A third configuration from another model family was planned as a cross-family diagnostic. It was halted by the provider's daily token limit after 26 of 180 trials and is excluded from all reported results. Its partial traces are kept in `experiments/excluded/`.

## Citation

```bibtex
@misc{ahmad2027autobench,
  title  = {AutoBench: A Multi-Dimensional Reliability Benchmark for LLM Agents
            in Business Process Automation},
  author = {Ahmad, Wajid},
  year   = {2027},
  note   = {MS Thesis, Riga Nordic University. In preparation.}
}
```

See CITATION.cff for a machine-readable version.

## Contact

Wajid Ahmad, MS Computer Systems, Riga Nordic University. GitHub: [@wajidahmad0305](https://github.com/wajidahmad0305)

## Licence

MIT. See LICENSE.
