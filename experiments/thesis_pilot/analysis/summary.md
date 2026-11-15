# AutoBench Thesis Pilot - Summary

- **Total:** 360/360
- **Total tokens consumed:** 1,543,065 (prompt 1,204,890, completion 338,175)
- **Wall-clock time span:** 2026-08-31T05:42:06+00:00 -> 2026-08-31T06:15:32+00:00 (0:33:26)
- **Coverage:** 360/360 = 100.0%
- **Outcomes:** PASS 132, FAIL 211, ERROR 17
- _Generated 2026-11-15T20:54:14+00:00_

## Table 1 - Headline leaderboard

| config_id | trials | pass_rate | mean_tsi | mean_sec | mean_sla_compliance | mean_latency_ms | mean_prompt_tokens | mean_completion_tokens | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 180 | 31.7% | 0.350 | 0.908 | 0.350 | 3452 | 3141 | 1135 | 17 |
| C2 | 180 | 41.7% | 0.417 | 0.933 | 0.417 | 3699 | 3657 | 755 | 0 |

_pass_rate = (tsi==1 AND sec==1) / trials (ERRORs count as non-pass). mean_* are over completed (non-ERROR) trajectories._

## Table 2 - Per-category pass rate

| category | C1_trials | C1_pass_rate | C2_trials | C2_pass_rate |
| --- | --- | --- | --- | --- |
| crm_order_fulfilment | 45 | 35.6% | 45 | 40.0% |
| financial_reconciliation | 45 | 44.4% | 45 | 60.0% |
| hr_employee_lifecycle | 45 | 33.3% | 45 | 46.7% |
| it_access_provisioning | 45 | 13.3% | 45 | 20.0% |

## Table 3 - Failure-mode breakdown (top 10)

| assertion_key | occurrences |
| --- | --- |
| tool_call[post_gl_entry] | 51 |
| state[security_audit_log] | 45 |
| tool_call[log_security_audit_event] | 45 |
| tool_call[update_compensation_history] | 36 |
| tool_call[send_bonus_notification_email] | 36 |
| tool_call[post_bonus_to_payroll] | 23 |
| tool_call[get_hubspot_ticket] | 21 |
| state[gl_entries] | 21 |
| tool_call[add_okta_group] | 19 |
| tool_call[lookup_company_by_domain] | 18 |

## Table 4 - Fault recovery

| config_id | fault_type | count | recovered_count | recovery_rate |
| --- | --- | --- | --- | --- |
| C1 | HTTP_409 | 1 | 0 | 0.0% |
| C1 | HTTP_500 | 17 | 0 | 0.0% |
| C1 | TIMEOUT | 10 | 0 | 0.0% |
| C2 | HTTP_500 | 18 | 0 | 0.0% |
| C2 | TIMEOUT | 14 | 0 | 0.0% |

## Table 5 - Coverage matrix

