"""Pydantic param/result models for Bitwarden Connector.

Same "explicit ConnectionScoped mixin + one params + one result class per
@chat.function" shape as every other connector this session's schemas.py.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ConnectionScoped(BaseModel):
    connection_id: str = Field("", description="Which saved Bitwarden organization to use. Omit if only one is connected.")


# ── Connection lifecycle ────────────────────────────────────────────────

class ConnectBitwardenParams(BaseModel):
    label: str = Field("", description="A friendly name for this organization, e.g. 'Acme Corp'.")
    client_id: str = Field(description="Organization API client_id, format organization.{uuid} (Settings > My Organization > API Key).")
    client_secret: str = Field(description="Organization API client_secret from the same API Key screen.")


class ConnectBitwardenResult(BaseModel):
    connection_id: str = ""
    label: str = ""
    member_count: int = 0


class DisconnectBitwardenParams(BaseModel):
    connection_id: str = Field(description="The connection id to disconnect, from list_connections.")


class DeleteResult(BaseModel):
    deleted: bool = False
    id: str = ""


class BitwardenConnection(BaseModel):
    id: str = ""
    label: str = ""
    member_count: int = 0


class ConnectionList(BaseModel):
    connections: list[BitwardenConnection] = Field(default_factory=list)


class ListConnectionsParams(BaseModel):
    pass


# ── Members ──────────────────────────────────────────────────────────────

class ListMembersParams(ConnectionScoped):
    pass


class Member(BaseModel):
    id: str = ""
    email: str = ""
    name: str = ""
    status: int = 0
    status_label: str = ""
    type: int = 0
    two_factor_enabled: bool = False
    external_id: str = ""


class MemberList(BaseModel):
    members: list[Member] = Field(default_factory=list)


class GetMemberParams(ConnectionScoped):
    member_id: str = Field(description="The member's Bitwarden id, from list_members.")


class InviteMemberParams(ConnectionScoped):
    email: str = Field(description="Email address to invite.")
    type: int = Field(2, description="Bitwarden member type: 0=Owner, 1=Admin, 2=User, 3=Manager, 4=Custom.")
    external_id: str = Field("", description="Optional external id (e.g. from your HR/IdP system) to correlate this member.")
    collection_ids: list[str] = Field(default_factory=list, description="Collection ids to grant access to on invite (optional).")


class UpdateMemberParams(ConnectionScoped):
    member_id: str = Field(description="The member's Bitwarden id, from list_members.")
    type: int = Field(-1, description="New Bitwarden member type (0=Owner..4=Custom). -1 = leave unchanged.")
    external_id: str = Field("", description="New external id. Empty = leave unchanged.")


class RemoveMemberParams(ConnectionScoped):
    member_id: str = Field(description="The member's Bitwarden id, from list_members.")


class ReinviteMemberParams(ConnectionScoped):
    member_id: str = Field(description="The member's Bitwarden id, from list_members.")


# ── Collections ──────────────────────────────────────────────────────────

class ListCollectionsParams(ConnectionScoped):
    pass


class Collection(BaseModel):
    id: str = ""
    name: str = ""
    external_id: str = ""


class CollectionList(BaseModel):
    collections: list[Collection] = Field(default_factory=list)


class GetCollectionParams(ConnectionScoped):
    collection_id: str = Field(description="The collection's Bitwarden id, from list_collections.")


class DeleteCollectionParams(ConnectionScoped):
    collection_id: str = Field(description="The collection's Bitwarden id, from list_collections.")


# ── Groups ───────────────────────────────────────────────────────────────

class ListGroupsParams(ConnectionScoped):
    pass


class Group(BaseModel):
    id: str = ""
    name: str = ""
    external_id: str = ""


class GroupList(BaseModel):
    groups: list[Group] = Field(default_factory=list)


class GetGroupParams(ConnectionScoped):
    group_id: str = Field(description="The group's Bitwarden id, from list_groups.")


class CreateGroupParams(ConnectionScoped):
    name: str = Field(description="Name for the new group, e.g. 'Engineering'.")
    external_id: str = Field("", description="Optional external id to correlate this group with your IdP/HR system.")
    collection_ids: list[str] = Field(default_factory=list, description="Collection ids this group should have access to.")


class DeleteGroupParams(ConnectionScoped):
    group_id: str = Field(description="The group's Bitwarden id, from list_groups.")


class ListGroupMembersParams(ConnectionScoped):
    group_id: str = Field(description="The group's Bitwarden id, from list_groups.")


class GroupMemberList(BaseModel):
    member_ids: list[str] = Field(default_factory=list)


class UpdateGroupMembersParams(ConnectionScoped):
    group_id: str = Field(description="The group's Bitwarden id, from list_groups.")
    member_ids: list[str] = Field(description="Full replacement list of member ids for this group.")


# ── Policies ─────────────────────────────────────────────────────────────

class ListPoliciesParams(ConnectionScoped):
    pass


class Policy(BaseModel):
    id: str = ""
    type: int = 0
    enabled: bool = False
    data: dict = Field(default_factory=dict)


class PolicyList(BaseModel):
    policies: list[Policy] = Field(default_factory=list)


class GetPolicyParams(ConnectionScoped):
    policy_type: int = Field(description="Policy type id, from list_policies.")


class UpdatePolicyParams(ConnectionScoped):
    policy_type: int = Field(description="Policy type id, from list_policies.")
    enabled: bool = Field(description="Turn this policy on or off.")
    data: dict = Field(default_factory=dict, description="Policy-specific configuration data (varies by policy type).")


# ── Event logs ───────────────────────────────────────────────────────────

class ListEventsParams(ConnectionScoped):
    start: str = Field("", description="ISO 8601 start date/time to filter events from (optional).")
    end: str = Field("", description="ISO 8601 end date/time to filter events to (optional).")
    actingUserId: str = Field("", description="Filter to events performed by this member id (optional).")


class EventEntry(BaseModel):
    type: int = 0
    date: str = ""
    acting_user_id: str = ""
    item_id: str = ""
    ip_address: str = ""


class EventList(BaseModel):
    events: list[EventEntry] = Field(default_factory=list)


# ── Reports ──────────────────────────────────────────────────────────────

class AuditOrgHealthParams(ConnectionScoped):
    pass


class MemberStatusSummary(BaseModel):
    status_label: str = ""
    count: int = 0


class OrgHealthReport(BaseModel):
    total_members: int = 0
    by_status: list[MemberStatusSummary] = Field(default_factory=list)
    two_factor_disabled_count: int = 0
    total_groups: int = 0
    total_collections: int = 0


class GetRecentAdminActivityParams(ConnectionScoped):
    days: int = Field(7, description="Look back this many days for admin/security-relevant events.")


class AdminActivityEntry(BaseModel):
    type: int = 0
    date: str = ""
    acting_user_id: str = ""


class AdminActivityReport(BaseModel):
    days: int = 0
    event_count: int = 0
    entries: list[AdminActivityEntry] = Field(default_factory=list)
