# AutoBench

**A multi-dimensional reliability benchmark for LLM agents in business process automation.**

> ⚠️ **Status: Under active development.** This is an MS thesis project (Riga Nordic University, 2026–2027). Task set, harness, and leaderboard are being built incrementally through Q4 2026 and Q1 2027. Star or watch to follow along.

---

## Why AutoBench

LLM-based agents are being deployed across enterprise workflows — CRM enrichment, invoice extraction, lead qualification, support triage, calendar coordination — but existing agent benchmarks were not built to evaluate them.

- **τ-bench** and **τ²-bench** focus on customer-service dialogues in retail and airline domains.
- **AgentBench** targets generic reasoning across OS, DB, and web environments.
- **WebArena / SWE-bench** focus on web tasks and code, respectively.

None of these measure the reliability dimensions that block production deployment of business-automation agents: **tool-call correctness, hallucination rate, cost per task, latency, and failure recovery**, evaluated over multiple trials on realistic business tasks with realistic tool APIs.

AutoBench fills that gap.

---

## What AutoBench measures

For every `(agent, task)` pair, run over N trials:

| Dimension | Definition |
|---|---|
| **Task success** | Did the final state match the expected state? (binary) |
| **Tool-call correctness** | Fraction of required tool calls made with correct arguments |
| **Hallucination rate** | Fraction of trials containing forbidden or unsupported claims |
| **Cost per task** | Total USD spent on API calls (tokens in + tokens out) |
| **Latency** | End-to-end wall-clock seconds |
| **Failure recovery** | Given an injected tool error, did the agent recover? |

Reliability is reported using the `pass^k` methodology of [Yao et al. (2024)](https://arxiv.org/abs/2406.12045): the fraction of tasks an agent solves on **all** of k independent trials.

---

## Task categories

Five categories drawn from real business automation workflows. Target: 60–100 tasks total at v1.0.

| Category | Example task |
|---|---|
| `crm_enrichment` | Given an inbound lead's email + name, enrich the CRM record with company, role, and industry |
| `invoice_extraction` | Extract line items, totals, VAT, and payment terms from a PDF invoice into a structured record |
| `lead_qualification` | Score an inbound lead against ICP criteria and route to the correct sales pipeline |
| `support_triage` | Classify an incoming support ticket, apply the correct SLA, and draft an initial response |
| `calendar_coordination` | Schedule a meeting across 3+ attendees given constraints on availability and time zones |

See [`tasks/schema.json`](tasks/schema.json) for the full task specification.

---

## Planned agent configurations

Leaderboard will cover at minimum:

- **Frontier + orchestration:** GPT-5 + LangGraph, Claude Opus 4.7 + native tool use, Gemini 2 + LangGraph
- **Open-weight:** Llama 3.3 70B + LangGraph, Qwen 2.5 72B + LangGraph
- **Simple baseline:** ReAct with any of the above (no framework)
- **Multi-agent:** CrewAI on a frontier model
- **Managed:** OpenAI Assistants API

Each configuration is a **framework adapter** in `autobench/adapters/` — contributions of additional adapters are welcome.

---

## Repository layout

```
autobench/
├── README.md                    # this file
├── LICENSE                      # MIT
├── CITATION.cff                 # academic citation
├── pyproject.toml               # Python project metadata
├── docs/
│   └── PROPOSAL.md              # link to the thesis proposal PDF
├── tasks/
│   ├── schema.json              # task specification schema
│   ├── README.md                # how tasks are structured
│   └── <category>/task_*.json   # individual tasks
└── autobench/                   # Python package (harness)
    └── __init__.py              # placeholder — implementation in W8–11
```

---

## Roadmap

| Milestone | Target date |
|---|---|
| Task schema v0.1 + 5 seed tasks (1 per category) | September 2026 ✓ |
| Full task set (60–100 tasks) | November 2026 |
| Evaluation harness (Python, framework-agnostic) | December 2026 |
| First adapters: LangGraph, CrewAI, OpenAI Assistants | December 2026 |
| Leaderboard v0.1 (frontier models only) | January 2027 |
| Leaderboard v1.0 (frontier + open-weight) | February 2027 |
| arXiv preprint + thesis defence | March 2027 |
| NeurIPS 2027 Datasets & Benchmarks submission | May–June 2027 |

---

## Contributing

The project is at a very early stage. If you're a researcher or practitioner working on agent evaluation, task realism, or specific business-automation domains, please open a discussion — I'd like to talk to you.

- **Task contributions:** open an issue using the "New task proposal" template
- **Adapter contributions:** open a PR against `autobench/adapters/`
- **Domain feedback:** open a discussion — especially if you deploy agents in production

---

## Citation

If you use AutoBench in your work, please cite:

```bibtex
@misc{ahmad2027autobench,
  title  = {AutoBench: A Multi-Dimensional Reliability Benchmark for LLM Agents
            in Business Process Automation},
  author = {Ahmad, Wajid},
  year   = {2027},
  note   = {MS Thesis, Riga Nordic University. In preparation.}
}
```

See [`CITATION.cff`](CITATION.cff) for a machine-readable version.

---

## Contact

**Wajid Ahmad** — MS Computer Systems, Riga Nordic University
GitHub: [@wajidahmad0305](https://github.com/wajidahmad0305)

---

## License

MIT — see [`LICENSE`](LICENSE).