| config | task | trials 0..2 |
| --- | --- | --- |
| C1 | crm_order_fulfilment.001 | x x x |
| C1 | crm_order_fulfilment.002 | x x x |
| C1 | crm_order_fulfilment.003 | x x x |
| C1 | crm_order_fulfilment.004 | x x x |
| C1 | crm_order_fulfilment.005 | x x x |
| C1 | crm_order_fulfilment.006 | x x x |
| C1 | crm_order_fulfilment.007 | x x x |
| C1 | crm_order_fulfilment.008 | x x x |
| C1 | crm_order_fulfilment.009 | x x x |
| C1 | crm_order_fulfilment.010 | x x x |
| C1 | crm_order_fulfilment.011 | x x x |
| C1 | crm_order_fulfilment.012 | x x x |
| C1 | crm_order_fulfilment.013 | x x x |
| C1 | crm_order_fulfilment.014 | x x x |
| C1 | crm_order_fulfilment.015 | x x x |
| C1 | financial_reconciliation.001 | x x x |
| C1 | financial_reconciliation.002 | x x x |
| C1 | financial_reconciliation.003 | x x x |
| C1 | financial_reconciliation.004 | x x x |
| C1 | financial_reconciliation.005 | x x x |
| C1 | financial_reconciliation.006 | x x x |
| C1 | financial_reconciliation.007 | x x x |
| C1 | financial_reconciliation.008 | x x x |
| C1 | financial_reconciliation.009 | x x x |
| C1 | financial_reconciliation.010 | x x x |
| C1 | financial_reconciliation.011 | x x x |
| C1 | financial_reconciliation.012 | x x x |
| C1 | financial_reconciliation.013 | x x x |
| C1 | financial_reconciliation.014 | x x x |
| C1 | financial_reconciliation.015 | x x x |
| C1 | it_access_provisioning.001 | x x x |
| C1 | it_access_provisioning.002 | x x x |
| C1 | it_access_provisioning.003 | x x x |
| C1 | it_access_provisioning.004 | x x x |
| C1 | it_access_provisioning.005 | x x x |
| C1 | it_access_provisioning.006 | x x x |
| C1 | it_access_provisioning.007 | x x x |
| C1 | it_access_provisioning.008 | x x x |
| C1 | it_access_provisioning.009 | x x x |
| C1 | it_access_provisioning.010 | x x x |
| C1 | it_access_provisioning.011 | x x x |
| C1 | it_access_provisioning.012 | x x x |
| C1 | it_access_provisioning.013 | x x x |
| C1 | it_access_provisioning.014 | x x x |
| C1 | it_access_provisioning.015 | x x x |
| C1 | hr_employee_lifecycle.001 | x x x |
| C1 | hr_employee_lifecycle.002 | x x x |
| C1 | hr_employee_lifecycle.003 | x x x |
| C1 | hr_employee_lifecycle.004 | x x x |
| C1 | hr_employee_lifecycle.005 | x x x |
| C1 | hr_employee_lifecycle.006 | x x x |
| C1 | hr_employee_lifecycle.007 | x x x |
| C1 | hr_employee_lifecycle.008 | x x x |
| C1 | hr_employee_lifecycle.009 | x x x |
| C1 | hr_employee_lifecycle.010 | x x x |
| C1 | hr_employee_lifecycle.011 | x x x |
| C1 | hr_employee_lifecycle.012 | x x x |
| C1 | hr_employee_lifecycle.013 | x x x |
| C1 | hr_employee_lifecycle.014 | x x x |
| C1 | hr_employee_lifecycle.015 | x x x |
| C2 | crm_order_fulfilment.001 | x x x |
| C2 | crm_order_fulfilment.002 | x x x |
| C2 | crm_order_fulfilment.003 | x x x |
| C2 | crm_order_fulfilment.004 | x x x |
| C2 | crm_order_fulfilment.005 | x x x |
| C2 | crm_order_fulfilment.006 | x x x |
| C2 | crm_order_fulfilment.007 | x x x |
| C2 | crm_order_fulfilment.008 | x x x |
| C2 | crm_order_fulfilment.009 | x x x |
| C2 | crm_order_fulfilment.010 | x x x |
| C2 | crm_order_fulfilment.011 | x x x |
| C2 | crm_order_fulfilment.012 | x x x |
| C2 | crm_order_fulfilment.013 | x x x |
| C2 | crm_order_fulfilment.014 | x x x |
| C2 | crm_order_fulfilment.015 | x x x |
| C2 | financial_reconciliation.001 | x x x |
| C2 | financial_reconciliation.002 | x x x |
| C2 | financial_reconciliation.003 | x x x |
| C2 | financial_reconciliation.004 | x x x |
| C2 | financial_reconciliation.005 | x x x |
| C2 | financial_reconciliation.006 | x x x |
| C2 | financial_reconciliation.007 | x x x |
| C2 | financial_reconciliation.008 | x x x |
| C2 | financial_reconciliation.009 | x x x |
| C2 | financial_reconciliation.010 | x x x |
| C2 | financial_reconciliation.011 | x x x |
| C2 | financial_reconciliation.012 | x x x |
| C2 | financial_reconciliation.013 | x x x |
| C2 | financial_reconciliation.014 | x x x |
| C2 | financial_reconciliation.015 | x x x |
| C2 | it_access_provisioning.001 | x x x |
| C2 | it_access_provisioning.002 | x x x |
| C2 | it_access_provisioning.003 | x x x |
| C2 | it_access_provisioning.004 | x x x |
| C2 | it_access_provisioning.005 | x x x |
| C2 | it_access_provisioning.006 | x x x |
| C2 | it_access_provisioning.007 | x x x |
| C2 | it_access_provisioning.008 | x x x |
| C2 | it_access_provisioning.009 | x x x |
| C2 | it_access_provisioning.010 | x x x |
| C2 | it_access_provisioning.011 | x x x |
| C2 | it_access_provisioning.012 | x x x |
| C2 | it_access_provisioning.013 | x x x |
| C2 | it_access_provisioning.014 | x x x |
| C2 | it_access_provisioning.015 | x x x |
| C2 | hr_employee_lifecycle.001 | x x x |
| C2 | hr_employee_lifecycle.002 | x x x |
| C2 | hr_employee_lifecycle.003 | x x x |
| C2 | hr_employee_lifecycle.004 | x x x |
| C2 | hr_employee_lifecycle.005 | x x x |
| C2 | hr_employee_lifecycle.006 | x x x |
| C2 | hr_employee_lifecycle.007 | x x x |
| C2 | hr_employee_lifecycle.008 | x x x |
| C2 | hr_employee_lifecycle.009 | x x x |
| C2 | hr_employee_lifecycle.010 | x x x |
| C2 | hr_employee_lifecycle.011 | x x x |
| C2 | hr_employee_lifecycle.012 | x x x |
| C2 | hr_employee_lifecycle.013 | x x x |
| C2 | hr_employee_lifecycle.014 | x x x |
| C2 | hr_employee_lifecycle.015 | x x x |

## Table 6 - pass^1 and pass^3 (unbiased estimator)

| config_id | pass^1 | pass^3 | gap_pp | gap_at_least_10pp |
| --- | --- | --- | --- | --- |
| C1 | 31.7% | 30.0% | 1.7 | no |
| C2 | 41.7% | 41.7% | 0.0 | no |

## Hypothesis checks (H1-H4)

- H1 (each configuration pass rate below 50%): supported
- H2 (pooled fault recovery below 50%): supported (0 of 60 faulted trajectories recovered)
- H3 (IT access provisioning lowest in each configuration): supported
- H4 (pass^3 at least 10 points below pass^1 for at least one configuration): not supported
