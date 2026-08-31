# C3 Diagnostic — `qwen/qwen3.8-27b` via Groq

Companion to `summary.md`. The expanded v1.0 pilot was scoped for three
configurations; C1 (`openai/gpt-oss-20b`) and C2 (`openai/gpt-oss-120b`)
completed at full coverage. C3 did not, for the reasons recorded here.

## 1. Coverage

| | value |
| --- | --- |
| Trajectories completed | **26 / 180 (14%)** |
| Categories touched | `crm_order_fulfilment` only (tasks 001–009) |
| Categories with zero data | `financial_reconciliation`, `it_access_provisioning`, `hr_employee_lifecycle` |
| Outcomes | 3 PASS · 17 FAIL · 6 ERROR |
| ERROR breakdown | 4× `killed: timeout` (tasks 003, 006), 2× `killed: token_cap` (task 009) |

C3 is therefore **not reported as a leaderboard row** in the thesis. The
26 trajectories are retained as trace artifacts and characterised
qualitatively below.

## 2. Failure mode — argument-type coercion on structured tool calls

qwen3.8-27b produces JSON tool-call arguments with the wrong primitive
type: **booleans (and bare tokens) substituted for the string values the
tool schema requires.** Observed concretely in the traces:

- a notification tool invoked with `email=True` instead of
  `email="<recipient address>"` — the model emits the *presence* of the
  field as a boolean rather than its value;
- ID-bearing arguments (`order_id`, `ticket_id`) sent as truncated or
  malformed tokens, matching the same tool-schema failure seen when qwen
  was trialled as C1 early in the project (see `CLAUDE.md` progress log
  and git history).

The tool layer rejects the malformed call, the rejection is fed back, and
qwen **re-issues the same malformed call** rather than correcting the
type. The trajectory then loops until one of the harness kill-switches
trips (`MAX_TRAJECTORY_SECONDS = 90`, `MAX_TRAJECTORY_TOKENS = 15_000`).

### Bimodal behaviour

C3 trajectories split cleanly into two populations:

| population | tool calls | tokens | example |
| --- | --- | --- | --- |
| schema followed on first try | ~4 | ~1,700 | task 007 (all 3 trials → PASS) |
| coercion loop | 22–44 | 12,000–15,352 | tasks 003, 009 |

There is almost nothing in between. When qwen gets the argument types
right it completes the task cleanly; when it does not, it never recovers
within budget.

## 3. Token-cost pattern

| config | mean tokens / trajectory |
| --- | --- |
| C1 | 4,160 |
| C2 | 4,412 |
| C3 | **7,049 (~1.7× C1/C2)** |

The excess is entirely the coercion loops: looping trajectories hit the
15k token cap, non-looping ones are *cheaper* than C1/C2. Mean latency
tells the same story — C3 mean 33,945 ms vs ~3,500 ms for C1/C2, driven
by trajectories running to the 90 s wall-clock kill.

## 4. Infrastructure limit — Groq per-model daily quota

The run halted mid-C3 at trajectory 386/540 on:

```
Error code: 429 — Rate limit reached for model `qwen/qwen3.8-27b`
service tier `on_demand` on tokens per day (TPD):
Limit 200000, Used 198927, Requested 1250.
```

Findings:

- Groq enforces the **200,000 tokens-per-day cap per model** on this
  account's serving tier for `qwen/qwen3.8-27b`; the `openai/gpt-oss-*`
  models were not similarly constrained and completed in full.
- The runner detected the TPD 429 (distinct from a transient per-minute
  429), stopped cleanly, and preserved all completed traces — resume from
  checkpoint is intact.
- Because the coercion loops inflate C3 token cost ~1.7×, the remaining
  ~154 C3 trajectories would need on the order of **1.0–1.1 M qwen tokens
  ≈ 5+ daily quota resets**. This does not fit the thesis submission
  window.

## 5. Conclusion

`qwen/qwen3.8-27b` as served on Groq's current `on_demand` tier is
**unsuitable for structured tool-calling BPA agents**: it exhibits
systematic argument-type coercion (booleans for strings) that induces
non-recoverable tool-call retry loops, and its per-model daily token
quota cannot sustain a 180-trajectory run.

The within-family capability comparison (C1 vs C2, `gpt-oss-20b` vs
`gpt-oss-120b`, 360 trajectories at full coverage) stands as the pilot's
primary leaderboard. **Cross-family evaluation is deferred to future
work**, pending either a different qwen serving path (dedicated endpoint,
higher quota, or a non-preview build) or a different open-weight,
non-`openai`-family model with reliable function-calling support.
