"""Thin HTTP client for the Bitwarden Public API + OAuth2 client_credentials.

Same "fail()-dict + ClientFail exception + generic request() helper"
shape as every other connector this session's *_client.py. Confirmed
against bitwarden.com/help/public-api and contributing.bitwarden.com/
architecture/deep-dives/authentication, 2026-08-29:

- Token endpoint: https://identity.bitwarden.com/connect/token
  (grant_type=client_credentials, scope=api.organization,
  client_id=organization.{uuid}, client_secret=...).
- API base: https://api.bitwarden.com
- Resources: /public/members, /public/collections, /public/groups,
  /public/events, /public/policies.
- Access tokens are short-lived (~1 hour) -- ensure_fresh_token()
  proactively refreshes near expiry, same pattern as every other
  client-credentials connector this session.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

TOKEN_URL = "https://identity.bitwarden.com/connect/token"
API_BASE = "https://api.bitwarden.com"

BW_NOT_CONNECTED = "BITWARDEN_NOT_CONNECTED"
BW_UNAUTHORIZED = "BITWARDEN_UNAUTHORIZED"
BW_FORBIDDEN = "BITWARDEN_FORBIDDEN"
BW_NOT_FOUND = "BITWARDEN_NOT_FOUND"
BW_RATE_LIMITED = "BITWARDEN_RATE_LIMITED"
BW_BACKEND_ERROR = "BITWARDEN_BACKEND_ERROR"
BW_VALIDATION_FAILED = "BITWARDEN_VALIDATION_FAILED"
BW_RESPONSE_UNEXPECTED = "BITWARDEN_RESPONSE_UNEXPECTED"

_MESSAGES = {
    BW_NOT_CONNECTED: "No Bitwarden organization connected. Connect one first.",
    BW_UNAUTHORIZED: "Bitwarden rejected the client credentials as invalid or expired.",
    BW_FORBIDDEN: "Bitwarden denied access to this organization resource.",
    BW_NOT_FOUND: "That Bitwarden record was not found.",
    BW_RATE_LIMITED: "Bitwarden rate-limited this request. Try again shortly.",
    BW_BACKEND_ERROR: "Bitwarden returned an error.",
    BW_VALIDATION_FAILED: "Bitwarden rejected the request as invalid.",
    BW_RESPONSE_UNEXPECTED: "Bitwarden returned an unexpected response shape.",
}


class ClientFail(Exception):
    def __init__(self, payload: dict):
        self.payload = payload
        super().__init__(payload.get("message", "Bitwarden request failed"))


def fail(code: str, detail: str = "") -> dict:
    msg = _MESSAGES.get(code, "Bitwarden request failed.")
    if detail:
        msg = f"{msg} ({detail})"
    return {"ok": False, "code": code, "message": msg}


def parse_fields_json(fields_json: str) -> dict | None:
    try:
        data = json.loads(fields_json)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


async def exchange_client_credentials(ctx, client_id: str, client_secret: str) -> dict:
    """Exchange client_id/client_secret for an access token via OAuth2 client_credentials."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "scope": "api.organization",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code == 400 or resp.status_code == 401:
        raise ClientFail(fail(BW_UNAUTHORIZED, "token exchange"))
    if resp.status_code >= 400:
        raise ClientFail(fail(BW_BACKEND_ERROR, f"token exchange: HTTP {resp.status_code}"))
    try:
        return resp.json()
    except ValueError:
        raise ClientFail(fail(BW_RESPONSE_UNEXPECTED, "token exchange: non-JSON response"))


async def ensure_fresh_token(ctx, conn: dict) -> dict:
    """Proactively refresh the access_token if it's within 60s of expiry."""
    expires_at = conn.get("expires_at", 0)
    if time.time() < expires_at - 60:
        return conn
    result = await exchange_client_credentials(ctx, conn["client_id"], conn["client_secret"])
    conn["access_token"] = result["access_token"]
    conn["expires_at"] = time.time() + result.get("expires_in", 3600)
    return conn


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def _check_status(resp: httpx.Response, action: str) -> Any:
    if resp.status_code == 401:
        raise ClientFail(fail(BW_UNAUTHORIZED, action))
    if resp.status_code == 403:
        raise ClientFail(fail(BW_FORBIDDEN, action))
    if resp.status_code == 404:
        raise ClientFail(fail(BW_NOT_FOUND, action))
    if resp.status_code == 429:
        raise ClientFail(fail(BW_RATE_LIMITED, action))
    if resp.status_code == 422 or resp.status_code == 400:
        raise ClientFail(fail(BW_VALIDATION_FAILED, f"{action}: {resp.text[:300]}"))
    if resp.status_code >= 500:
        raise ClientFail(fail(BW_BACKEND_ERROR, f"{action}: HTTP {resp.status_code}"))
    if resp.status_code >= 400:
        raise ClientFail(fail(BW_BACKEND_ERROR, f"{action}: HTTP {resp.status_code} {resp.text[:300]}"))
    if not resp.content:
        return {}
    try:
        return resp.json()
    except ValueError:
        raise ClientFail(fail(BW_RESPONSE_UNEXPECTED, f"{action}: non-JSON response"))


async def request(ctx, conn: dict, method: str, path: str, *, params: dict | None = None,
                   json_body: Any = None, action: str = "request") -> Any:
    access_token = conn.get("access_token", "")
    if not access_token:
        raise ClientFail(fail(BW_NOT_CONNECTED))
    url = f"{API_BASE}{path}"
    headers = _headers(access_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, url, headers=headers, params=params, json=json_body)
    return _check_status(resp, action)
