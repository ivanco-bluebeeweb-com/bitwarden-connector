"""Members, Collections, Groups, Policies, Event logs for Bitwarden Connector.

Confirmed against bitwarden.com/help/public-api, 2026-08-29:
GET /public/members, POST /public/members, GET/PUT/DELETE /public/members/{id},
POST /public/members/{id}/reinvite,
GET /public/collections, GET/PUT/DELETE /public/collections/{id},
GET /public/groups, POST /public/groups, GET/PUT/DELETE /public/groups/{id},
GET /public/policies, GET/PUT /public/policies/{type},
GET /public/events.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import bitwarden_client as bc
from app import chat
from handlers_connection import resolve_or_error
from schemas import (
    ListMembersParams, MemberList, Member,
    GetMemberParams,
    InviteMemberParams,
    UpdateMemberParams,
    RemoveMemberParams, DeleteResult,
    ReinviteMemberParams,
    ListCollectionsParams, CollectionList, Collection,
    GetCollectionParams,
    DeleteCollectionParams,
    ListGroupsParams, GroupList, Group,
    GetGroupParams,
    CreateGroupParams,
    DeleteGroupParams,
    ListPoliciesParams, PolicyList, Policy,
    GetPolicyParams,
    UpdatePolicyParams,
    ListEventsParams, EventList, EventEntry,
)

_STATUS_LABELS = {0: "Invited", 1: "Accepted", 2: "Confirmed", 3: "Revoked"}


def _member_entity(m: dict) -> Member:
    status = m.get("status", 0)
    return Member(
        id=m.get("id", ""), email=m.get("email", ""), name=m.get("name") or "",
        status=status, status_label=_STATUS_LABELS.get(status, "Unknown"),
        type=m.get("type", 0), two_factor_enabled=m.get("twoFactorEnabled", False),
        external_id=m.get("externalId") or "",
    )


@chat.function(
    "list_members",
    "List members of the connected Bitwarden organization.",
    action_type="read", chain_callable=True, data_model=MemberList,
)
async def list_members(ctx, params: ListMembersParams) -> ActionResult:
    """List organization members (name, email, status, two-factor state) from the Public API."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await bc.request(ctx, conn, "GET", "/public/members", action="list members")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    data = resp.get("data", []) if isinstance(resp, dict) else []
    return ActionResult.success(MemberList(members=[_member_entity(m) for m in data]), summary="Members listed.")


@chat.function(
    "get_member",
    "Read one Bitwarden organization member in full by id.",
    action_type="read", chain_callable=True, data_model=Member,
)
async def get_member(ctx, params: GetMemberParams) -> ActionResult:
    """Read one organization member in full by member id."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        m = await bc.request(ctx, conn, "GET", f"/public/members/{params.member_id}", action="get member")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_member_entity(m), summary="Member retrieved.")


@chat.function(
    "invite_member",
    "Invite a new member to the connected Bitwarden organization by email.",
    action_type="write", event="bitwarden-connector.invite_member", effects=['create:resource'], chain_callable=True, data_model=Member,
)
async def invite_member(ctx, params: InviteMemberParams) -> ActionResult:
    """Invite a new member to the organization by email with a given type and optional access rules."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"type": params.type, "email": params.email, "accessAll": False,
             "collections": [{"id": cid, "readOnly": False} for cid in params.collection_ids]}
    if params.external_id:
        body["externalId"] = params.external_id
    try:
        m = await bc.request(ctx, conn, "POST", "/public/members", json_body=body, action="invite member")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_member_entity(m), summary="Invite member done.")


@chat.function(
    "update_member",
    "Update selected fields of an existing Bitwarden member (type and/or external_id). Only given fields change.",
    action_type="write", event="bitwarden-connector.update_member", effects=['update:resource'], chain_callable=True, data_model=Member,
)
async def update_member(ctx, params: UpdateMemberParams) -> ActionResult:
    """Update an existing member's type or external_id; only supplied fields change."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        current = await bc.request(ctx, conn, "GET", f"/public/members/{params.member_id}", action="get member for update")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    body = {
        "type": params.type if params.type >= 0 else current.get("type", 2),
        "externalId": params.external_id or current.get("externalId") or "",
        "accessAll": current.get("accessAll", False),
        "collections": current.get("collections", []),
    }
    try:
        m = await bc.request(ctx, conn, "PUT", f"/public/members/{params.member_id}", json_body=body, action="update member")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_member_entity(m), summary="Member updated.")


@chat.function(
    "remove_member",
    "Permanently remove a member from the connected Bitwarden organization. Cannot be undone.",
    action_type="write", event="bitwarden-connector.remove_member", effects=['delete:resource'], chain_callable=True, data_model=DeleteResult,
)
async def remove_member(ctx, params: RemoveMemberParams) -> ActionResult:
    """Permanently remove a member from the organization. Cannot be undone."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await bc.request(ctx, conn, "DELETE", f"/public/members/{params.member_id}", action="remove member")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(DeleteResult(deleted=True, id=params.member_id), summary="Member deleted.")


