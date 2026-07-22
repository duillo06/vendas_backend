from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ValidationResult:
    ok: bool
    error_code: str | None = None


@dataclass
class ProvisionResult:
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QrPayload:
    image_base64: str | None = None
    code: str | None = None
    expires_at: str | None = None


@dataclass
class SessionStatus:
    state: str  # connected | disconnected | pending_qr | error
    phone_e164: str | None = None
    raw_state: str | None = None


@dataclass
class SendResult:
    provider_message_id: str | None = None
    accepted: bool = True


@dataclass
class ProviderEvent:
    kind: str  # qr_updated | connection_update | message_ack | provider_error
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionContext:
    """dados que o adapter precisa pra falar com o vendor"""

    connection_id: str
    tenant_id: str
    base_url: str
    api_key: str
    instance_name: str
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    webhook_url: str | None = None


class WhatsAppProvider(Protocol):
    provider_key: str

    def validate_credentials(self, *, base_url: str, api_key: str) -> ValidationResult: ...

    def provision(self, ctx: ConnectionContext) -> ProvisionResult: ...

    def get_qr(self, ctx: ConnectionContext) -> QrPayload | None: ...

    def get_session_status(self, ctx: ConnectionContext) -> SessionStatus: ...

    def send_text(self, ctx: ConnectionContext, *, to_e164: str, body: str) -> SendResult: ...

    def disconnect(self, ctx: ConnectionContext) -> None: ...

    def parse_webhook(self, headers: dict, raw_body: bytes) -> list[ProviderEvent]: ...
