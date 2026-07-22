from django.db import models

from apps.communications.domain.enums import (
    AlertSeverity,
    Channel,
    ConnectionRole,
    ConnectionStatus,
    DispatchStatus,
    ProviderKey,
)
from core.models.tenant_model import TenantAwareModel


class CommunicationConnection(TenantAwareModel):
    """uma conexão WhatsApp (ou outro canal) do tenant — Fase 1: um default"""

    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WHATSAPP)
    provider_key = models.CharField(
        max_length=40,
        choices=ProviderKey.choices,
        default=ProviderKey.EVOLUTION,
    )
    role = models.CharField(
        max_length=20,
        choices=ConnectionRole.choices,
        default=ConnectionRole.DEFAULT,
    )
    display_name = models.CharField(max_length=120, blank=True, default="")
    phone_e164 = models.CharField(max_length=20, blank=True, default="")
    phone_display = models.CharField(max_length=30, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.PENDING,
    )
    # signed blob — nunca logar cru
    credentials_signed = models.TextField(blank=True, default="")
    provider_metadata = models.JSONField(default=dict, blank=True)
    last_health_at = models.DateTimeField(null=True, blank=True)
    last_health_status = models.JSONField(default=dict, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        db_table = "communication_connections"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "channel", "role"],
                name="uniq_comm_conn_tenant_channel_role",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "channel", "status"], name="comm_conn_tenant_ch_st"),
        ]

    def __str__(self) -> str:
        return f"{self.channel}/{self.provider_key} ({self.status})"


class SituationSetting(TenantAwareModel):
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WHATSAPP)
    event_key = models.CharField(max_length=60)
    is_enabled = models.BooleanField(default=True)
    connection = models.ForeignKey(
        CommunicationConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="situation_settings",
        db_column="connection_id",
    )

    class Meta:
        db_table = "communication_situation_settings"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "channel", "event_key"],
                name="uniq_comm_situation_tenant_ch_ev",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_key} ({'on' if self.is_enabled else 'off'})"


class MessageTemplate(TenantAwareModel):
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WHATSAPP)
    event_key = models.CharField(max_length=60)
    body = models.TextField()
    is_system_seed = models.BooleanField(default=True)

    class Meta:
        db_table = "message_templates"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "channel", "event_key"],
                name="uniq_msg_tpl_tenant_ch_ev",
            ),
        ]

    def __str__(self) -> str:
        return f"tpl:{self.event_key}"


class MessageDispatch(TenantAwareModel):
    connection = models.ForeignKey(
        CommunicationConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatches",
        db_column="connection_id",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WHATSAPP)
    event_key = models.CharField(max_length=60, blank=True, default="")
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatches",
        db_column="template_id",
    )
    status = models.CharField(
        max_length=20,
        choices=DispatchStatus.choices,
        default=DispatchStatus.PENDING,
    )
    recipient = models.CharField(max_length=40, blank=True, default="")
    body_snapshot = models.TextField(blank=True, default="")
    provider_message_id = models.CharField(max_length=120, blank=True, default="")
    error_code = models.CharField(max_length=40, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(max_length=120, blank=True, default="")
    payload_snapshot = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    is_test = models.BooleanField(default=False)

    class Meta:
        db_table = "message_dispatches"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "created_at"], name="msg_disp_tenant_st_cr"),
            models.Index(fields=["tenant", "idempotency_key"], name="msg_disp_tenant_idem"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_msg_disp_tenant_idem",
            ),
        ]


class MerchantAlert(TenantAwareModel):
    connection = models.ForeignKey(
        CommunicationConnection,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alerts",
        db_column="connection_id",
    )
    kind = models.CharField(max_length=60)
    severity = models.CharField(
        max_length=20,
        choices=AlertSeverity.choices,
        default=AlertSeverity.WARNING,
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    action_hint = models.CharField(max_length=200, blank=True, default="")
    is_read = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merchant_alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "is_read", "created_at"], name="malert_tenant_read_cr"),
        ]
