# AutoBench Thesis Pilot - Summary

- **Total:** 48/120
- **Total tokens consumed:** 198,993 (prompt 139,823, completion 59,170)
- **Wall-clock time span:** 2026-08-29T12:18:43+00:00 -> 2026-08-29T12:50:27+00:00 (0:31:43)
- **Coverage:** 48/120 = 40.0%
- **Outcomes:** PASS 11, FAIL 32, ERROR 5
- _Generated 2026-08-29T13:41:39+00:00_

## Table 1 - Headline leaderboard

| config_id | trials | pass_rate | mean_tsi | mean_sec | mean_sla_compliance | mean_latency_ms | mean_prompt_tokens | mean_completion_tokens | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 48 | 22.9% | 0.256 | 0.837 | 0.186 | 25517 | 2976 | 1291 | 5 |

_pass_rate = (tsi==1 AND sec==1) / trials (ERRORs count as non-pass). mean_* are over completed (non-ERROR) trajectories._

## Table 2 - Per-category pass rate

| category | C1_trials | C1_pass_rate | C2_trials | C2_pass_rate |
| --- | --- | --- | --- | --- |
| crm_order_fulfilment | 15 | 20.0% | 0 | - |
| financial_reconciliation | 15 | 40.0% | 0 | - |
| hr_employee_lifecycle | 3 | 66.7% | 0 | - |
| it_access_provisioning | 15 | 0.0% | 0 | - |

## Table 3 - Failure-mode breakdown (top 10)

| assertion_key | occurrences |
| --- | --- |
| tool_call[post_gl_entry] | 15 |
| tool_call[lookup_company_by_domain] | 9 |
| tool_call[add_okta_group] | 8 |
| state[gl_entries] | 6 |
| state[okta_group_memberships] | 4 |
| state[security_audit_log] | 4 |
| tool_call[get_hubspot_ticket] | 3 |
| state[salesforce_opportunities] | 3 |
| state[hubspot_contacts] | 3 |
| state[pipelines] | 3 |

## Table 4 - Fault recovery

| config_id | fault_type | count | recovered_count | recovery_rate |
| --- | --- | --- | --- | --- |
| C1 | HTTP_409 | 1 | 0 | 0.0% |
| C1 | HTTP_500 | 4 | 0 | 0.0% |

## Table 5 - Coverage matrix

| config | task | trials 0..2 |
| --- | --- | --- |
| C1 | crm_order_fulfilment.001 | x x x |
| C1 | crm_order_fulfilment.002 | x x x |
| C1 | crm_order_fulfilment.003 | x x x |
| C1 | crm_order_fulfilment.004 | x x x |
| C1 | crm_order_fulfilment.005 | x x x |
| C1 | financial_reconciliation.001 | x x x |
| C1 | financial_reconciliation.002 | x x x |
| C1 | financial_reconciliation.003 | x x x |
| C1 | financial_reconciliation.004 | x x x |
| C1 | financial_reconciliation.005 | x x x |
| C1 | it_access_provisioning.001 | x x x |
| C1 | it_access_provisioning.002 | x x x |
| C1 | it_access_provisioning.003 | x x x |
| C1 | it_access_provisioning.004 | x x x |
| C1 | it_access_provisioning.005 | x x x |
| C1 | hr_employee_lifecycle.001 | x x x |
| C1 | hr_employee_lifecycle.002 | . . . |
| C1 | hr_employee_lifecycle.003 | . . . |
| C1 | hr_employee_lifecycle.004 | . . . |
| C1 | hr_employee_lifecycle.005 | . . . |
| C2 | crm_order_fulfilment.001 | . . . |
| C2 | crm_order_fulfilment.002 | . . . |
| C2 | crm_order_fulfilment.003 | . . . |
| C2 | crm_order_fulfilment.004 | . . . |
| C2 | crm_order_fulfilment.005 | . . . |
| C2 | financial_reconciliation.001 | . . . |
| C2 | financial_reconciliation.002 | . . . |
| C2 | financial_reconciliation.003 | . . . |
| C2 | financial_reconciliation.004 | . . . |
| C2 | financial_reconciliation.005 | . . . |
| C2 | it_access_provisioning.001 | . . . |
| C2 | it_access_provisioning.002 | . . . |
| C2 | it_access_provisioning.003 | . . . |
| C2 | it_access_provisioning.004 | . . . |
| C2 | it_access_provisioning.005 | . . . |
| C2 | hr_employee_lifecycle.001 | . . . |
| C2 | hr_employee_lifecycle.002 | . . . |
| C2 | hr_employee_lifecycle.003 | . . . |
| C2 | hr_employee_lifecycle.004 | . . . |
| C2 | hr_employee_lifecycle.005 | . . . |
