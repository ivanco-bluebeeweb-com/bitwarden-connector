"""Connection lifecycle: connect (OAuth2 client_credentials token exchange
+ verify against /public/members), list, disconnect.

Same "secrets-store list of dicts" shape as every other BYOK connector
this session's handlers_connection.py.
"""
from __future__ import annotations

import json
import uuid

from imperal_sdk import ActionResult

import bitwarden_client as bc
from app import chat
from schemas import (
    ConnectBitwardenParams, ConnectBitwardenResult,
    DisconnectBitwardenParams, DeleteResult,
    BitwardenConnection, ConnectionList, ListConnectionsParams,
)

_CONNECTIONS_SECRET = "bitwarden_connections"


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_CONNECTIONS_SECRET)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_CONNECTIONS_SECRET, json.dumps(connections))


async def resolve_connection(ctx, connection_id: str = "") -> dict | None:
    connections = await _load_connections(ctx)
    if not connections:
        return None
    if connection_id:
        return next((c for c in connections if c.get("id") == connection_id), None)
    return connections[0]


async def resolve_or_error(ctx, connection_id: str = ""):
    conn = await resolve_connection(ctx, connection_id)
    if not conn:
        return None, ActionResult.error(
            "No Bitwarden organization found. Connect one with connect_bitwarden first.",
            code=bc.BW_NOT_CONNECTED,
        )
    return conn, None


async def _persist_conn(ctx, conn: dict) -> None:
    connections = await _load_connections(ctx)
    for i, c in enumerate(connections):
        if c.get("id") == conn.get("id"):
            connections[i] = conn
            await _save_connections(ctx, connections)
            return
    connections.append(conn)
    await _save_connections(ctx, connections)


def _connection_to_entity(c: dict) -> BitwardenConnection:
    return BitwardenConnection(
        id=c.get("id", ""), label=c.get("label") or "Bitwarden organization",
        member_count=c.get("member_count", 0),
    )


@chat.function(
    "connect_bitwarden",
    "Connect your own Bitwarden organization by saving its Public API client_id/client_secret, after "
    "checking they actually work.",
    action_type="write", event="bitwarden-connector.connect_bitwarden", effects=['create:resource'], chain_callable=True, data_model=ConnectBitwardenResult,
)
async def connect_bitwarden(ctx, params: ConnectBitwardenParams) -> ActionResult:
    """Exchange client_id/client_secret for an access token, verify against /public/members, then save."""
    conn = {
        "id": str(uuid.uuid4()),
        "label": params.label or "Bitwarden organization",
        "client_id": params.client_id,
        "client_secret": params.client_secret,
        "access_token": "",
        "token_expires_at": 0,
        "member_count": 0,
    }
    try:
        await bc.ensure_fresh_token(ctx, conn)
        members = await bc.request(ctx, conn, "GET", "/public/members", action="verify connection")
    except bc.ClientFail as exc:
        return ActionResult.error(exc.payload["message"], code=exc.payload["code"])
    data = members.get("data", []) if isinstance(members, dict) else []
    conn["member_count"] = len(data)
    await _persist_conn(ctx, conn)
    return ActionResult.ok(ConnectBitwardenResult(
        connection_id=conn["id"], label=conn["label"], member_count=conn["member_count"],
    ))


@chat.function(
    "disconnect_bitwarden",
    "Disconnect a Bitwarden organization: deletes the saved client_id/client_secret. Nothing in Bitwarden "
    "itself is changed.",
    action_type="write", event="bitwarden-connector.disconnect_bitwarden", effects=['delete:resource'], chain_callable=True, data_model=DeleteResult,
)
async def disconnect_bitwarden(ctx, params: DisconnectBitwardenParams) -> ActionResult:
    """Delete a saved Bitwarden connection by id; nothing in Bitwarden itself changes."""
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.error("Connection not found.", code=bc.BW_NOT_FOUND)
    await _save_connections(ctx, remaining)
    return ActionResult.ok(DeleteResult(deleted=True, id=params.connection_id))


@chat.function(
    "list_connections",
    "List the connected Bitwarden organizations.",
    action_type="read", chain_callable=True, data_model=ConnectionList,
)
async def list_connections(ctx, params: ListConnectionsParams) -> ActionResult:
    """List saved Bitwarden organization connections."""
    connections = await _load_connections(ctx)
    return ActionResult.ok(ConnectionList(connections=[_connection_to_entity(c) for c in connections]))
