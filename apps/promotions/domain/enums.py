from django.db import models


class CommercialGoal(models.TextChoices):
    INCREASE_SALES = "increase_sales", "Aumentar vendas"
    RAISE_TICKET = "raise_ticket", "Aumentar ticket"
    ATTRACT_NEW = "attract_new", "Atrair novos clientes"
    BRING_BACK = "bring_back", "Trazer clientes de volta"
    SELL_CATEGORY = "sell_category", "Vender mais de uma categoria"
    ENCOURAGE_COMBO = "encourage_combo", "Incentivar combos"
    ORDER_THRESHOLD = "order_threshold", "Pedidos acima de um valor"


class CampaignMechanism(models.TextChoices):
    PRODUCT_PRICE = "product_price", "Preço de produto"
    # futuros
    BUNDLE = "bundle", "Combo"
    FREE_SHIPPING = "free_shipping", "Frete grátis"
    GIFT = "gift", "Brinde"
    ORDER_DISCOUNT = "order_discount", "Desconto no pedido"


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    ACTIVE = "active", "Ativa"
    PAUSED = "paused", "Pausada"
    ENDED = "ended", "Encerrada"


class RecurrenceType(models.TextChoices):
    ONCE = "once", "Apenas uma vez"
    DAILY = "daily", "Todos os dias"
    WEEKDAYS = "weekdays", "Dias da semana"
    HOURS = "hours", "Horários"
    COMMEMORATIVE = "commemorative", "Datas comemorativas"
