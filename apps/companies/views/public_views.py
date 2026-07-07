from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import BusinessHours
from apps.companies.services.settings_service import SettingsService
from apps.companies.services.store_hours_service import StoreHoursService
from core.tenancy.context import TenantContext

DAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


class PublicCompanyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tenant = TenantContext.get()
        if tenant is None:
            raise Http404("Estabelecimento não encontrado") from None

        settings = SettingsService.get_for_tenant(tenant)
        hours = BusinessHours.all_objects.filter(tenant=tenant).order_by("day_of_week")

        return Response(
            {
                "id": str(tenant.id),
                "trade_name": tenant.trade_name,
                "slug": tenant.slug,
                "description": tenant.description,
                "logo_url": tenant.logo_url,
                "cover_url": tenant.cover_url,
                "phone": tenant.phone,
                "is_open": StoreHoursService.is_store_open(tenant),
                "settings": {
                    "min_order_value": float(settings.min_order_value),
                    "delivery_fee": float(settings.delivery_fee),
                    "free_delivery_above": (
                        float(settings.free_delivery_above)
                        if settings.free_delivery_above is not None
                        else None
                    ),
                    "estimated_prep_time": settings.estimated_prep_time,
                    "estimated_delivery_time": settings.estimated_delivery_time,
                    "accepts_delivery": settings.accepts_delivery,
                    "accepts_pickup": settings.accepts_pickup,
                    "payment_methods": settings.payment_methods,
                },
                "business_hours": [
                    {
                        "day_of_week": row.day_of_week,
                        "day_name": DAY_NAMES[row.day_of_week],
                        "opens_at": row.opens_at.strftime("%H:%M"),
                        "closes_at": row.closes_at.strftime("%H:%M"),
                        "is_closed": row.is_closed,
                    }
                    for row in hours
                ],
                "theme": settings.theme,
            }
        )
