from django.urls import path

from apps.accounts.views.auth_views import MeView
from apps.catalog.views.admin_views import (
    AdminCategoryViewSet,
    AdminOptionGroupViewSet,
    AdminProductViewSet,
)

urlpatterns = [
    path("me/", MeView.as_view(), name="admin-me"),
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
        AdminProductViewSet.as_view({"delete": "delete_image"}),
        name="admin-product-image-delete",
    ),
    path(
        "option-groups/",
        AdminOptionGroupViewSet.as_view({"get": "list", "post": "create"}),
        name="admin-option-groups",
    ),
    path(
        "option-groups/<uuid:pk>/",
        AdminOptionGroupViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="admin-option-group-detail",
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
]
