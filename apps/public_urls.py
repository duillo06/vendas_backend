from django.urls import include, path

urlpatterns = [
    path("catalog/", include("apps.catalog.public_urls")),
]
