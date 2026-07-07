from django.urls import include, path

urlpatterns = [
    path("company/", include("apps.companies.public_urls")),
    path("catalog/", include("apps.catalog.public_urls")),
    path("orders/", include("apps.orders.public_urls")),
]
