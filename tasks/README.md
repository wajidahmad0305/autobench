# Tasks

Every task is a single JSON file that validates against [`schema.json`](schema.json).

## Structure

```
tasks/
├── schema.json                      # JSON Schema — the source of truth
├── README.md                        # this file
├── crm_enrichment/
│   ├── task_001.json
│   └── task_002.json
├── invoice_extraction/
│   └── task_001.json
├── lead_qualification/
│   └── task_001.json
├── support_triage/
│   └── task_001.json
└── calendar_coordination/
    └── task_001.json
```

## Task ID convention

Task IDs follow the pattern `<category>.<zero-padded-index>`, e.g. `crm_enrichment.001`.

## Adding a task

1. Copy an existing task in the same category as a template.
2. Assign the next unused `task_id`.
3. Set `provenance.author` to your name and `provenance.created` to today's date.
4. Set `provenance.domain_source` to one of `synthetic`, `real-anonymised`, or `literature-derived`. **Real-anonymised tasks must be scrubbed of every client-identifying detail.**
5. Validate: `python -m jsonschema -i tasks/<category>/task_XXX.json tasks/schema.json`
6. Open a PR titled `[task] <category>.<index> — <short description>`.

## Design principles

- **Ground truth is state, not text.** Wherever possible, `expected_final_state` should describe the state of a mock backend after the task ends, not the agent's exact wording. Text-only tasks are the exception, not the rule.
- **Tool-call requirements are subset matches.** `args_contain` checks that specific keys/values are present in the tool call — the agent may pass additional fields.
- **Policy violations are separate from task failures.** An agent can complete a task successfully while violating policy (e.g. skipping a required disclosure). Both are recorded independently.
- **Hard tasks are hard for a specific reason.** Note it in `provenance.notes` (e.g. "long context", "ambiguous user request", "requires tool-call ordering").
