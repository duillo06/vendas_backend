from django.urls import path

from apps.promotions.views.public_views import PublicOffersView

urlpatterns = [
    path("offers/", PublicOffersView.as_view(), name="public-promotion-offers"),
]
