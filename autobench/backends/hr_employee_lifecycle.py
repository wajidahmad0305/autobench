"""Mock backend for the ``hr_employee_lifecycle`` category.

Tool set = union of ``ground_truth.required_tool_calls`` across
``tasks/hr_employee_lifecycle/task_001..005.json``:

    get_bamboohr_new_hire_form, create_workday_employee_record,
    generate_start_date_checklist, get_welcomes_channel_for_date,
    add_to_slack_channel, list_employees_due_for_review,
    assign_review_in_lattice, send_slack_dm, get_leave_request,
    get_employee_tenure, get_leave_policy, create_leave_record,
    generate_coverage_plan_draft, get_merit_increase_submission,
    get_department_budget, get_employee_performance_rating,
    apply_workday_compensation_change, generate_compensation_confirmation_report,
    get_approved_bonus_list, post_bonus_to_payroll, update_compensation_history,
    send_bonus_notification_email
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

import structlog

from autobench.backends import _kvstore as kv
from autobench.schema import TaskSpec

log = structlog.get_logger(__name__)

_Handler = Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]]


def initialize(db_conn: sqlite3.Connection, task_spec: TaskSpec) -> None:
    kv.initialize_kv(db_conn, task_spec.context.initial_state)


def dispatch(db_conn: sqlite3.Connection, tool_name: str, arguments: dict[str, Any]) -> Any:
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        raise ValueError(f"unknown tool for hr_employee_lifecycle: {tool_name!r}")
    result = handler(db_conn, arguments)
    log.debug("hr_dispatch", tool=tool_name, arguments=arguments, result=result)
    return result


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------- handlers


def _get_bamboohr_new_hire_form(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    fid = args.get("form_id")
    return {"form_id": fid, **(kv.get_item(db, "bamboohr_new_hire_forms", fid) or {})}


def _create_workday_employee_record(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    eid = args.get("employee_id")
    patch = {k: v for k, v in args.items() if k != "employee_id"}
    kv.patch_item(db, "workday_employees", eid, patch)
    return {"employee_id": eid, "created": True}


def _generate_start_date_checklist(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    entry = dict(args)
    kv.append(db, "start_date_checklists", entry)
    return {
        "checklist_id": kv.next_id(db, "chk"),
        "employee_id": args.get("employee_id"),
        "assigned_to": args.get("assigned_to"),
        "items": ["laptop", "accounts", "orientation"],
    }


def _get_welcomes_channel_for_date(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    date = args.get("date")
    schedule = kv.load_dict(db, "welcomes_channel_schedule")
    return {"date": date, "channel": schedule.get(date)}


def _add_to_slack_channel(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    channel = args.get("channel")
    eid = args.get("employee_id")
    members = kv.load_dict(db, "slack_channel_members")
    roster = list(members.get(channel, []))
    if eid not in roster:
        roster.append(eid)
    members[channel] = roster
    kv.save(db, "slack_channel_members", members)
    return {"channel": channel, "employee_id": eid, "added": True}


def _list_employees_due_for_review(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    employees = kv.load_dict(db, "employees")
    policy = kv.load_dict(db, "review_policy")
    thresholds = set(policy.get("due_at_tenure_months", []))
    due = [
        {
            "employee_id": eid,
            "manager_id": fields.get("manager_id"),
            "tenure_months": fields.get("tenure_months"),
        }
        for eid, fields in employees.items()
        if isinstance(fields, dict) and fields.get("tenure_months") in thresholds
    ]
    return {"due": due}


def _assign_review_in_lattice(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"due_date": kv.load(db, "review_cycle_due_date", None), **args}
    kv.append(db, "lattice_reviews", entry)
    return {"review_id": kv.next_id(db, "rev"), "assigned": True, **entry}


def _send_slack_dm(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    kv.append(db, "slack_dms_sent", dict(args))
    return {"to": args.get("to"), "sent": True}


def _get_leave_request(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    rid = args.get("request_id")
    return {"request_id": rid, **(kv.get_item(db, "leave_requests", rid) or {})}


def _get_employee_tenure(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    eid = args.get("employee_id")
    record = kv.get_item(db, "employees", eid) or {}
    return {"employee_id": eid, "tenure_months": record.get("tenure_months"), **record}


def _get_leave_policy(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    jurisdiction = args.get("jurisdiction")
    leave_type = args.get("leave_type")
    policies = kv.load_dict(db, "leave_policies")
    by_type = policies.get(jurisdiction, {})
    policy = by_type.get(leave_type, {}) if isinstance(by_type, dict) else {}
    return {
        "jurisdiction": jurisdiction,
        "leave_type": leave_type,
        **(policy if isinstance(policy, dict) else {}),
    }


def _create_leave_record(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "status": "approved",
        "paid_pay_code": "PARENTAL_PAID",
        "unpaid_pay_code": "PARENTAL_UNPAID",
        **args,
    }
    kv.append(db, "leave_records", entry)
    return {"record_id": kv.next_id(db, "lr"), "status": "approved", **entry}


def _generate_coverage_plan_draft(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    # TODO(session-6+): a real coverage-plan draft is a generated document. We
    # persist the assignment and return a placeholder string rather than calling
    # an LLM from inside the mock backend.
    kv.append(db, "coverage_plan_drafts", dict(args))
    return {
        "request_id": args.get("request_id"),
        "assigned_to": args.get("assigned_to"),
        "status": "draft",
        "draft": "Auto-generated coverage plan draft (mock).",
    }


def _get_merit_increase_submission(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    submission = kv.load_dict(db, "merit_increase_submission")
    return submission if submission else {"submission_id": args.get("submission_id")}


def _get_department_budget(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    dept = args.get("department")
    budgets = kv.load_dict(db, "department_budgets")
    entry = budgets.get(dept)
    return {"department": dept, **(entry if isinstance(entry, dict) else {})}


def _get_employee_performance_rating(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    eid = args.get("employee_id")
    ratings = kv.load_dict(db, "employee_performance_ratings")
    return {"employee_id": eid, "rating": ratings.get(eid)}


def _apply_workday_compensation_change(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    eid = args.get("employee_id")
    new_salary = args.get("new_salary")
    if new_salary is None:
        current = args.get("current_salary")
        pct = args.get("increase_pct", args.get("proposed_increase_pct"))
        if current is not None and pct is not None:
            new_salary = round(_as_float(current) * (1.0 + _as_float(pct) / 100.0), 2)
    entry = {"employee_id": eid, "new_salary": new_salary, "effective": "next_pay_cycle"}
    kv.append(db, "workday_compensation_changes", entry)
    return {"applied": True, **entry}


def _generate_compensation_confirmation_report(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    # Best-effort: "applied" is derived from what was written; "flagged" is
    # echoed from the caller if provided (the full budget/rating re-check is
    # left to the evaluator against expected_final_state).
    changes = kv.load_list(db, "workday_compensation_changes")
    applied = [c.get("employee_id") for c in changes if isinstance(c, dict)]
    report = {
        "submission_id": args.get("submission_id"),
        "applied": applied,
        "flagged": args.get("flagged", []),
    }
    kv.append(db, "compensation_confirmation_reports", report)
    return report


def _get_approved_bonus_list(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    bonus_list = kv.load_dict(db, "approved_bonus_list")
    return bonus_list if bonus_list else {"batch_id": args.get("batch_id"), "employees": []}


def _post_bonus_to_payroll(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    amount = args.get("amount", args.get("bonus_amount"))
    entry = {"employee_id": args.get("employee_id"), "amount": amount}
    kv.append(db, "workday_payroll_bonus_entries", entry)
    return {"posted": True, **entry}


def _update_compensation_history(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    amount = args.get("bonus_amount", args.get("amount"))
    entry = {"employee_id": args.get("employee_id"), "bonus_amount": amount}
    kv.append(db, "compensation_history_updates", entry)
    return {"updated": True, **entry}


def _send_bonus_notification_email(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    entry = {"employee_id": args.get("employee_id")}
    kv.append(db, "bonus_notifications_sent", entry)
    return {"sent": True, **entry}


_HANDLERS: dict[str, _Handler] = {
    "get_bamboohr_new_hire_form": _get_bamboohr_new_hire_form,
    "create_workday_employee_record": _create_workday_employee_record,
    "generate_start_date_checklist": _generate_start_date_checklist,
    "get_welcomes_channel_for_date": _get_welcomes_channel_for_date,
    "add_to_slack_channel": _add_to_slack_channel,
    "list_employees_due_for_review": _list_employees_due_for_review,
    "assign_review_in_lattice": _assign_review_in_lattice,
    "send_slack_dm": _send_slack_dm,
    "get_leave_request": _get_leave_request,
    "get_employee_tenure": _get_employee_tenure,
    "get_leave_policy": _get_leave_policy,
    "create_leave_record": _create_leave_record,
    "generate_coverage_plan_draft": _generate_coverage_plan_draft,
    "get_merit_increase_submission": _get_merit_increase_submission,
    "get_department_budget": _get_department_budget,
    "get_employee_performance_rating": _get_employee_performance_rating,
    "apply_workday_compensation_change": _apply_workday_compensation_change,
    "generate_compensation_confirmation_report": _generate_compensation_confirmation_report,
    "get_approved_bonus_list": _get_approved_bonus_list,
    "post_bonus_to_payroll": _post_bonus_to_payroll,
    "update_compensation_history": _update_compensation_history,
    "send_bonus_notification_email": _send_bonus_notification_email,
}