@chat.function(
    "reinvite_member",
    "Resend the invitation email to a member stuck in Invited status.",
    action_type="write", event="bitwarden-connector.reinvite_member", effects=['update:resource'], chain_callable=True, data_model=DeleteResult,
)
async def reinvite_member(ctx, params: ReinviteMemberParams) -> ActionResult:
    """Resend the invitation email to a member still in Invited status."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await bc.request(ctx, conn, "POST", f"/public/members/{params.member_id}/reinvite", action="reinvite member")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(DeleteResult(deleted=False, id=params.member_id), summary="Reinvite member done.")


def _collection_entity(c: dict) -> Collection:
    return Collection(id=c.get("id", ""), name=c.get("name", ""), external_id=c.get("externalId") or "")


@chat.function(
    "list_collections",
    "List collections (shared folders of vault items) configured in the connected Bitwarden organization.",
    action_type="read", chain_callable=True, data_model=CollectionList,
)
async def list_collections(ctx, params: ListCollectionsParams) -> ActionResult:
    """List collections (shared folders of vault items) configured in the organization."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await bc.request(ctx, conn, "GET", "/public/collections", action="list collections")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    data = resp.get("data", []) if isinstance(resp, dict) else []
    return ActionResult.success(CollectionList(collections=[_collection_entity(c) for c in data]), summary="Collections listed.")


@chat.function(
    "get_collection",
    "Read one Bitwarden collection in full by id.",
    action_type="read", chain_callable=True, data_model=Collection,
)
async def get_collection(ctx, params: GetCollectionParams) -> ActionResult:
    """Read one collection in full by id."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        c = await bc.request(ctx, conn, "GET", f"/public/collections/{params.collection_id}", action="get collection")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_collection_entity(c), summary="Collection retrieved.")


@chat.function(
    "delete_collection",
    "Permanently delete a Bitwarden collection. Items inside are not deleted, only unshared. Cannot be undone.",
    action_type="write", event="bitwarden-connector.delete_collection", effects=['delete:resource'], chain_callable=True, data_model=DeleteResult,
)
async def delete_collection(ctx, params: DeleteCollectionParams) -> ActionResult:
    """Permanently delete a collection; items inside are not deleted, only unlinked."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await bc.request(ctx, conn, "DELETE", f"/public/collections/{params.collection_id}", action="delete collection")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(DeleteResult(deleted=True, id=params.collection_id), summary="Collection deleted.")


def _group_entity(g: dict) -> Group:
    return Group(id=g.get("id", ""), name=g.get("name", ""), access_all=g.get("accessAll", False), external_id=g.get("externalId") or "")


@chat.function(
    "list_groups",
    "List groups (named collections of members) configured in the connected Bitwarden organization.",
    action_type="read", chain_callable=True, data_model=GroupList,
)
async def list_groups(ctx, params: ListGroupsParams) -> ActionResult:
    """List groups (named collections of members) configured in the organization."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await bc.request(ctx, conn, "GET", "/public/groups", action="list groups")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    data = resp.get("data", []) if isinstance(resp, dict) else []
    return ActionResult.success(GroupList(groups=[_group_entity(g) for g in data]), summary="Groups listed.")


@chat.function(
    "get_group",
    "Read one Bitwarden group in full by id.",
    action_type="read", chain_callable=True, data_model=Group,
)
async def get_group(ctx, params: GetGroupParams) -> ActionResult:
    """Read one group in full by id."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        g = await bc.request(ctx, conn, "GET", f"/public/groups/{params.group_id}", action="get group")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_group_entity(g), summary="Group retrieved.")


