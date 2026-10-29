"""Mock backend for the ``crm_order_fulfilment`` category.

Tool set = union of ``ground_truth.required_tool_calls`` across
``tasks/crm_order_fulfilment/task_001..005.json``:

    get_hubspot_contact_by_email, create_hubspot_contact, tag_hubspot_contact,
    add_to_fulfillment_queue, get_hubspot_ticket, get_shopify_order,
    create_stripe_refund, update_hubspot_ticket_status,
    list_salesforce_closed_won_opportunities, get_shopify_orders_by_account,
    flag_opportunity, add_opportunity_note, lookup_company_by_domain,
    route_to_pipeline, update_shopify_order_status, send_confirmation_email
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
        raise ValueError(f"unknown tool for crm_order_fulfilment: {tool_name!r}")
    result = handler(db_conn, arguments)
    log.debug("crm_dispatch", tool=tool_name, arguments=arguments, result=result)
    return result


# --------------------------------------------------------------------- handlers


def _get_hubspot_contact_by_email(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    email = args.get("email")
    contact = kv.get_item(db, "hubspot_contacts", email)
    return {"email": email, "found": contact is not None, "contact": contact}


def _create_hubspot_contact(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    email = args.get("email")
    patch = {k: v for k, v in args.items() if k != "email"}
    patch["email"] = email
    record = kv.patch_item(db, "hubspot_contacts", email, patch)
    return {"id": kv.next_id(db, "contact"), "email": email, "created": True, "contact": record}


def _tag_hubspot_contact(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    email = args.get("email")
    tag = args.get("tag")
    existing = kv.get_item(db, "hubspot_contacts", email) or {}
    tags = list(existing.get("tags", []))
    if tag not in tags:
        tags.append(tag)
    record = kv.patch_item(db, "hubspot_contacts", email, {"email": email, "tags": tags})
    return {"email": email, "tag": tag, "tags": record["tags"], "tagged": True}


def _add_to_fulfillment_queue(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"status": "queued", **args}
    kv.append(db, "fulfillment_queue", entry)
    return {"order_id": args.get("order_id"), "queued": True, "entry": entry}


def _get_hubspot_ticket(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    tid = args.get("ticket_id")
    ticket = kv.get_item(db, "hubspot_tickets", tid) or {}
    return {"ticket_id": tid, **ticket}


def _get_shopify_order(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    oid = args.get("order_id")
    order = kv.get_item(db, "shopify_orders", oid) or {}
    return {"order_id": oid, **order}


def _create_stripe_refund(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = dict(args)
    kv.append(db, "stripe_refunds", entry)
    return {"id": kv.next_id(db, "re"), "status": "succeeded", **entry}


def _update_hubspot_ticket_status(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    tid = args.get("ticket_id")
    status = args.get("status")
    kv.patch_item(db, "hubspot_tickets", tid, {"status": status})
    return {"ticket_id": tid, "status": status, "updated": True}


def _list_salesforce_closed_won_opportunities(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    opps = kv.load_dict(db, "salesforce_opportunities")
    won = [
        {"opportunity_id": oid, **fields}
        for oid, fields in opps.items()
        if isinstance(fields, dict) and fields.get("status") == "Closed Won"
    ]
    return {"opportunities": won}


def _get_shopify_orders_by_account(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    account = args.get("account")
    by_account = kv.load_dict(db, "shopify_orders_by_account")
    return {"account": account, "orders": by_account.get(account, [])}


def _flag_opportunity(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    oid = args.get("opportunity_id")
    kv.patch_item(db, "salesforce_opportunities", oid, {"flagged": True})
    return {"opportunity_id": oid, "flagged": True}


def _add_opportunity_note(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    oid = args.get("opportunity_id")
    kv.patch_item(db, "opportunity_notes", oid, {"note_added": True, "note": args.get("note")})
    return {"opportunity_id": oid, "note_added": True}


def _lookup_company_by_domain(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    domain = args.get("domain")
    directory = kv.load_dict(db, "company_directory")
    hit = directory.get(domain)
    if not isinstance(hit, dict):
        return {"domain": domain, "name": None, "size_bucket": None}
    return {"domain": domain, **hit}


def _route_to_pipeline(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    pipeline = args.get("pipeline")
    email = args.get("email")
    pipelines = kv.load_dict(db, "pipelines")
    members = list(pipelines.get(pipeline, []))
    if email not in members:
        members.append(email)
    pipelines[pipeline] = members
    kv.save(db, "pipelines", pipelines)
    return {"pipeline": pipeline, "email": email, "routed": True}


def _update_shopify_order_status(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    oid = args.get("order_id")
    status = args.get("status")
    kv.patch_item(db, "shopify_orders", oid, {"status": status})
    return {"order_id": oid, "status": status, "updated": True}


def _send_confirmation_email(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"template": "shipping_confirmation", **args}
    kv.append(db, "sendgrid_emails_sent", entry)
    return {"order_id": args.get("order_id"), "sent": True}


_HANDLERS: dict[str, _Handler] = {
    "get_hubspot_contact_by_email": _get_hubspot_contact_by_email,
    "create_hubspot_contact": _create_hubspot_contact,
    "tag_hubspot_contact": _tag_hubspot_contact,
    "add_to_fulfillment_queue": _add_to_fulfillment_queue,
    "get_hubspot_ticket": _get_hubspot_ticket,
    "get_shopify_order": _get_shopify_order,
    "create_stripe_refund": _create_stripe_refund,
    "update_hubspot_ticket_status": _update_hubspot_ticket_status,
    "list_salesforce_closed_won_opportunities": _list_salesforce_closed_won_opportunities,
    "get_shopify_orders_by_account": _get_shopify_orders_by_account,
    "flag_opportunity": _flag_opportunity,
    "add_opportunity_note": _add_opportunity_note,
    "lookup_company_by_domain": _lookup_company_by_domain,
    "route_to_pipeline": _route_to_pipeline,
    "update_shopify_order_status": _update_shopify_order_status,
    "send_confirmation_email": _send_confirmation_email,
}

