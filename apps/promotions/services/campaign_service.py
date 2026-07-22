from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.catalog.models import Product
from apps.companies.models import Company
from apps.promotions.domain.enums import (
    CampaignMechanism,
    CampaignStatus,
    CommercialGoal,
    RecurrenceType,
)
from apps.promotions.domain.exceptions import InvalidCampaignError
from apps.promotions.models import Campaign
from core.utils.money import round_money


class CampaignService:
    @staticmethod
    @transaction.atomic
    def create(*, tenant: Company, data: dict) -> Campaign:
        mechanism = data.get("mechanism", CampaignMechanism.PRODUCT_PRICE)
        if mechanism != CampaignMechanism.PRODUCT_PRICE:
            raise InvalidCampaignError("Nesta versão só dá pra criar promoção de preço de produto")

        product_id = data.get("product_id")
        if not product_id:
            raise InvalidCampaignError("Escolha um produto")

        try:
            product = Product.objects.get(id=product_id, tenant=tenant)
        except Product.DoesNotExist as exc:
            raise InvalidCampaignError("Produto não encontrado") from exc

        promo_price = round_money(Decimal(str(data["promo_price"])))
        if promo_price <= 0:
            raise InvalidCampaignError("O preço promocional precisa ser maior que zero")
        if promo_price >= Decimal(product.base_price):
            raise InvalidCampaignError("O novo preço precisa ser menor que o preço atual do produto")

        reference = round_money(Decimal(product.base_price))
        recurrence = data.get("recurrence_type", RecurrenceType.ONCE)
        weekdays = data.get("weekdays") or []
        if recurrence == RecurrenceType.WEEKDAYS and not weekdays:
            raise InvalidCampaignError("Escolha pelo menos um dia da semana")

        starts_at = data.get("starts_at") or timezone.now()
        if isinstance(starts_at, str):
            starts_at = parse_datetime(starts_at) or timezone.now()

        ends_at = data.get("ends_at")
        if isinstance(ends_at, str):
            ends_at = parse_datetime(ends_at)

        if ends_at is not None and ends_at <= starts_at:
            raise InvalidCampaignError("A data de término precisa ser depois do início")

        title = (data.get("title") or "").strip() or f"{product.name} em oferta"

        link_only = bool(data.get("link_only", False))
        campaign = Campaign.all_objects.create(
            tenant=tenant,
            commercial_goal=data.get("commercial_goal", CommercialGoal.INCREASE_SALES),
            mechanism=CampaignMechanism.PRODUCT_PRICE,
            status=data.get("status", CampaignStatus.ACTIVE),
            title=title,
            product=product,
            promo_price=promo_price,
            reference_price=reference,
            recurrence_type=recurrence,
            weekdays=[int(d) for d in weekdays],
            starts_at=starts_at,
            ends_at=ends_at,
            show_on_home=False if link_only else bool(data.get("show_on_home", True)),
            show_on_menu=False if link_only else bool(data.get("show_on_menu", True)),
            show_on_product=bool(data.get("show_on_product", True)),
            link_only=link_only,
            show_as_banner=bool(data.get("show_as_banner", False)),
        )
        return campaign

    @staticmethod
    @transaction.atomic
    def update(*, campaign: Campaign, data: dict) -> Campaign:
        if "status" in data:
            status = data["status"]
            if status not in CampaignStatus.values:
                raise InvalidCampaignError("Status inválido")
            campaign.status = status

        if "promo_price" in data and data["promo_price"] is not None:
            promo = round_money(Decimal(str(data["promo_price"])))
            ref = Decimal(campaign.reference_price or 0)
            if promo <= 0 or (ref and promo >= ref):
                raise InvalidCampaignError("O novo preço precisa ser menor que o preço de referência")
            campaign.promo_price = promo

        for field in (
            "title",
            "show_on_home",
            "show_on_menu",
            "show_on_product",
            "link_only",
            "show_as_banner",
            "recurrence_type",
            "weekdays",
            "starts_at",
            "ends_at",
            "commercial_goal",
        ):
            if field not in data:
                continue
            value = data[field]
            if field in ("starts_at", "ends_at") and isinstance(value, str):
                value = parse_datetime(value)
            if field == "weekdays" and value is not None:
                value = [int(d) for d in value]
            setattr(campaign, field, value)

        if campaign.link_only:
            campaign.show_on_home = False
            campaign.show_on_menu = False

        campaign.save()
        return campaign

    @staticmethod
    def pause(campaign: Campaign) -> Campaign:
        return CampaignService.update(campaign=campaign, data={"status": CampaignStatus.PAUSED})

    @staticmethod
    def activate(campaign: Campaign) -> Campaign:
        return CampaignService.update(campaign=campaign, data={"status": CampaignStatus.ACTIVE})