@chat.function(
    "create_group",
    "Create a new group on the connected Bitwarden organization.",
    action_type="write", event="bitwarden-connector.create_group", effects=['create:resource'], chain_callable=True, data_model=Group,
)
async def create_group(ctx, params: CreateGroupParams) -> ActionResult:
    """Create a new group with an explicit name and member/collection assignments."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"name": params.name, "accessAll": params.access_all, "collections": [],
            "externalId": params.external_id or ""}
    try:
        g = await bc.request(ctx, conn, "POST", "/public/groups", json_body=body, action="create group")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_group_entity(g), summary="Group created.")


@chat.function(
    "delete_group",
    "Permanently delete a Bitwarden group. Members keep their individual access; only the group is removed. "
    "Cannot be undone.",
    action_type="write", event="bitwarden-connector.delete_group", effects=['delete:resource'], chain_callable=True, data_model=DeleteResult,
)
async def delete_group(ctx, params: DeleteGroupParams) -> ActionResult:
    """Permanently delete a group; members keep their individual access."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await bc.request(ctx, conn, "DELETE", f"/public/groups/{params.group_id}", action="delete group")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(DeleteResult(deleted=True, id=params.group_id), summary="Group deleted.")


def _policy_entity(p: dict) -> Policy:
    return Policy(type=p.get("type", 0), enabled=p.get("enabled", False), data=p.get("data") or {})


@chat.function(
    "list_policies",
    "List organization policies (security/compliance rules, e.g. master password requirements, 2FA "
    "enforcement) configured in the connected Bitwarden organization.",
    action_type="read", chain_callable=True, data_model=PolicyList,
)
async def list_policies(ctx, params: ListPoliciesParams) -> ActionResult:
    """List organization policies (security/compliance rules) and their enabled state."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await bc.request(ctx, conn, "GET", "/public/policies", action="list policies")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    data = resp.get("data", []) if isinstance(resp, dict) else []
    return ActionResult.success(PolicyList(policies=[_policy_entity(p) for p in data]), summary="Policies listed.")


@chat.function(
    "get_policy",
    "Read one Bitwarden organization policy in full by its type id.",
    action_type="read", chain_callable=True, data_model=Policy,
)
async def get_policy(ctx, params: GetPolicyParams) -> ActionResult:
    """Read one policy in full by its policy type id."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        p = await bc.request(ctx, conn, "GET", f"/public/policies/{params.policy_type}", action="get policy")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_policy_entity(p), summary="Policy retrieved.")


@chat.function(
    "update_policy",
    "Turn a Bitwarden organization policy on/off and set its configuration data. Only given fields change.",
    action_type="write", event="bitwarden-connector.update_policy", effects=['update:resource'], chain_callable=True, data_model=Policy,
)
async def update_policy(ctx, params: UpdatePolicyParams) -> ActionResult:
    """Turn a policy on/off and set its configuration data; only supplied fields change."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"enabled": params.enabled, "data": params.data}
    try:
        p = await bc.request(ctx, conn, "PUT", f"/public/policies/{params.policy_type}", json_body=body, action="update policy")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    return ActionResult.success(_policy_entity(p), summary="Policy updated.")


def _event_entity(e: dict) -> EventEntry:
    return EventEntry(
        type=e.get("type", 0), date=e.get("date", ""),
        acting_user_id=e.get("actingUserId") or "", item_id=e.get("itemId") or "",
        ip_address=e.get("ipAddress") or "",
    )


@chat.function(
    "list_events",
    "List event log entries (the audit trail of member/collection/policy changes) for the connected "
    "Bitwarden organization, optionally filtered by date range and/or acting member.",
    action_type="read", chain_callable=True, data_model=EventList,
)
async def list_events(ctx, params: ListEventsParams) -> ActionResult:
    """Read the organization event log (audit trail) over an explicit date range."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query: dict = {}
    if params.start:
        query["start"] = params.start
    if params.end:
        query["end"] = params.end
    if params.actingUserId:
        query["actingUserId"] = params.actingUserId
    try:
        resp = await bc.request(ctx, conn, "GET", "/public/events", params=query, action="list events")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    data = resp.get("data", []) if isinstance(resp, dict) else []
    return ActionResult.success(EventList(events=[_event_entity(e) for e in data]), summary="Events listed.")
