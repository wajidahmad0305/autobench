"""Full JSON Schema for every mock-backend tool, keyed by category.

This replaces the ``args_contain``-derived schema *synthesis* that
``scripts/run_pilot.py`` used to do. Synthesis only exposed the arguments that
appear in ``ground_truth.required_tool_calls``; but the mock backends' record
tools (``add_to_fulfillment_queue``, ``create_stripe_refund``, …) store every
argument passed, and ``expected_final_state`` depends on fields the model never
saw. Every schema here covers the full set of fields its handler needs to reach
the target state, with descriptions that pin ID prefixes and enum-like values so
models stop truncating identifiers or copying one argument into another.

``get_tool_schema(category, tool_name)`` returns an OpenAI-style
``{"name", "description", "parameters"}`` dict; it raises ``KeyError`` with a
helpful message when a task references a tool with no registry entry.
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------- tiny builders


def _s(desc: str) -> dict[str, Any]:
    return {"type": "string", "description": desc}


def _i(desc: str) -> dict[str, Any]:
    return {"type": "integer", "description": desc}


def _n(desc: str) -> dict[str, Any]:
    return {"type": "number", "description": desc}


def _arr(desc: str) -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "description": desc}


def _enum(values: list[str], desc: str) -> dict[str, Any]:
    return {"type": "string", "enum": values, "description": desc}


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }


def _person(example: str) -> dict[str, Any]:
    return _s(
        f"The employee/user identifier, e.g. {example!r} (never the bare number). "
        "Pass this same value for BOTH 'employee_id' and 'user_id'."
    )


# ============================================================ crm_order_fulfilment

CRM_ORDER_FULFILMENT: dict[str, dict[str, Any]] = {
    "get_hubspot_contact_by_email": _tool(
        "get_hubspot_contact_by_email",
        "Look up a HubSpot contact by email. Returns whether it exists.",
        {"email": _s("Contact email address, e.g. 'jordan.lee@example.com'.")},
        ["email"],
    ),
    "create_hubspot_contact": _tool(
        "create_hubspot_contact",
        "Create a HubSpot contact. Include company / company_size when known "
        "(e.g. from lookup_company_by_domain).",
        {
            "email": _s("Contact email address, e.g. 'jordan.lee@example.com'."),
            "full_name": _s("Contact full name, e.g. 'Amy Chen'."),
            "company": _s("Company name from enrichment, e.g. 'BrightGear Inc' (omit if unknown)."),
            "company_size": _s("Company size bucket, e.g. '11-50' (omit if unknown)."),
        },
        ["email"],
    ),
    "tag_hubspot_contact": _tool(
        "tag_hubspot_contact",
        "Add a tag (typically the purchased SKU) to an existing HubSpot contact.",
        {
            "email": _s("Contact email address, e.g. 'jordan.lee@example.com'."),
            "tag": _s("Tag to add, usually the product SKU, e.g. 'WGT-100-BLU'."),
        },
        ["email", "tag"],
    ),
    "add_to_fulfillment_queue": _tool(
        "add_to_fulfillment_queue",
        "Queue a Shopify order for fulfillment with full customer and product context.",
        {
            "order_id": _s("Full Shopify order id incl. prefix, e.g. 'SHOP-10432' (never '10432')."),
            "email": _s("Customer email address, e.g. 'jordan.lee@example.com'."),
            "sku": _s("Product SKU incl. prefix, e.g. 'WGT-100-BLU'."),
            "qty": _i("Quantity ordered, e.g. 2."),
        },
        ["order_id", "email", "sku", "qty"],
    ),
    "get_hubspot_ticket": _tool(
        "get_hubspot_ticket",
        "Fetch a HubSpot support ticket by id.",
        {"ticket_id": _s("Full ticket id incl. prefix, e.g. 'TICKET-5521' (never '5521').")},
        ["ticket_id"],
    ),
    "get_shopify_order": _tool(
        "get_shopify_order",
        "Fetch a Shopify order by id.",
        {"order_id": _s("Full Shopify order id incl. prefix, e.g. 'SHOP-9981' (never '9981').")},
        ["order_id"],
    ),
    "create_stripe_refund": _tool(
        "create_stripe_refund",
        "Issue a Stripe refund against a payment intent for the full order amount.",
        {
            "payment_intent_id": _s(
                "Stripe payment intent id incl. prefix, e.g. 'pi_9981abc' (never '9981')."
            ),
            "amount": _i(
                "Refund amount in integer cents (Stripe minor units), e.g. 8400 for an "
                "$84.00 order. Multiply the order's dollar total by 100."
            ),
            "currency": _s("ISO currency code from the order, e.g. 'USD'."),
            "order_id": _s("Full Shopify order id incl. prefix, e.g. 'SHOP-9981'."),
        },
        ["payment_intent_id", "amount", "currency", "order_id"],
    ),
    "update_hubspot_ticket_status": _tool(
        "update_hubspot_ticket_status",
        "Set the status of a HubSpot ticket.",
        {
            "ticket_id": _s("Full ticket id incl. prefix, e.g. 'TICKET-5521' (never '5521')."),
            "status": _enum(
                ["open", "in_progress", "resolved", "closed"],
                "New ticket status. Must be one of the allowed lowercase values.",
            ),
        },
        ["ticket_id", "status"],
    ),
    "list_salesforce_closed_won_opportunities": _tool(
        "list_salesforce_closed_won_opportunities",
        "List all Salesforce opportunities in stage 'Closed Won'. Takes no arguments.",
        {},
        [],
    ),
    "get_shopify_orders_by_account": _tool(
        "get_shopify_orders_by_account",
        "List Shopify orders placed by a given account (company).",
        {"account": _s("Account / company name, e.g. 'Acme Corp'.")},
        ["account"],
    ),
    "flag_opportunity": _tool(
        "flag_opportunity",
        "Flag a Salesforce opportunity for follow-up.",
        {"opportunity_id": _s("Full opportunity id incl. prefix, e.g. 'OPP-3302' (never '3302').")},
        ["opportunity_id"],
    ),
    "add_opportunity_note": _tool(
        "add_opportunity_note",
        "Attach a note to a Salesforce opportunity.",
        {
            "opportunity_id": _s("Full opportunity id incl. prefix, e.g. 'OPP-3302'."),
            "note": _s("Free-text note content."),
        },
        ["opportunity_id"],
    ),
    "lookup_company_by_domain": _tool(
        "lookup_company_by_domain",
        "Enrich a company by email domain. Returns name and size bucket (nulls if unknown).",
        {"domain": _s("Company email domain, e.g. 'brightgear.com'.")},
        ["domain"],
    ),
    "route_to_pipeline": _tool(
        "route_to_pipeline",
        "Route a contact (by email) into a HubSpot pipeline.",
        {
            "pipeline": _enum(
                [
                    "smb_pipeline",
                    "midmarket_pipeline",
                    "enterprise_pipeline",
                    "needs_enrichment_pipeline",
                ],
                "Target HubSpot pipeline. Must be one of the allowed values.",
            ),
            "email": _s("Contact email address, e.g. 'leo@vertexbio.com'."),
        },
        ["pipeline", "email"],
    ),
    "update_shopify_order_status": _tool(
        "update_shopify_order_status",
        "Set the status of a Shopify order.",
        {
            "order_id": _s("Full Shopify order id incl. prefix, e.g. 'SHOP-22110'."),
            "status": _enum(
                ["processing", "shipped", "delivered", "cancelled"],
                "New order status. Must be one of the allowed lowercase values.",
            ),
        },
        ["order_id", "status"],
    ),
    "send_confirmation_email": _tool(
        "send_confirmation_email",
        "Send the customer a shipping-confirmation email for an order.",
        {"order_id": _s("Full Shopify order id incl. prefix, e.g. 'SHOP-22110'.")},
        ["order_id"],
    ),
}

# ======================================================= financial_reconciliation

FINANCIAL_RECONCILIATION: dict[str, dict[str, Any]] = {
    "read_invoice_document": _tool(
        "read_invoice_document",
        "Extract a vendor invoice document by id.",
        {"document_id": _s("Full document id incl. prefix, e.g. 'INV-VEND-3341'.")},
        ["document_id"],
    ),
    "get_vendor_expense_category": _tool(
        "get_vendor_expense_category",
        "Look up the default expense category (GL code) for a vendor.",
        {"vendor_name": _s("Vendor name exactly as on the invoice, e.g. 'Metro Office Supplies'.")},
        ["vendor_name"],
    ),
    "create_quickbooks_draft_invoice": _tool(
        "create_quickbooks_draft_invoice",
        "Create a QuickBooks draft bill from an extracted invoice.",
        {
            "invoice_number": _s("Full invoice number incl. prefix, e.g. 'INV-VEND-3341'."),
            "vendor_name": _s("Vendor name, e.g. 'Metro Office Supplies'."),
            "expense_category": _s(
                "Expense category string copied verbatim from get_vendor_expense_category, "
                "e.g. '6021 — Office supplies'."
            ),
            "total": _n("Invoice total amount, e.g. 500.0."),
        },
        ["invoice_number", "vendor_name", "expense_category", "total"],
    ),
    "get_bank_feed_transactions": _tool(
        "get_bank_feed_transactions",
        "List today's bank-feed transactions. Takes no arguments.",
        {},
        [],
    ),
    "get_outstanding_invoices": _tool(
        "get_outstanding_invoices",
        "List all invoices still outstanding. Takes no arguments.",
        {},
        [],
    ),
    "mark_invoice_paid": _tool(
        "mark_invoice_paid",
        "Mark an outstanding invoice as paid, matched to a bank transaction.",
        {
            "invoice_id": _s("Full invoice id incl. prefix, e.g. 'INV-8801'."),
            "tx_id": _s("Full bank transaction id incl. prefix, e.g. 'TX-501'."),
        },
        ["invoice_id", "tx_id"],
    ),
    "flag_transaction_for_review": _tool(
        "flag_transaction_for_review",
        "Send an unmatched bank transaction to the manual review queue.",
        {
            "tx_id": _s("Full bank transaction id incl. prefix, e.g. 'TX-503'."),
            "reason": _s("Reason code, e.g. 'no_matching_invoice'."),
        },
        ["tx_id"],
    ),
    "get_stripe_payout": _tool(
        "get_stripe_payout",
        "Fetch a Stripe payout by id.",
        {"payout_id": _s("Full payout id incl. prefix, e.g. 'PO-7742'.")},
        ["payout_id"],
    ),
    "list_settlement_charges": _tool(
        "list_settlement_charges",
        "List the charges settled in a given settlement window.",
        {"settlement_window_id": _s("Full settlement window id, e.g. 'SW-2026-08-26'.")},
        ["settlement_window_id"],
    ),
    "post_gl_entry": _tool(
        "post_gl_entry",
        "Post one general-ledger line. Every line has both a debit and a credit amount; "
        "set the side that does not apply to 0.",
        {
            "account": _enum(
                ["cash", "stripe_clearing", "accounts_payable", "cash_usd", "fx_gain_loss"],
                "GL account name. Must be one of the allowed lowercase values.",
            ),
            "ref": _s("Source-document reference incl. prefix, e.g. 'PO-7742' or 'INV-EUR-501'."),
            "debit": _n("Debit amount for this line (0 if this line is a credit), e.g. 1840.0."),
            "credit": _n("Credit amount for this line (0 if this line is a debit), e.g. 1840.0."),
        },
        ["account", "ref", "debit", "credit"],
    ),
    "get_gl_balance": _tool(
        "get_gl_balance",
        "Return the running balance for a GL account (or all accounts if omitted).",
        {"account": _s("GL account name, e.g. 'cash'. Omit for the total.")},
        [],
    ),
    "list_purchase_orders_this_month": _tool(
        "list_purchase_orders_this_month",
        "List purchase orders received in the current month. Takes no arguments.",
        {},
        [],
    ),
    "list_vendor_invoices": _tool(
        "list_vendor_invoices",
        "List all vendor invoices on file. Takes no arguments.",
        {},
        [],
    ),
    "create_accrual_journal_entry": _tool(
        "create_accrual_journal_entry",
        "Book a month-end accrual for a received PO that has no matching vendor invoice yet.",
        {
            "po_ref": _s("Full purchase-order reference incl. prefix, e.g. 'PO-202'."),
            "department": _s("Owning department from the PO, e.g. 'Marketing'."),
            "amount": _n("Accrual amount from the PO, e.g. 1500.0."),
            "account": _s("GL account; defaults to 'accrued_liabilities' if omitted."),
        },
        ["po_ref", "department", "amount"],
    ),
    "generate_cfo_summary_report": _tool(
        "generate_cfo_summary_report",
        "Summarise the accruals booked this run by department. Takes no arguments.",
        {},
        [],
    ),
    "get_vendor_invoice": _tool(
        "get_vendor_invoice",
        "Fetch a vendor invoice by id.",
        {"invoice_id": _s("Full invoice id incl. prefix, e.g. 'INV-EUR-501'.")},
        ["invoice_id"],
    ),
    "get_fx_rate": _tool(
        "get_fx_rate",
        "Get the current FX rate for a currency pair.",
        {"pair": _s("Currency pair, e.g. 'EUR_USD'.")},
        ["pair"],
    ),
    "initiate_wire_transfer": _tool(
        "initiate_wire_transfer",
        "Send a wire to pay a vendor invoice; marks the invoice paid.",
        {
            "invoice_id": _s("Full invoice id incl. prefix, e.g. 'INV-EUR-501'."),
            "amount_usd": _n("USD amount to wire (invoice amount * current FX rate), e.g. 2170.0."),
            "currency": _s("Settlement currency; defaults to 'USD'."),
        },
        ["invoice_id", "amount_usd"],
    ),
}

# ======================================================= it_access_provisioning

IT_ACCESS_PROVISIONING: dict[str, dict[str, Any]] = {
    "get_department_provisioning_config": _tool(
        "get_department_provisioning_config",
        "Return the Okta groups and Slack channel for a department.",
        {"department": _s("Department name, e.g. 'Engineering'.")},
        ["department"],
    ),
    "provision_google_workspace_email": _tool(
        "provision_google_workspace_email",
        "Create the new hire's Google Workspace mailbox.",
        {
            "employee_id": _person("EMP-4471"),
            "user_id": _person("EMP-4471"),
            "email": _s("Work email to provision, e.g. 'sofia.martinez@newco.io'."),
            "full_name": _s("Employee full name, e.g. 'Sofia Martinez'."),
        },
        ["employee_id", "user_id", "email", "full_name"],
    ),
    "add_okta_group": _tool(
        "add_okta_group",
        "Add an employee to an Okta group.",
        {
            "employee_id": _person("EMP-4471"),
            "user_id": _person("EMP-4471"),
            "group": _s("Okta group name, e.g. 'okta-eng-all'."),
        },
        ["employee_id", "user_id", "group"],
    ),
    "remove_okta_group": _tool(
        "remove_okta_group",
        "Remove an employee from an Okta group.",
        {
            "employee_id": _person("EMP-2001"),
            "user_id": _person("EMP-2001"),
            "group": _s("Okta group name, e.g. 'okta-salesforce-users'."),
        },
        ["employee_id", "user_id", "group"],
    ),
    "post_slack_message": _tool(
        "post_slack_message",
        "Post a welcome message about an employee to a Slack channel.",
        {
            "channel": _s("Slack channel incl. '#', e.g. '#eng-team'."),
            "employee_id": _person("EMP-4471"),
            "user_id": _person("EMP-4471"),
        },
        ["channel", "employee_id", "user_id"],
    ),
    "get_access_review_report": _tool(
        "get_access_review_report",
        "Fetch a quarterly access-review report with its per-user decisions.",
        {"report_id": _s("Full report id incl. prefix, e.g. 'AR-2026-Q3'.")},
        ["report_id"],
    ),
    "revoke_oauth_tokens": _tool(
        "revoke_oauth_tokens",
        "Revoke a user's OAuth tokens for one application.",
        {
            "employee_id": _person("EMP-2001"),
            "user_id": _person("EMP-2001"),
            "app": _s("Application name, e.g. 'Salesforce'."),
        },
        ["employee_id", "user_id", "app"],
    ),
    "log_security_audit_event": _tool(
        "log_security_audit_event",
        "Append an entry to the security audit log. Include every field relevant to the action.",
        {
            "employee_id": _person("EMP-2001"),
            "user_id": _person("EMP-2001"),
            "action": _enum(
                ["REVOKE", "GRANT", "GRANT_TEMP_ACCESS"],
                "Audit action code (uppercase). Use 'REVOKE' for access removals and "
                "'GRANT_TEMP_ACCESS' for temporary elevations.",
            ),
            "app": _s("Application involved, e.g. 'Salesforce' (when applicable)."),
            "request_id": _s("Related request id incl. prefix, e.g. 'EAR-771' (when applicable)."),
            "expires_at": _s("Expiry timestamp ISO-8601, e.g. '2026-08-27T15:30:00Z' (when applicable)."),
        },
        [],
    ),
    "get_role_change_event": _tool(
        "get_role_change_event",
        "Fetch the role-change event for a user (old role, new role, effective date).",
        {"employee_id": _person("EMP-3110"), "user_id": _person("EMP-3110")},
        ["employee_id", "user_id"],
    ),
    "update_workday_job_title": _tool(
        "update_workday_job_title",
        "Update a user's Workday job title.",
        {
            "employee_id": _person("EMP-3110"),
            "user_id": _person("EMP-3110"),
            "job_title": _s("New job title, e.g. 'Engineering Manager'."),
        },
        ["employee_id", "user_id", "job_title"],
    ),
    "notify_aws_iam": _tool(
        "notify_aws_iam",
        "Notify AWS IAM of a user's new role.",
        {
            "employee_id": _person("EMP-3110"),
            "user_id": _person("EMP-3110"),
            "new_role": _s("The user's new role, e.g. 'Engineering Manager'."),
        },
        ["employee_id", "user_id", "new_role"],
    ),
    "notify_github_enterprise": _tool(
        "notify_github_enterprise",
        "Notify GitHub Enterprise of a user's new role.",
        {
            "employee_id": _person("EMP-3110"),
            "user_id": _person("EMP-3110"),
            "new_role": _s("The user's new role, e.g. 'Engineering Manager'."),
        },
        ["employee_id", "user_id", "new_role"],
    ),
    "get_approved_access_hours": _tool(
        "get_approved_access_hours",
        "Return the approved access-hours window (UTC). Takes no arguments.",
        {},
        [],
    ),
    "provision_temporary_iam_role": _tool(
        "provision_temporary_iam_role",
        "Grant a time-boxed elevated IAM role in an AWS account.",
        {
            "employee_id": _person("EMP-5091"),
            "user_id": _person("EMP-5091"),
            "account_id": _s("AWS account id, e.g. 'aws-prod-217'."),
            "duration_minutes": _i("Grant duration in minutes, e.g. 60."),
        },
        ["employee_id", "user_id", "account_id", "duration_minutes"],
    ),
    "notify_pagerduty": _tool(
        "notify_pagerduty",
        "Notify PagerDuty about an emergency-access request.",
        {
            "request_id": _s("Full request id incl. prefix, e.g. 'EAR-771'."),
            "team": _s("Team to notify; defaults to 'security'."),
        },
        ["request_id"],
    ),
    "get_termination_event": _tool(
        "get_termination_event",
        "Fetch the termination event for a user (manager, effective time, reason).",
        {"employee_id": _person("EMP-1188"), "user_id": _person("EMP-1188")},
        ["employee_id", "user_id"],
    ),
    "revoke_okta_sso": _tool(
        "revoke_okta_sso",
        "Revoke a user's Okta SSO sessions.",
        {"employee_id": _person("EMP-1188"), "user_id": _person("EMP-1188")},
        ["employee_id", "user_id"],
    ),
    "revoke_aws_iam_access": _tool(
        "revoke_aws_iam_access",
        "Revoke a user's AWS IAM access and sessions.",
        {"employee_id": _person("EMP-1188"), "user_id": _person("EMP-1188")},
        ["employee_id", "user_id"],
    ),
    "revoke_github_enterprise_access": _tool(
        "revoke_github_enterprise_access",
        "Revoke a user's GitHub Enterprise access and sessions.",
        {"employee_id": _person("EMP-1188"), "user_id": _person("EMP-1188")},
        ["employee_id", "user_id"],
    ),
    "revoke_google_workspace_access": _tool(
        "revoke_google_workspace_access",
        "Revoke a user's Google Workspace access and sessions.",
        {"employee_id": _person("EMP-1188"), "user_id": _person("EMP-1188")},
        ["employee_id", "user_id"],
    ),
    "quarantine_active_sessions": _tool(
        "quarantine_active_sessions",
        "Terminate all of a user's active sessions across every system.",
        {"employee_id": _person("EMP-1188"), "user_id": _person("EMP-1188")},
        ["employee_id", "user_id"],
    ),
    "transfer_asset_ownership": _tool(
        "transfer_asset_ownership",
        "Transfer all assets owned by the departing employee to a new owner.",
        {
            "employee_id": _person("EMP-1188"),
            "user_id": _person("EMP-1188"),
            "new_owner_id": _s("New owner's employee id incl. prefix, e.g. 'EMP-1050'."),
        },
        ["employee_id", "user_id", "new_owner_id"],
    ),
}

# ======================================================= hr_employee_lifecycle

HR_EMPLOYEE_LIFECYCLE: dict[str, dict[str, Any]] = {
    "get_bamboohr_new_hire_form": _tool(
        "get_bamboohr_new_hire_form",
        "Fetch a BambooHR new-hire form by id.",
        {"form_id": _s("Full form id incl. prefix, e.g. 'NHF-6612'.")},
        ["form_id"],
    ),
    "create_workday_employee_record": _tool(
        "create_workday_employee_record",
        "Create the employee's Workday record.",
        {
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-6612'."),
            "full_name": _s("Employee full name, e.g. 'Marcus Webb'."),
            "department": _s("Department, e.g. 'Customer Success'."),
            "manager_id": _s("Manager's employee id incl. prefix, e.g. 'EMP-2200'."),
        },
        ["employee_id", "full_name", "department", "manager_id"],
    ),
    "generate_start_date_checklist": _tool(
        "generate_start_date_checklist",
        "Generate the day-one checklist for a new hire, assigned to their manager.",
        {
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-6612'."),
            "assigned_to": _s("Manager's employee id incl. prefix, e.g. 'EMP-2200'."),
        },
        ["employee_id", "assigned_to"],
    ),
    "get_welcomes_channel_for_date": _tool(
        "get_welcomes_channel_for_date",
        "Return the Slack welcomes channel scheduled for a start date.",
        {"date": _s("Start date, ISO-8601 date, e.g. '2026-09-08'.")},
        ["date"],
    ),
    "add_to_slack_channel": _tool(
        "add_to_slack_channel",
        "Add an employee to a Slack channel.",
        {
            "channel": _s("Slack channel incl. '#', e.g. '#welcomes-sept-8'."),
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-6612'."),
        },
        ["channel", "employee_id"],
    ),
    "list_employees_due_for_review": _tool(
        "list_employees_due_for_review",
        "List employees whose tenure makes them due for a review this cycle. Takes no arguments.",
        {},
        [],
    ),
    "assign_review_in_lattice": _tool(
        "assign_review_in_lattice",
        "Create a Lattice review for an employee, owned by their manager.",
        {
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-7001'."),
            "manager_id": _s("Manager's employee id incl. prefix, e.g. 'EMP-9000'."),
            "due_date": _s("Review due date ISO-8601, e.g. '2026-09-15' (defaults to the cycle date)."),
        },
        ["employee_id", "manager_id"],
    ),
    "send_slack_dm": _tool(
        "send_slack_dm",
        "DM a manager the list of their direct reports due for review.",
        {
            "to": _s("Manager's employee id incl. prefix, e.g. 'EMP-9000'."),
            "direct_reports": _arr("Their direct reports due this cycle, e.g. ['EMP-7001','EMP-7002']."),
            "due_date": _s("Review due date ISO-8601, e.g. '2026-09-15'."),
        },
        ["to"],
    ),
    "get_leave_request": _tool(
        "get_leave_request",
        "Fetch a Workday leave request by id.",
        {"request_id": _s("Full leave request id incl. prefix, e.g. 'LR-4402'.")},
        ["request_id"],
    ),
    "get_employee_tenure": _tool(
        "get_employee_tenure",
        "Return an employee's tenure and jurisdiction.",
        {"employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-8801'.")},
        ["employee_id"],
    ),
    "get_leave_policy": _tool(
        "get_leave_policy",
        "Return the leave policy for a jurisdiction and leave type.",
        {
            "jurisdiction": _s("Jurisdiction code, e.g. 'CA-US'."),
            "leave_type": _s("Leave type, e.g. 'parental'."),
        },
        ["jurisdiction", "leave_type"],
    ),
    "create_leave_record": _tool(
        "create_leave_record",
        "Create the approved leave record. paid_weeks + unpaid_weeks must equal the total requested.",
        {
            "request_id": _s("Full leave request id incl. prefix, e.g. 'LR-4402'."),
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-8801'."),
            "paid_weeks": _i("Paid weeks per policy, e.g. 12."),
            "unpaid_weeks": _i("Unpaid weeks (total requested minus paid), e.g. 4."),
        },
        ["request_id", "paid_weeks", "unpaid_weeks"],
    ),
    "generate_coverage_plan_draft": _tool(
        "generate_coverage_plan_draft",
        "Draft a coverage plan for the leave, assigned to the employee's manager.",
        {
            "request_id": _s("Full leave request id incl. prefix, e.g. 'LR-4402'."),
            "assigned_to": _s("Manager's employee id incl. prefix, e.g. 'EMP-9500'."),
        },
        ["request_id", "assigned_to"],
    ),
    "get_merit_increase_submission": _tool(
        "get_merit_increase_submission",
        "Fetch a merit-increase submission with its proposed increases.",
        {"submission_id": _s("Full submission id incl. prefix, e.g. 'MI-2026Q3-ENG'.")},
        ["submission_id"],
    ),
    "get_department_budget": _tool(
        "get_department_budget",
        "Return a department's merit budget cap.",
        {"department": _s("Department name, e.g. 'Engineering'.")},
        ["department"],
    ),
    "get_employee_performance_rating": _tool(
        "get_employee_performance_rating",
        "Return an employee's latest performance rating.",
        {"employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-8001'.")},
        ["employee_id"],
    ),
    "apply_workday_compensation_change": _tool(
        "apply_workday_compensation_change",
        "Apply an approved salary change in Workday. Pass new_salary, or current_salary + increase_pct.",
        {
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-8001'."),
            "new_salary": _n("Resulting salary, e.g. 100700.0."),
            "current_salary": _n("Current salary, e.g. 95000."),
            "increase_pct": _n("Percentage increase, e.g. 6."),
        },
        ["employee_id"],
    ),
    "generate_compensation_confirmation_report": _tool(
        "generate_compensation_confirmation_report",
        "Produce the confirmation report listing applied changes and flagged (rejected) ones.",
        {
            "submission_id": _s("Full submission id incl. prefix, e.g. 'MI-2026Q3-ENG'."),
            "flagged": _arr("Employee ids that were not applied, with reasons."),
        },
        ["submission_id"],
    ),
    "get_approved_bonus_list": _tool(
        "get_approved_bonus_list",
        "Fetch the approved annual-bonus batch and its per-employee amounts.",
        {"batch_id": _s("Full batch id incl. prefix, e.g. 'BONUS-2026-ANNUAL'.")},
        ["batch_id"],
    ),
    "post_bonus_to_payroll": _tool(
        "post_bonus_to_payroll",
        "Post one employee's bonus to Workday payroll.",
        {
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-9101'."),
            "amount": _n("Bonus amount from the approved batch, e.g. 2500.0."),
        },
        ["employee_id", "amount"],
    ),
    "update_compensation_history": _tool(
        "update_compensation_history",
        "Record one employee's bonus in their compensation history.",
        {
            "employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-9101'."),
            "bonus_amount": _n("Bonus amount from the approved batch, e.g. 2500.0."),
        },
        ["employee_id", "bonus_amount"],
    ),
    "send_bonus_notification_email": _tool(
        "send_bonus_notification_email",
        "Email one employee their bonus notification.",
        {"employee_id": _s("Full employee id incl. prefix, e.g. 'EMP-9101'.")},
        ["employee_id"],
    ),
}

_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {
    "crm_order_fulfilment": CRM_ORDER_FULFILMENT,
    "financial_reconciliation": FINANCIAL_RECONCILIATION,
    "it_access_provisioning": IT_ACCESS_PROVISIONING,
    "hr_employee_lifecycle": HR_EMPLOYEE_LIFECYCLE,
}


def get_tool_schema(category: str, tool_name: str) -> dict[str, Any]:
    """Return the OpenAI-style schema dict for ``tool_name`` in ``category``."""
    try:
        schemas = _REGISTRY[category]
    except KeyError:
        raise KeyError(
            f"tool_registry: unknown category {category!r} (known: {sorted(_REGISTRY)})"
        ) from None
    try:
        return schemas[tool_name]
    except KeyError:
        raise KeyError(
            f"tool_registry: category {category!r} has no schema for tool {tool_name!r} "
            f"(known: {sorted(schemas)})"
        ) from None

