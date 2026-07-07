from django.db import models


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    CONFIRMED = "confirmed", "Confirmado"
    PREPARING = "preparing", "Em preparo"
    READY = "ready", "Pronto"
    OUT_FOR_DELIVERY = "out_for_delivery", "Saiu para entrega"
    COMPLETED = "completed", "Concluído"
    CANCELLED = "cancelled", "Cancelado"


VALID_TRANSITIONS: dict[str, list[str]] = {
    OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
    OrderStatus.CONFIRMED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
    OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
    OrderStatus.READY: [
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED,
    ],
    OrderStatus.OUT_FOR_DELIVERY: [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
    OrderStatus.COMPLETED: [],
    OrderStatus.CANCELLED: [],
}


class DeliveryType(models.TextChoices):
    DELIVERY = "delivery", "Entrega"
    PICKUP = "pickup", "Retirada"
    DINE_IN = "dine_in", "No local"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Dinheiro"
    PIX = "pix", "PIX"
    CARD_ON_DELIVERY = "card_on_delivery", "Cartão na entrega"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    PAID = "paid", "Pago"
    FAILED = "failed", "Falhou"
    REFUNDED = "refunded", "Estornado"


class OrderSource(models.TextChoices):
    STOREFRONT = "storefront", "Storefront"
    BACKOFFICE = "backoffice", "Backoffice"
    API = "api", "API"
