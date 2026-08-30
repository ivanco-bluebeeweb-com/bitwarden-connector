"""Panel UI -- connections list/connect form + the one required "App
settings" entry point, same shape as 1Password Connector's panels.py
(corrected UI kwargs: ui.Input uses param_name not name; ui.Form uses
action not on_submit; ui.Stack/ui.Form do not accept full_width).

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule. Disconnect lives only in the
"App settings" screen (panels_settings.py). The one secondary "App
settings" button is always the LAST element at the bottom of the sidebar.

PER ~/UI_INTERFACE_STANDARD.md (2026-08-21 addendum): every Input carries
its own visible label, the placeholder text is always contextually
specific, the form's own container is stretched to the full width of the
left sidebar, and the form's inner content is stretched to fill that
container. The "How do I set this up?" instructions live ONLY in the help
modal below -- never duplicated as static sidebar text.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers_connection as h


def _settings_button() -> ui.UINode:
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__bitwarden_settings"),
    )


def _connection_row(c: dict) -> ui.UINode:
    label = c.get("label") or "Bitwarden organization"
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(label, variant="body"),
        ui.Text(f"{c.get('member_count', 0)} member(s)", variant="caption"),
    ])


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return ui.Text("No Bitwarden organizations connected yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, children=children)


def _help_modal() -> ui.UINode:
    return ui.Modal(
        trigger=ui.Button("How do I set this up?", variant="ghost", size="sm", full_width=True),
        title="Connecting Bitwarden",
        children=[
            ui.Text(
                "In your Bitwarden web vault, go to Settings > Organizations > (your org) > "
                "Settings > My Organization > API Key. Generate/view your organization's client_id "
                "(format organization.{uuid}) and client_secret, then paste both here.",
                variant="body",
            ),
            ui.Text(
                "This connects the Bitwarden Public (organization-management) API -- members, "
                "collections, groups, policies, and event logs. It does not read or expose individual "
                "vault item passwords.",
                variant="caption",
            ),
        ],
    )


@ext.panel("bitwarden_connect", slot="left", title="Bitwarden")
async def bitwarden_connect_panel(ctx, **kwargs) -> object:
    connections = await h._load_connections(ctx)
    return ui.Stack(direction="v", gap=3, children=[
        ui.Text("Bitwarden", variant="heading"),
        _connections_section(connections),
        ui.Divider(),
        ui.Form(
            submit_label="Connect",
            action=ui.Call("connect_bitwarden"),
            children=[
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Label", variant="label"),
                    ui.Input(param_name="label", placeholder="e.g. Acme Corp"),
                ]),
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Client ID", variant="label"),
                    ui.Input(param_name="client_id", placeholder="organization.00000000-0000-0000-0000-000000000000"),
                ]),
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Client secret", variant="label"),
                    ui.Input(param_name="client_secret", placeholder="Client secret from the API Key screen"),
                ]),
            ],
        ),
        _help_modal(),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("bitwarden_connect_help", slot="overlay", title="How do I set this up?")
async def bitwarden_connect_help(ctx, **kwargs) -> object:
    return ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. Sign in to the Bitwarden web vault and open your organization."),
        ui.Text("2. Go to Settings > My Organization > API Key and generate/view the organization's "
                "client_id (format organization.{uuid}) and client_secret."),
        ui.Text("3. Paste both values into the form on the left, then click Connect."),
        ui.Text("This connects the Public (organization-management) API only -- members, collections, "
                "groups, policies and event logs. Individual vault item passwords are never read."),
    ])
