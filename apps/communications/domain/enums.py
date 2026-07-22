from django.db import models


class Channel(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"


class ProviderKey(models.TextChoices):
    EVOLUTION = "evolution", "Evolution"
    META_CLOUD = "meta_cloud", "Meta Cloud"
    ZAPI = "zapi", "Z-API"
    FAKE = "fake", "Fake (testes)"


class ConnectionRole(models.TextChoices):
    DEFAULT = "default", "Padrão"
    DELIVERY = "delivery", "Delivery"
    FINANCE = "finance", "Financeiro"
    SUPPORT = "support", "Suporte"
    STORE = "store", "Loja física"


class ConnectionStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    AWAITING_QR = "awaiting_qr", "Aguardando QR"
    CONNECTED = "connected", "Conectado"
    DISCONNECTED = "disconnected", "Desconectado"
    ERROR = "error", "Erro"


class DispatchStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    QUEUED = "queued", "Na fila"
    SENT = "sent", "Enviada"
    DELIVERED = "delivered", "Entregue"
    FAILED = "failed", "Falhou"
    TEST = "test", "Teste"


class AlertSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Aviso"
    CRITICAL = "critical", "Crítico"


# situações do assistente pós-conexão (UI humana)
EVENT_ORDER_RECEIVED = "order.received"
EVENT_ORDER_CONFIRMED = "order.confirmed"
EVENT_ORDER_PREPARING = "order.preparing"
EVENT_ORDER_OUT_FOR_DELIVERY = "order.out_for_delivery"
EVENT_ORDER_DELIVERED = "order.delivered"
EVENT_PAYMENT_APPROVED = "payment.approved"
EVENT_PAYMENT_REJECTED = "payment.rejected"

PHASE1_EVENT_KEYS = (
    EVENT_ORDER_RECEIVED,
    EVENT_ORDER_CONFIRMED,
    EVENT_ORDER_PREPARING,
    EVENT_ORDER_OUT_FOR_DELIVERY,
    EVENT_ORDER_DELIVERED,
    EVENT_PAYMENT_APPROVED,
    EVENT_PAYMENT_REJECTED,
)

# order.status → event_key
ORDER_STATUS_TO_EVENT = {
    "pending": EVENT_ORDER_RECEIVED,
    "confirmed": EVENT_ORDER_CONFIRMED,
    "preparing": EVENT_ORDER_PREPARING,
    "out_for_delivery": EVENT_ORDER_OUT_FOR_DELIVERY,
    "completed": EVENT_ORDER_DELIVERED,
}
