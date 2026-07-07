from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.catalog.selectors.catalog_selector import CatalogSelector
from apps.catalog.serializers.public_serializers import (
    CategoryPublicSerializer,
    ProductDetailPublicSerializer,
    ProductListPublicSerializer,
)
from core.pagination import StandardPagination
from core.tenancy.context import TenantContext


class PublicCatalogMixin:
    def get_tenant(self):
        return TenantContext.get()


class PublicCategoryListView(PublicCatalogMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tenant = self.get_tenant()
        categories = CatalogSelector.get_categories(tenant.id)
        data = CategoryPublicSerializer(categories, many=True).data
        return Response(data)


class PublicProductListView(PublicCatalogMixin, APIView):
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get(self, request):
        qs = CatalogSelector.get_active_products(
            category_slug=request.query_params.get("category"),
            search=request.query_params.get("search"),
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductListPublicSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PublicProductDetailView(PublicCatalogMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        tenant = self.get_tenant()
        try:
            product = CatalogSelector.get_product_detail(tenant_id=tenant.id, slug=slug)
        except Product.DoesNotExist:
            raise Http404("Produto não encontrado") from None

        return Response(ProductDetailPublicSerializer(product).data)
