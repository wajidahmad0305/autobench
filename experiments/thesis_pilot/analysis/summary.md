# AutoBench Thesis Pilot - Summary

- **Total:** 111/120
- **Total tokens consumed:** 453,313 (prompt 344,789, completion 108,524)
- **Wall-clock time span:** 2026-08-29T12:18:43+00:00 -> 2026-08-30T10:00:54+00:00 (21:42:10)
- **Coverage:** 111/120 = 92.5%
- **Outcomes:** PASS 23, FAIL 79, ERROR 9
- _Generated 2026-08-30T10:13:10+00:00_

## Table 1 - Headline leaderboard

| config_id | trials | pass_rate | mean_tsi | mean_sec | mean_sla_compliance | mean_latency_ms | mean_prompt_tokens | mean_completion_tokens | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 60 | 18.3% | 0.216 | 0.804 | 0.157 | 23606 | 2881 | 1203 | 9 |
| C2 | 51 | 23.5% | 0.235 | 0.824 | 0.216 | 25571 | 3490 | 809 | 0 |

_pass_rate = (tsi==1 AND sec==1) / trials (ERRORs count as non-pass). mean_* are over completed (non-ERROR) trajectories._

## Table 2 - Per-category pass rate

| category | C1_trials | C1_pass_rate | C2_trials | C2_pass_rate |
| --- | --- | --- | --- | --- |
| crm_order_fulfilment | 15 | 20.0% | 15 | 20.0% |
| financial_reconciliation | 15 | 40.0% | 15 | 40.0% |
| hr_employee_lifecycle | 15 | 13.3% | 6 | 50.0% |
| it_access_provisioning | 15 | 0.0% | 15 | 0.0% |

## Table 3 - Failure-mode breakdown (top 10)

| assertion_key | occurrences |
| --- | --- |
| tool_call[post_gl_entry] | 30 |
| tool_call[lookup_company_by_domain] | 18 |
| tool_call[post_bonus_to_payroll] | 15 |
| tool_call[update_compensation_history] | 15 |
| tool_call[send_bonus_notification_email] | 15 |
| tool_call[add_okta_group] | 14 |
| state[gl_entries] | 12 |
| tool_call[log_security_audit_event] | 11 |
| state[security_audit_log] | 10 |
| state[okta_group_memberships] | 7 |

## Table 4 - Fault recovery

| config_id | fault_type | count | recovered_count | recovery_rate |
| --- | --- | --- | --- | --- |
| C1 | HTTP_409 | 1 | 0 | 0.0% |
| C1 | HTTP_500 | 4 | 0 | 0.0% |
| C2 | HTTP_409 | 1 | 0 | 0.0% |
| C2 | HTTP_500 | 6 | 0 | 0.0% |

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
| C1 | hr_employee_lifecycle.002 | x x x |
| C1 | hr_employee_lifecycle.003 | x x x |
| C1 | hr_employee_lifecycle.004 | x x x |
| C1 | hr_employee_lifecycle.005 | x x x |
| C2 | crm_order_fulfilment.001 | x x x |
| C2 | crm_order_fulfilment.002 | x x x |
| C2 | crm_order_fulfilment.003 | x x x |
| C2 | crm_order_fulfilment.004 | x x x |
| C2 | crm_order_fulfilment.005 | x x x |
| C2 | financial_reconciliation.001 | x x x |
| C2 | financial_reconciliation.002 | x x x |
| C2 | financial_reconciliation.003 | x x x |
| C2 | financial_reconciliation.004 | x x x |
| C2 | financial_reconciliation.005 | x x x |
| C2 | it_access_provisioning.001 | x x x |
| C2 | it_access_provisioning.002 | x x x |
| C2 | it_access_provisioning.003 | x x x |
| C2 | it_access_provisioning.004 | x x x |
| C2 | it_access_provisioning.005 | x x x |
| C2 | hr_employee_lifecycle.001 | x x x |
| C2 | hr_employee_lifecycle.002 | x x x |
| C2 | hr_employee_lifecycle.003 | . . . |
| C2 | hr_employee_lifecycle.004 | . . . |
| C2 | hr_employee_lifecycle.005 | . . . |
