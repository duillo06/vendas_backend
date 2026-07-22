from django.urls import include, path

from apps.companies.views.geo_views import PublicGeoReverseView

urlpatterns = [
    path("company/", include("apps.companies.public_urls")),
    path("geo/reverse/", PublicGeoReverseView.as_view(), name="public-geo-reverse"),
    path("catalog/", include("apps.catalog.public_urls")),
    path("orders/", include("apps.orders.public_urls")),
    path("account/", include("apps.customers.account_urls")),
    path("promotions/", include("apps.promotions.public_urls")),
]
