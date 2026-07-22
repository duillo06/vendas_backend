"""adapter fake — testes sem rede"""

from __future__ import annotations

from apps.communications.domain.ports import (
    ConnectionContext,
    ProviderEvent,
    ProvisionResult,
    QrPayload,
    SendResult,
    SessionStatus,
    ValidationResult,
)


class FakeWhatsAppAdapter:
    provider_key = "fake"

    def __init__(self):
        self.connected = False
        self.sent: list[tuple[str, str]] = []
        self.qr = "data:image/png;base64,fakeqr"

    def validate_credentials(self, *, base_url: str, api_key: str) -> ValidationResult:
        if not base_url or not api_key:
            return ValidationResult(ok=False, error_code="credentials_invalid")
        if api_key == "bad":
            return ValidationResult(ok=False, error_code="credentials_invalid")
        return ValidationResult(ok=True)

    def provision(self, ctx: ConnectionContext) -> ProvisionResult:
        return ProvisionResult(provider_metadata={"instance_name": ctx.instance_name})

    def get_qr(self, ctx: ConnectionContext) -> QrPayload | None:
        if self.connected:
            return None
        return QrPayload(image_base64=self.qr)

    def get_session_status(self, ctx: ConnectionContext) -> SessionStatus:
        if self.connected:
            return SessionStatus(state="connected", phone_e164="5531999999999")
        return SessionStatus(state="pending_qr")

    def send_text(self, ctx: ConnectionContext, *, to_e164: str, body: str) -> SendResult:
        self.sent.append((to_e164, body))
        return SendResult(provider_message_id="fake-1", accepted=True)

    def disconnect(self, ctx: ConnectionContext) -> None:
        self.connected = False

    def parse_webhook(self, headers: dict, raw_body: bytes) -> list[ProviderEvent]:
        return []

    def simulate_connect(self) -> None:
        self.connected = True
