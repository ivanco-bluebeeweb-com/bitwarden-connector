"""Value-add reports for Bitwarden Connector -- org health overview and
recent admin/security activity, same "aggregate raw records into one
glance" shape as every other connector's handlers_reports.py this session.
"""
from __future__ import annotations

import datetime as _dt

from imperal_sdk import ActionResult

import bitwarden_client as bc
from app import chat
from handlers_connection import resolve_or_error
from schemas import (
    AuditOrgHealthParams, OrgHealthReport, MemberStatusSummary,
    GetRecentAdminActivityParams, AdminActivityReport, AdminActivityEntry,
)

_STATUS_LABELS = {0: "Invited", 1: "Accepted", 2: "Confirmed", 3: "Revoked"}


@chat.function(
    "audit_org_health",
    "Build one aggregated health report for the connected Bitwarden organization: member count by status, "
    "members without two-factor enabled, group and collection counts.",
    action_type="read", chain_callable=True, data_model=OrgHealthReport,
)
async def audit_org_health(ctx, params: AuditOrgHealthParams) -> ActionResult:
    """Scan members/groups/collections and summarize organization health."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        members_resp = await bc.request(ctx, conn, "GET", "/public/members", action="list members for audit")
        groups_resp = await bc.request(ctx, conn, "GET", "/public/groups", action="list groups for audit")
        collections_resp = await bc.request(ctx, conn, "GET", "/public/collections", action="list collections for audit")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    members = members_resp.get("data", []) if isinstance(members_resp, dict) else []
    groups = groups_resp.get("data", []) if isinstance(groups_resp, dict) else []
    collections = collections_resp.get("data", []) if isinstance(collections_resp, dict) else []
    by_status: dict[str, int] = {}
    two_fa_disabled = 0
    for m in members:
        label = _STATUS_LABELS.get(m.get("status", 0), "Unknown")
        by_status[label] = by_status.get(label, 0) + 1
        if not m.get("twoFactorEnabled", False):
            two_fa_disabled += 1
    return ActionResult.ok(OrgHealthReport(
        total_members=len(members),
        by_status=[MemberStatusSummary(status_label=k, count=v) for k, v in by_status.items()],
        two_factor_disabled_count=two_fa_disabled,
        total_groups=len(groups),
        total_collections=len(collections),
    ))


@chat.function(
    "get_recent_admin_activity",
    "Value-add report: read the connected Bitwarden organization's event log for the last N days -- a quick "
    "way to spot recent member/collection/policy changes without paging through the raw log.",
    action_type="read", chain_callable=True, data_model=AdminActivityReport,
)
async def get_recent_admin_activity(ctx, params: GetRecentAdminActivityParams) -> ActionResult:
    """Summarize the last N days of member/collection/policy changes as one report."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    start = (_dt.datetime.utcnow() - _dt.timedelta(days=params.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        resp = await bc.request(ctx, conn, "GET", "/public/events", params={"start": start}, action="list events for report")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    data = resp.get("data", []) if isinstance(resp, dict) else []
    entries = [
        AdminActivityEntry(type=e.get("type", 0), date=e.get("date", ""), acting_user_id=e.get("actingUserId") or "")
        for e in data
    ]
    return ActionResult.ok(AdminActivityReport(days=params.days, event_count=len(entries), entries=entries))
