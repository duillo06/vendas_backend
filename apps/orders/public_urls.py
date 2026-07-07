from django.urls import path

from apps.orders.views.public_views import CheckoutView, PublicOrderDetailView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="public-order-checkout"),
    path("<uuid:order_id>/", PublicOrderDetailView.as_view(), name="public-order-detail"),
]
