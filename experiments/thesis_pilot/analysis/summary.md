# AutoBench Thesis Pilot - Summary

- **Total:** 386/540
- **Total tokens consumed:** 1,726,327 (prompt 1,375,620, completion 350,707)
- **Wall-clock time span:** 2026-08-31T05:42:06+00:00 -> 2026-08-31T06:39:21+00:00 (0:57:15)
- **Coverage:** 386/540 = 71.5%
- **Outcomes:** PASS 135, FAIL 228, ERROR 23
- _Generated 2026-08-31T06:53:26+00:00_

## Table 1 - Headline leaderboard

| config_id | trials | pass_rate | mean_tsi | mean_sec | mean_sla_compliance | mean_latency_ms | mean_prompt_tokens | mean_completion_tokens | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 180 | 31.7% | 0.350 | 0.908 | 0.350 | 3452 | 3141 | 1135 | 17 |
| C2 | 180 | 41.7% | 0.417 | 0.933 | 0.417 | 3699 | 3657 | 755 | 0 |
| C3 | 26 | 11.5% | 0.150 | 1.000 | 0.150 | 33945 | 4678 | 386 | 6 |

_pass_rate = (tsi==1 AND sec==1) / trials (ERRORs count as non-pass). mean_* are over completed (non-ERROR) trajectories._

## Table 2 - Per-category pass rate

| category | C1_trials | C1_pass_rate | C2_trials | C2_pass_rate | C3_trials | C3_pass_rate |
| --- | --- | --- | --- | --- | --- | --- |
| crm_order_fulfilment | 45 | 35.6% | 45 | 40.0% | 26 | 11.5% |
| financial_reconciliation | 45 | 44.4% | 45 | 60.0% | 0 | - |
| hr_employee_lifecycle | 45 | 33.3% | 45 | 46.7% | 0 | - |
| it_access_provisioning | 45 | 13.3% | 45 | 20.0% | 0 | - |

## Table 3 - Failure-mode breakdown (top 10)

| assertion_key | occurrences |
| --- | --- |
| tool_call[post_gl_entry] | 51 |
| state[security_audit_log] | 45 |
| tool_call[log_security_audit_event] | 45 |
| tool_call[update_compensation_history] | 36 |
| tool_call[send_bonus_notification_email] | 36 |
| tool_call[get_hubspot_ticket] | 27 |
| tool_call[lookup_company_by_domain] | 27 |
| state[hubspot_tickets] | 26 |
| tool_call[update_hubspot_ticket_status] | 26 |
| tool_call[post_bonus_to_payroll] | 23 |

## Table 4 - Fault recovery

| config_id | fault_type | count | recovered_count | recovery_rate |
| --- | --- | --- | --- | --- |
| C1 | HTTP_409 | 1 | 0 | 0.0% |
| C1 | HTTP_500 | 17 | 0 | 0.0% |
| C1 | TIMEOUT | 10 | 0 | 0.0% |
| C2 | HTTP_500 | 18 | 0 | 0.0% |
| C2 | TIMEOUT | 14 | 0 | 0.0% |
| C3 | HTTP_500 | 3 | 0 | 0.0% |

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
| C3 | crm_order_fulfilment.001 | x x x |
| C3 | crm_order_fulfilment.002 | x x x |
| C3 | crm_order_fulfilment.003 | x x x |
| C3 | crm_order_fulfilment.004 | x x x |
| C3 | crm_order_fulfilment.005 | x x x |
| C3 | crm_order_fulfilment.006 | x x x |
| C3 | crm_order_fulfilment.007 | x x x |
| C3 | crm_order_fulfilment.008 | x x x |
| C3 | crm_order_fulfilment.009 | x x . |
| C3 | crm_order_fulfilment.010 | . . . |
| C3 | crm_order_fulfilment.011 | . . . |
| C3 | crm_order_fulfilment.012 | . . . |
| C3 | crm_order_fulfilment.013 | . . . |
| C3 | crm_order_fulfilment.014 | . . . |
| C3 | crm_order_fulfilment.015 | . . . |
| C3 | financial_reconciliation.001 | . . . |
| C3 | financial_reconciliation.002 | . . . |
| C3 | financial_reconciliation.003 | . . . |
| C3 | financial_reconciliation.004 | . . . |
| C3 | financial_reconciliation.005 | . . . |
| C3 | financial_reconciliation.006 | . . . |
| C3 | financial_reconciliation.007 | . . . |
| C3 | financial_reconciliation.008 | . . . |
| C3 | financial_reconciliation.009 | . . . |
| C3 | financial_reconciliation.010 | . . . |
| C3 | financial_reconciliation.011 | . . . |
| C3 | financial_reconciliation.012 | . . . |
| C3 | financial_reconciliation.013 | . . . |
| C3 | financial_reconciliation.014 | . . . |
| C3 | financial_reconciliation.015 | . . . |
| C3 | it_access_provisioning.001 | . . . |
| C3 | it_access_provisioning.002 | . . . |
| C3 | it_access_provisioning.003 | . . . |
| C3 | it_access_provisioning.004 | . . . |
| C3 | it_access_provisioning.005 | . . . |
| C3 | it_access_provisioning.006 | . . . |
| C3 | it_access_provisioning.007 | . . . |
| C3 | it_access_provisioning.008 | . . . |
| C3 | it_access_provisioning.009 | . . . |
| C3 | it_access_provisioning.010 | . . . |
| C3 | it_access_provisioning.011 | . . . |
| C3 | it_access_provisioning.012 | . . . |
| C3 | it_access_provisioning.013 | . . . |
| C3 | it_access_provisioning.014 | . . . |
| C3 | it_access_provisioning.015 | . . . |
| C3 | hr_employee_lifecycle.001 | . . . |
| C3 | hr_employee_lifecycle.002 | . . . |
| C3 | hr_employee_lifecycle.003 | . . . |
| C3 | hr_employee_lifecycle.004 | . . . |
| C3 | hr_employee_lifecycle.005 | . . . |
| C3 | hr_employee_lifecycle.006 | . . . |
| C3 | hr_employee_lifecycle.007 | . . . |
| C3 | hr_employee_lifecycle.008 | . . . |
| C3 | hr_employee_lifecycle.009 | . . . |
| C3 | hr_employee_lifecycle.010 | . . . |
| C3 | hr_employee_lifecycle.011 | . . . |
| C3 | hr_employee_lifecycle.012 | . . . |
| C3 | hr_employee_lifecycle.013 | . . . |
| C3 | hr_employee_lifecycle.014 | . . . |
| C3 | hr_employee_lifecycle.015 | . . . |

