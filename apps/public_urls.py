from django.urls import include, path

from apps.companies.views.geo_views import PublicGeoReverseView
from apps.orders.views.table_public_views import (
    PublicTableByNumberView,
    PublicTableByTokenView,
)

urlpatterns = [
    path("company/", include("apps.companies.public_urls")),
    path("geo/reverse/", PublicGeoReverseView.as_view(), name="public-geo-reverse"),
    path("locations/", include("apps.locations.urls")),
    path("catalog/", include("apps.catalog.public_urls")),
    path("orders/", include("apps.orders.public_urls")),
    path(
        "tables/by-number/<str:number>/",
        PublicTableByNumberView.as_view(),
        name="public-table-by-number",
    ),
    path("tables/<str:qr_token>/", PublicTableByTokenView.as_view(), name="public-table"),
    path("account/", include("apps.customers.account_urls")),
    path("promotions/", include("apps.promotions.public_urls")),
]
