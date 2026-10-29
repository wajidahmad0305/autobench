"""Mock backend for the ``it_access_provisioning`` category.

Tool set = union of ``ground_truth.required_tool_calls`` across
``tasks/it_access_provisioning/task_001..005.json``:

    get_department_provisioning_config, provision_google_workspace_email,
    add_okta_group, post_slack_message, get_access_review_report,
    remove_okta_group, revoke_oauth_tokens, log_security_audit_event,
    get_role_change_event, update_workday_job_title, notify_aws_iam,
    notify_github_enterprise, get_approved_access_hours,
    provision_temporary_iam_role, notify_pagerduty, get_termination_event,
    revoke_okta_sso, revoke_aws_iam_access, revoke_github_enterprise_access,
    revoke_google_workspace_access, quarantine_active_sessions,
    transfer_asset_ownership

Tasks use ``employee_id`` (task 001) and ``user_id`` (tasks 002-005)
interchangeably for the subject; :func:`_uid` accepts either.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import structlog

from autobench.backends import _kvstore as kv
from autobench.schema import TaskSpec

log = structlog.get_logger(__name__)

_Handler = Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]]
_SESSION_CHANNELS = ("okta", "aws_iam", "github_enterprise", "google_workspace")


def initialize(db_conn: sqlite3.Connection, task_spec: TaskSpec) -> None:
    kv.initialize_kv(db_conn, task_spec.context.initial_state)


def dispatch(db_conn: sqlite3.Connection, tool_name: str, arguments: dict[str, Any]) -> Any:
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        raise ValueError(f"unknown tool for it_access_provisioning: {tool_name!r}")
    result = handler(db_conn, arguments)
    log.debug("it_dispatch", tool=tool_name, arguments=arguments, result=result)
    return result


def _uid(args: dict[str, Any]) -> Any:
    return args.get("user_id") if args.get("user_id") is not None else args.get("employee_id")


def _add_minutes(iso_ts: str, minutes: int) -> str:
    try:
        base = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return iso_ts
    return (base + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------- handlers


def _get_department_provisioning_config(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    dept = args.get("department")
    config = kv.load_dict(db, "department_provisioning_config")
    entry = config.get(dept)
    return {"department": dept, **(entry if isinstance(entry, dict) else {})}


def _provision_google_workspace_email(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    uid = _uid(args)
    patch: dict[str, Any] = {"email": args.get("email")}
    if args.get("full_name") is not None:
        patch["full_name"] = args["full_name"]
    kv.patch_item(db, "google_workspace_accounts", uid, patch)
    return {"employee_id": uid, "email": args.get("email"), "provisioned": True}


def _add_okta_group(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    uid = _uid(args)
    group = args.get("group")
    memberships = kv.load_dict(db, "okta_group_memberships")
    groups = list(memberships.get(uid, []))
    if group not in groups:
        groups.append(group)
    memberships[uid] = groups
    kv.save(db, "okta_group_memberships", memberships)
    return {"user_id": uid, "group": group, "added": True, "groups": groups}


def _remove_okta_group(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    uid = _uid(args)
    group = args.get("group")
    memberships = kv.load_dict(db, "okta_group_memberships")
    groups = [g for g in memberships.get(uid, []) if g != group]
    memberships[uid] = groups
    kv.save(db, "okta_group_memberships", memberships)
    return {"user_id": uid, "group": group, "removed": True, "groups": groups}


def _post_slack_message(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"channel": args.get("channel"), "employee_id": _uid(args)}
    kv.append(db, "slack_messages", entry)
    return {"channel": args.get("channel"), "posted": True}


def _get_access_review_report(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    report = kv.load_dict(db, "access_review_report")
    if report:
        return report
    return {"report_id": args.get("report_id"), "decisions": []}


def _revoke_oauth_tokens(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    uid = _uid(args)
    app = args.get("app")
    tokens_by_user = kv.load_dict(db, "oauth_tokens")
    user_tokens = list(tokens_by_user.get(uid, []))
    revoked = 0
    for token in user_tokens:
        if isinstance(token, dict) and token.get("app") == app:
            token["status"] = "revoked"
            revoked += 1
    tokens_by_user[uid] = user_tokens
    kv.save(db, "oauth_tokens", tokens_by_user)
    return {"user_id": uid, "app": app, "revoked": revoked}


def _log_security_audit_event(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    event = dict(args)
    kv.append(db, "security_audit_log", event)
    return {"logged": True, "event": event}


def _get_role_change_event(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    event = kv.load_dict(db, "role_change_event")
    return event if event else {"user_id": _uid(args)}


def _update_workday_job_title(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    uid = _uid(args)
    title = args.get("job_title")
    kv.patch_item(db, "workday_profiles", uid, {"job_title": title})
    return {"user_id": uid, "job_title": title, "updated": True}


def _notify_aws_iam(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"user_id": _uid(args)}
    if args.get("new_role") is not None:
        entry["new_role"] = args["new_role"]
    kv.append(db, "aws_iam_notifications", entry)
    return {"notified": True, **entry}


def _notify_github_enterprise(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"user_id": _uid(args)}
    if args.get("new_role") is not None:
        entry["new_role"] = args["new_role"]
    kv.append(db, "github_enterprise_notifications", entry)
    return {"notified": True, **entry}


def _get_approved_access_hours(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    return {"approved_access_hours_utc": kv.load(db, "approved_access_hours_utc", None)}


def _provision_temporary_iam_role(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    uid = _uid(args)
    account = args.get("account_id")
    try:
        duration = int(args.get("duration_minutes", 60))
    except (TypeError, ValueError):
        duration = 60
    expires_at = _add_minutes(kv.now(db), duration)
    entry = {
        "user_id": uid,
        "account_id": account,
        "role": "temporary-elevated",
        "expires_at": expires_at,
    }
    kv.append(db, "iam_role_grants", entry)
    return {"granted": True, **entry}


def _notify_pagerduty(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    entry = {"request_id": args.get("request_id"), "team": args.get("team", "security")}
    kv.append(db, "pagerduty_notifications", entry)
    return {"notified": True, **entry}


def _get_termination_event(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    event = kv.load_dict(db, "termination_event")
    return event if event else {"user_id": _uid(args)}


def _revoke_session_channel(
    db: sqlite3.Connection, args: dict[str, Any], channel: str
) -> dict[str, Any]:
    uid = _uid(args)
    sessions = kv.load_dict(db, "active_sessions")
    sessions[channel] = [
        s for s in sessions.get(channel, []) if not (isinstance(s, dict) and s.get("user_id") == uid)
    ]
    kv.save(db, "active_sessions", sessions)
    return {"user_id": uid, "channel": channel, "revoked": True}


def _revoke_okta_sso(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    return _revoke_session_channel(db, args, "okta")


def _revoke_aws_iam_access(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    return _revoke_session_channel(db, args, "aws_iam")


def _revoke_github_enterprise_access(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    return _revoke_session_channel(db, args, "github_enterprise")


def _revoke_google_workspace_access(
    db: sqlite3.Connection, args: dict[str, Any]
) -> dict[str, Any]:
    return _revoke_session_channel(db, args, "google_workspace")


def _quarantine_active_sessions(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    uid = _uid(args)
    sessions = kv.load_dict(db, "active_sessions")
    for channel in list(sessions.keys()):
        sessions[channel] = [
            s
            for s in sessions.get(channel, [])
            if not (isinstance(s, dict) and s.get("user_id") == uid)
        ]
    kv.save(db, "active_sessions", sessions)
    return {"user_id": uid, "quarantined": True, "channels_cleared": _SESSION_CHANNELS}


def _transfer_asset_ownership(db: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    uid = _uid(args)
    new_owner = args.get("new_owner_id")
    owned = kv.load_dict(db, "owned_assets")
    moving = list(owned.get(uid, []))
    dest = list(owned.get(new_owner, []))
    dest.extend(moving)
    owned[new_owner] = dest
    owned[uid] = []
    kv.save(db, "owned_assets", owned)
    return {"user_id": uid, "new_owner_id": new_owner, "transferred": len(moving)}


_HANDLERS: dict[str, _Handler] = {
    "get_department_provisioning_config": _get_department_provisioning_config,
    "provision_google_workspace_email": _provision_google_workspace_email,
    "add_okta_group": _add_okta_group,
    "post_slack_message": _post_slack_message,
    "get_access_review_report": _get_access_review_report,
    "remove_okta_group": _remove_okta_group,
    "revoke_oauth_tokens": _revoke_oauth_tokens,
    "log_security_audit_event": _log_security_audit_event,
    "get_role_change_event": _get_role_change_event,
    "update_workday_job_title": _update_workday_job_title,
    "notify_aws_iam": _notify_aws_iam,
    "notify_github_enterprise": _notify_github_enterprise,
    "get_approved_access_hours": _get_approved_access_hours,
    "provision_temporary_iam_role": _provision_temporary_iam_role,
    "notify_pagerduty": _notify_pagerduty,
    "get_termination_event": _get_termination_event,
    "revoke_okta_sso": _revoke_okta_sso,
    "revoke_aws_iam_access": _revoke_aws_iam_access,
    "revoke_github_enterprise_access": _revoke_github_enterprise_access,
    "revoke_google_workspace_access": _revoke_google_workspace_access,
    "quarantine_active_sessions": _quarantine_active_sessions,
    "transfer_asset_ownership": _transfer_asset_ownership,
}

