"""Mock backend for the ``financial_reconciliation`` category.

Tool set = union of ``ground_truth.required_tool_calls`` across
``tasks/financial_reconciliation/task_001..005.json``:

    read_invoice_document, get_vendor_expense_category,
    create_quickbooks_draft_invoice, get_bank_feed_transactions,
    get_outstanding_invoices, mark_invoice_paid, flag_transaction_for_review,
    get_stripe_payout, list_settlement_charges, post_gl_entry, get_gl_balance,
    list_purchase_orders_this_month, list_vendor_invoices,
    create_accrual_journal_entry, generate_cfo_summary_report,
    get_vendor_invoice, get_fx_rate, initiate_wire_transfer
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
        raise ValueError(f"unknown tool for financial_reconciliation: {tool_name!r}")
    result = handler(db_conn, arguments)
    log.debug("fin_dispatch", tool=tool_name, arguments=arguments, result=result)
    return result


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------- handlers


def _read_invoice_document(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    did = args.get("document_id")
    return {"document_id": did, **(kv.get_item(db, "documents", did) or {})}


def _get_vendor_expense_category(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    vendor = args.get("vendor_name")
    categories = kv.load_dict(db, "vendor_expense_categories")
    return {"vendor_name": vendor, "expense_category": categories.get(vendor)}


def _create_quickbooks_draft_invoice(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    entry = {"status": "draft", **args}
    kv.append(db, "quickbooks_draft_invoices", entry)
    return {"id": kv.next_id(db, "qbo"), "status": "draft", **entry}


def _get_bank_feed_transactions(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    return {"transactions": kv.load_list(db, "bank_feed_transactions")}


def _get_outstanding_invoices(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    return {"invoices": kv.load_dict(db, "outstanding_invoices")}


def _mark_invoice_paid(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    iid = args.get("invoice_id")
    kv.patch_item(db, "outstanding_invoices", iid, {"status": "paid"})
    return {"invoice_id": iid, "tx_id": args.get("tx_id"), "status": "paid"}


def _flag_transaction_for_review(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"reason": args.get("reason", "no_matching_invoice"), **args}
    kv.append(db, "review_queue", entry)
    return {"tx_id": args.get("tx_id"), "flagged": True}


def _get_stripe_payout(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    pid = args.get("payout_id")
    return {"payout_id": pid, **(kv.get_item(db, "stripe_payouts", pid) or {})}


def _list_settlement_charges(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    swid = args.get("settlement_window_id")
    charges = kv.load_dict(db, "settlement_charges")
    return {"settlement_window_id": swid, "charges": charges.get(swid, [])}


def _post_gl_entry(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "account": args.get("account"),
        "debit": _as_float(args.get("debit")),
        "credit": _as_float(args.get("credit")),
        "ref": args.get("ref"),
    }
    kv.append(db, "gl_entries", entry)
    return {"id": kv.next_id(db, "gl"), "posted": True, **entry}


def _get_gl_balance(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    account = args.get("account")
    balance = 0.0
    for entry in kv.load_list(db, "gl_entries"):
        if not isinstance(entry, dict):
            continue
        if account is None or entry.get("account") == account:
            balance += _as_float(entry.get("debit")) - _as_float(entry.get("credit"))
    return {"account": account, "balance": balance}


def _list_purchase_orders_this_month(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    return {"purchase_orders": kv.load_dict(db, "purchase_orders")}


def _list_vendor_invoices(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    return {"vendor_invoices": kv.load_dict(db, "vendor_invoices")}


def _create_accrual_journal_entry(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"account": "accrued_liabilities", **args}
    kv.append(db, "accrual_journal_entries", entry)
    return {"id": kv.next_id(db, "acc"), "posted": True, **entry}


def _generate_cfo_summary_report(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    by_department: dict[str, float] = {}
    for entry in kv.load_list(db, "accrual_journal_entries"):
        if not isinstance(entry, dict):
            continue
        dept = str(entry.get("department", "Unknown"))
        by_department[dept] = by_department.get(dept, 0.0) + _as_float(entry.get("amount"))
    report = {"by_department": by_department, "total_accrued": sum(by_department.values())}
    kv.save(db, "cfo_summary_report", report)
    return report


def _get_vendor_invoice(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    iid = args.get("invoice_id")
    return {"invoice_id": iid, **(kv.get_item(db, "vendor_invoices", iid) or {})}


def _get_fx_rate(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    pair = args.get("pair")
    rates = kv.load_dict(db, "fx_rates")
    return {"pair": pair, "rate": rates.get(pair)}


def _initiate_wire_transfer(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"currency": "USD", **args}
    kv.append(db, "wire_transfers", entry)
    iid = args.get("invoice_id")
    if iid is not None:
        kv.patch_item(db, "vendor_invoices", iid, {"status": "paid"})
    return {"id": kv.next_id(db, "wire"), "status": "sent", **entry}


_HANDLERS: dict[str, _Handler] = {
    "read_invoice_document": _read_invoice_document,
    "get_vendor_expense_category": _get_vendor_expense_category,
    "create_quickbooks_draft_invoice": _create_quickbooks_draft_invoice,
    "get_bank_feed_transactions": _get_bank_feed_transactions,
    "get_outstanding_invoices": _get_outstanding_invoices,
    "mark_invoice_paid": _mark_invoice_paid,
    "flag_transaction_for_review": _flag_transaction_for_review,
    "get_stripe_payout": _get_stripe_payout,
    "list_settlement_charges": _list_settlement_charges,
    "post_gl_entry": _post_gl_entry,
    "get_gl_balance": _get_gl_balance,
    "list_purchase_orders_this_month": _list_purchase_orders_this_month,
    "list_vendor_invoices": _list_vendor_invoices,
    "create_accrual_journal_entry": _create_accrual_journal_entry,
    "generate_cfo_summary_report": _generate_cfo_summary_report,
    "get_vendor_invoice": _get_vendor_invoice,
    "get_fx_rate": _get_fx_rate,
    "initiate_wire_transfer": _initiate_wire_transfer,
}

