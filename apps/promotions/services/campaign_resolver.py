from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from apps.catalog.models import Product
from apps.promotions.domain.enums import CampaignMechanism, CampaignStatus, RecurrenceType
from apps.promotions.models import Campaign
from core.utils.money import round_money


@dataclass(frozen=True)
class ResolvedOffer:
    campaign: Campaign
    promo_price: Decimal
    reference_price: Decimal
    save_amount: Decimal
    discount_percent: int
    badges: list[str]

    def as_public_dict(self) -> dict:
        return {
            "campaign_id": str(self.campaign.id),
            "promo_price": float(self.promo_price),
            "reference_price": float(self.reference_price),
            "save_amount": float(self.save_amount),
            "discount_percent": self.discount_percent,
            "badges": self.badges,
            "title": self.campaign.title,
            "weight": int(self.campaign.weight or 10),
            "ends_at": self.campaign.ends_at.isoformat() if self.campaign.ends_at else None,
            "show_on_home": self.campaign.show_on_home and not self.campaign.link_only,
            "show_on_menu": self.campaign.show_on_menu and not self.campaign.link_only,
            "show_on_product": self.campaign.show_on_product,
        }


class CampaignResolver:
    """Decide se uma campanha vale agora e monta preço + selos."""

    @staticmethod
    def indicators(reference: Decimal, promo: Decimal) -> tuple[Decimal, int]:
        save = round_money(max(reference - promo, Decimal("0")))
        if reference <= 0:
            return save, 0
        pct = int(round((float(save) / float(reference)) * 100))
        return save, pct

    @staticmethod
    def badges_for(
        *,
        save: Decimal,
        pct: int,
        ends_at: datetime | None,
        now: datetime,
    ) -> list[str]:
        badges = ["Oferta"]
        if pct > 0:
            badges.append(f"−{pct}%")
        if save > 0:
            badges.append(f"Economize R$ {save:.2f}".replace(".", ","))
        if ends_at is not None:
            local_end = timezone.localtime(ends_at)
            local_now = timezone.localtime(now)
            if local_end.date() == local_now.date():
                badges.append("Termina hoje")
            elif (local_end - local_now).total_seconds() <= 6 * 3600 and local_end > local_now:
                badges.append("Últimas horas")
        return badges

    @staticmethod
    def is_eligible(campaign: Campaign, now: datetime | None = None) -> bool:
        now = now or timezone.now()
        if campaign.status != CampaignStatus.ACTIVE:
            return False
        if campaign.starts_at > now:
            return False
        if campaign.ends_at is not None and campaign.ends_at < now:
            return False

        local = timezone.localtime(now)
        rtype = campaign.recurrence_type

        if rtype == RecurrenceType.WEEKDAYS:
            days = campaign.weekdays or []
            if int(local.weekday()) not in [int(d) for d in days]:
                return False

        if rtype == RecurrenceType.HOURS or (
            campaign.time_start is not None and campaign.time_end is not None
        ):
            t = local.time()
            start = campaign.time_start
            end = campaign.time_end
            if start and end:
                if start <= end:
                    if not (start <= t <= end):
                        return False
                else:
                    # atravessa meia-noite
                    if not (t >= start or t <= end):
                        return False

        return True

    @staticmethod
    def resolve_product(product: Product, now: datetime | None = None) -> ResolvedOffer | None:
        now = now or timezone.now()
        qs = (
            Campaign.all_objects.filter(
                tenant_id=product.tenant_id,
                product_id=product.id,
                status=CampaignStatus.ACTIVE,
                mechanism=CampaignMechanism.PRODUCT_PRICE,
            )
            .select_related("product")
            .order_by("promo_price", "-created_at")
        )
        best: Campaign | None = None
        for campaign in qs:
            if CampaignResolver.is_eligible(campaign, now):
                best = campaign
                break
        if best is None or best.promo_price is None or best.reference_price is None:
            return None

        save, pct = CampaignResolver.indicators(best.reference_price, best.promo_price)
        return ResolvedOffer(
            campaign=best,
            promo_price=round_money(best.promo_price),
            reference_price=round_money(best.reference_price),
            save_amount=save,
            discount_percent=pct,
            badges=CampaignResolver.badges_for(
                save=save,
                pct=pct,
                ends_at=best.ends_at,
                now=now,
            ),
        )

    @staticmethod
    def effective_base_price(product: Product, now: datetime | None = None) -> Decimal:
        offer = CampaignResolver.resolve_product(product, now)
        if offer is None:
            return round_money(Decimal(product.base_price))
        return offer.promo_price

    @staticmethod
    def list_home_offers(*, tenant_id, now: datetime | None = None) -> list[ResolvedOffer]:
        """Vitrine: maior weight primeiro; 1 card por produto (empate → menor preço)."""
        now = now or timezone.now()
        qs = (
            Campaign.all_objects.filter(
                tenant_id=tenant_id,
                status=CampaignStatus.ACTIVE,
                mechanism=CampaignMechanism.PRODUCT_PRICE,
                show_on_home=True,
                link_only=False,
            )
            .select_related("product")
            .prefetch_related("product__images")
            .order_by("-weight", "promo_price", "-created_at")
        )
        best_by_product: dict = {}
        for campaign in qs:
            if not CampaignResolver.is_eligible(campaign, now):
                continue
            if campaign.promo_price is None or campaign.reference_price is None:
                continue
            product = campaign.product
            if product is None or not product.is_active or product.deleted_at is not None:
                continue
            if not product.is_available:
                continue

            save, pct = CampaignResolver.indicators(campaign.reference_price, campaign.promo_price)
            offer = ResolvedOffer(
                campaign=campaign,
                promo_price=round_money(campaign.promo_price),
                reference_price=round_money(campaign.reference_price),
                save_amount=save,
                discount_percent=pct,
                badges=CampaignResolver.badges_for(
                    save=save,
                    pct=pct,
                    ends_at=campaign.ends_at,
                    now=now,
                ),
            )
            pid = campaign.product_id
            prev = best_by_product.get(pid)
            if prev is None:
                best_by_product[pid] = offer
                continue
            # vitrine: peso manda; checkout continua com menor preço em resolve_product
            if campaign.weight > prev.campaign.weight:
                best_by_product[pid] = offer
            elif campaign.weight == prev.campaign.weight and offer.promo_price < prev.promo_price:
                best_by_product[pid] = offer

        return sorted(
            best_by_product.values(),
            key=lambda o: (-int(o.campaign.weight or 10), o.promo_price),
        )
