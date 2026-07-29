from django.urls import path

from apps.locations.views import PublicCityListView, PublicStateListView

urlpatterns = [
    path("states/", PublicStateListView.as_view(), name="public-states"),
    path("cities/", PublicCityListView.as_view(), name="public-cities"),
]
