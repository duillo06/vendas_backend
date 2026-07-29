from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.services import LocationCatalogService


class PublicStateListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        states = LocationCatalogService.list_states()
        return Response(
            [{"id": state.id, "name": state.name, "acronym": state.acronym} for state in states]
        )


class PublicCityListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        state_id = request.query_params.get("state_id")
        state_acronym = request.query_params.get("state", "")
        try:
            parsed_state_id = int(state_id) if state_id else None
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Estado inválido"}},
                status=400,
            )

        cities = LocationCatalogService.list_cities(
            state_id=parsed_state_id,
            state_acronym=state_acronym,
        )
        return Response(
            [
                {
                    "id": city.id,
                    "name": city.name,
                    "state_id": city.state_id,
                    "state": city.state.acronym,
                }
                for city in cities
            ]
        )
