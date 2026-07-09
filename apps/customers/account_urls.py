from django.urls import path

from apps.customers.views.account_views import (
    AccountAddressDetailView,
    AccountAddressListView,
    AccountMeView,
    AccountOrderDetailView,
    AccountOrderListView,
)

urlpatterns = [
    path("me/", AccountMeView.as_view(), name="account-me"),
    path("orders/", AccountOrderListView.as_view(), name="account-orders"),
    path("orders/<uuid:order_id>/", AccountOrderDetailView.as_view(), name="account-order-detail"),
    path("addresses/", AccountAddressListView.as_view(), name="account-addresses"),
    path(
        "addresses/<uuid:address_id>/",
        AccountAddressDetailView.as_view(),
        name="account-address-detail",
    ),
]
