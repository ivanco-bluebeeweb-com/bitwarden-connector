"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK, same reasoning as every other connector this session -- the
user's own Bitwarden organization (members, collections, groups, event
logs, policies) is managed via their own organization API credentials.

WHY OAUTH2 CLIENT_CREDENTIALS WITH client_id/client_secret, CONFIRMED
against bitwarden.com/help/public-api, contributing.bitwarden.com/
architecture/deep-dives/authentication, and the public OpenAPI schema
(api-evangelist/bitwarden), 2026-08-29: the Bitwarden Public API is a
SEPARATE, organization-scoped REST surface (members/collections/groups/
event-logs/policies) from the end-user Vault -- it authenticates via
OAuth2 client_credentials against identity.bitwarden.com/connect/token,
using an organization-specific client_id (format `organization.{uuid}`)
and client_secret, both generated in the organization's own admin
console (Settings > My Organization > API Key). This is a DIFFERENT
Bitwarden product from Bitwarden Secrets Manager (its own separate API)
-- this connector targets the Public (organization-management) API,
matching the same "manage the org, not individual vault items" shape as
Okta/Entra ID Connector in this portfolio, not a password-vault-item CRUD
tool like 1Password Connector.

WHY EACH CONNECTION STORES client_id + client_secret + a live access_token
(refreshed on demand), SAME SHAPE AS EVERY OTHER OAUTH2-CLIENT-CREDENTIALS
CONNECTOR THIS SESSION (Databricks/CircleCI-style) -- Bitwarden access
tokens are short-lived (1 hour) so ensure_fresh_token() proactively
refreshes near expiry, same pattern as every other client-credentials
connector.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "bitwarden-connector",
    version="0.1.0",
    display_name="Bitwarden",
    icon="icon.svg",
    capabilities=["bitwarden:read", "bitwarden:write"],
    description=(
        "Connect your own Bitwarden organization (Public API, OAuth2 client_credentials) to manage "
        "members, collections, groups, event logs, and policies -- full read/write plus value-add "
        "organization health and inactive-member reports."
    ),
)

chat = ChatExtension(ext)
