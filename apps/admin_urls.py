from django.urls import path

from apps.accounts.views.auth_views import MeView
from apps.catalog.views.admin_views import (
    AdminCategoryViewSet,
    AdminOptionGroupViewSet,
    AdminProductViewSet,
)
from apps.companies.views.admin_views import (
    AdminDashboardView,
    AdminLogoUploadView,
    AdminSettingsView,
)
from apps.customers.views.admin_views import AdminCustomerDetailView, AdminCustomerListView
from apps.orders.views.admin_views import AdminOrderViewSet

urlpatterns = [
    path("me/", MeView.as_view(), name="admin-me"),
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("settings/", AdminSettingsView.as_view(), name="admin-settings"),
    path("settings/logo/", AdminLogoUploadView.as_view(), name="admin-settings-logo"),
    path(
        "orders/",
        AdminOrderViewSet.as_view({"get": "list"}),
        name="admin-orders",
    ),
    path(
        "orders/<uuid:pk>/",
        AdminOrderViewSet.as_view({"get": "retrieve"}),
        name="admin-order-detail",
    ),
    path(
        "orders/<uuid:pk>/status/",
        AdminOrderViewSet.as_view({"patch": "update_status"}),
        name="admin-order-status",
    ),
    path(
        "orders/<uuid:pk>/payment/",
        AdminOrderViewSet.as_view({"patch": "update_payment"}),
        name="admin-order-payment",
    ),
    path(
        "categories/",
        AdminCategoryViewSet.as_view({"get": "list", "post": "create"}),
        name="admin-categories",
    ),
    path(
        "categories/<uuid:pk>/",
        AdminCategoryViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="admin-category-detail",
    ),
    path(
        "products/",
        AdminProductViewSet.as_view({"get": "list", "post": "create"}),
        name="admin-products",
    ),
    path(
        "products/<uuid:pk>/",
        AdminProductViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            },
        ),
        name="admin-product-detail",
    ),
    path(
        "products/<uuid:pk>/images/",
        AdminProductViewSet.as_view({"post": "upload_image"}),
        name="admin-product-images",
    ),
    path(
        "products/<uuid:pk>/images/<uuid:image_id>/",
        AdminProductViewSet.as_view({"patch": "update_image", "delete": "delete_image"}),
        name="admin-product-image-detail",
    ),
    path(
        "products/<uuid:pk>/option-groups/reorder/",
        AdminProductViewSet.as_view({"patch": "reorder_option_groups"}),
        name="admin-product-option-groups-reorder",
    ),
    path(
        "option-groups/",
        AdminOptionGroupViewSet.as_view({"get": "list", "post": "create", "patch": "reorder_groups"}),
        name="admin-option-groups",
    ),
    path(
        "option-groups/<uuid:pk>/",
        AdminOptionGroupViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            },
        ),
        name="admin-option-group-detail",
    ),
    path(
        "option-groups/<uuid:pk>/duplicate/",
        AdminOptionGroupViewSet.as_view({"post": "duplicate_group"}),
        name="admin-option-group-duplicate",
    ),
    path(
        "option-groups/<uuid:pk>/options/reorder/",
        AdminOptionGroupViewSet.as_view({"patch": "reorder_options"}),
        name="admin-option-group-options-reorder",
    ),
    path(
        "option-groups/<uuid:pk>/options/",
        AdminOptionGroupViewSet.as_view({"post": "create_option"}),
        name="admin-option-group-options",
    ),
    path(
        "option-groups/<uuid:pk>/options/<uuid:option_id>/",
        AdminOptionGroupViewSet.as_view({"patch": "manage_option", "delete": "manage_option"}),
        name="admin-option-group-option-detail",
    ),
    path(
        "option-groups/<uuid:pk>/options/<uuid:option_id>/duplicate/",
        AdminOptionGroupViewSet.as_view({"post": "duplicate_option"}),
        name="admin-option-group-option-duplicate",
    ),
    path("customers/", AdminCustomerListView.as_view(), name="admin-customers"),
    path("customers/<uuid:customer_id>/", AdminCustomerDetailView.as_view(), name="admin-customer-detail"),
]
