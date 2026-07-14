from django.urls import path

from apps.catalog.views.public_views import (
    PublicCategoryListView,
    PublicProductCompositionView,
    PublicProductDetailView,
    PublicProductListView,
)

urlpatterns = [
    path("categories/", PublicCategoryListView.as_view(), name="public-catalog-categories"),
    path("products/", PublicProductListView.as_view(), name="public-catalog-products"),
    path(
        "products/<slug:slug>/composition/",
        PublicProductCompositionView.as_view(),
        name="public-catalog-product-composition",
    ),
    path("products/<slug:slug>/", PublicProductDetailView.as_view(), name="public-catalog-product-detail"),
]
