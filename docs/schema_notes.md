# AutoBench Task Schema — Reference Notes

## Chapter 4 §4.1 fields (thesis-formalized)

- `task_id`
- `category`
- `prompt`
- `provenance`
- `environment_spec`
- `tools`
- `ground_truth` (with `state_assertions`, `required_actions`, `forbidden_actions`, `invariant_rules`)
- `reliability` (with `k_trials`, `cost_budget_usd`, `latency_budget_ms`, `fault_injection_rules`)

**Mapping to the implemented `tasks/schema.json`.** The thesis names above and
the JSON field names on disk are not all identical; this table is the
authoritative cross-reference so the two don't drift silently:

| Chapter 4 §4.1 name             | Implemented field in `tasks/schema.json`                  |
|----------------------------------|------------------------------------------------------------|
| `prompt`                         | `description` + `user_message`                             |
| `environment_spec`                | `context` (`system_prompt`, `available_tools`, `initial_state`) |
| `tools`                          | `context.available_tools`                                   |
| `ground_truth.state_assertions`   | `ground_truth.expected_final_state`                          |
| `ground_truth.required_actions`   | `ground_truth.required_tool_calls`                           |
| `ground_truth.forbidden_actions`  | currently lives at `reliability.forbidden_actions`, not under `ground_truth` |
| `ground_truth.invariant_rules`    | matches as-is (`rule_id`, `sql_assertion`)                   |
| `reliability.k_trials` / `cost_budget_usd` / `latency_budget_ms` | match as-is; required as of this schema revision |
| `reliability.fault_injection_rules` | matches as-is (`tool_target`, `fault_type`, `trigger_probability`, `retry_after_ms`) |

## Additional optional fields (implementation superset)

- `reliability.hallucination_check` — forbidden claims and required disclosures
- `reliability.policy_rules` — soft rules that count as violations rather than task failures
- `reliability.max_tool_calls` — hard ceiling to terminate runaway trials
- `reliability.expected_cost_range_usd` — soft [min, max] for outlier flagging
- `reliability.expected_latency_seconds` — soft [min, max] for outlier flagging
- `reliability.forbidden_actions` — task-level forbidden tool calls (complements ground_truth.forbidden_actions)

These fields are recorded during evaluation but are not part of the six
primary reliability metrics reported in the thesis; they support future
extensions.

