from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.promotions.serializers import serialize_public_offer
from apps.promotions.services.campaign_resolver import CampaignResolver


class PublicOffersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tenant = request.tenant
        offers = CampaignResolver.list_home_offers(tenant_id=tenant.id)
        return Response(
            [serialize_public_offer(offer, request) for offer in offers],
        )
