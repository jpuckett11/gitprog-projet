"""Workspace bundle: dependencies shared by every UI mode.

Avoids passing many separate args into each widget constructor. Built once in
MainWindow after sign-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gitget.api import GraphQLClient, RestClient
from gitget.auth import storage
from gitget.auth.session import AuthSession
from gitget.bridge import WebhookBridge
from gitget.config import Settings
from gitget.polling import PollingEngine
from gitget.tunnel import CloudflareTunnel


@dataclass(slots=True)
class Workspace:
    settings: Settings
    session: AuthSession
    rest: RestClient
    graphql: GraphQLClient
    poller: PollingEngine
    bridge: WebhookBridge | None = field(default=None)
    tunnel: CloudflareTunnel | None = field(default=None)

    @classmethod
    def build(cls, settings: Settings) -> Workspace:
        session = AuthSession(settings)
        token_provider = session.user_token_provider()
        rest = RestClient(settings, token_provider)
        graphql = GraphQLClient(settings, token_provider)
        poller = PollingEngine()

        bridge: WebhookBridge | None = None
        tunnel: CloudflareTunnel | None = None

        sub_token = storage.load_subscriber_token() or ""
        if settings.webhook_mode == "remote" and settings.webhook_remote_url and sub_token:
            bridge = WebhookBridge(settings.webhook_remote_url, sub_token)
        elif settings.webhook_mode == "tunnel":
            tunnel = CloudflareTunnel(
                local_port=8765,
                cloudflared_path=settings.cloudflared_path,
            )

        return cls(
            settings=settings,
            session=session,
            rest=rest,
            graphql=graphql,
            poller=poller,
            bridge=bridge,
            tunnel=tunnel,
        )

    async def aclose(self) -> None:
        self.poller.stop()
        if self.bridge is not None:
            self.bridge.stop()
        if self.tunnel is not None:
            self.tunnel.stop()
        await self.rest.aclose()
        await self.graphql.aclose()
