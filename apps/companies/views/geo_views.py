from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.services.geo_service import GeoService


class PublicGeoReverseView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat", ""))
            lng = float(request.query_params.get("lng", ""))
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Informe lat e lng"}},
                status=400,
            )

        result = GeoService.reverse(lat=lat, lng=lng)
        return Response(result)
