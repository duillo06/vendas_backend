from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.catalog.models import Category, Option, OptionGroup, Product
from apps.catalog.selectors.catalog_selector import ProductImageService
from apps.catalog.serializers.admin_serializers import (
    CategoryAdminSerializer,
    OptionAdminSerializer,
    OptionGroupAdminSerializer,
    ProductAdminDetailSerializer,
    ProductAdminListSerializer,
    ProductImageSerializer,
)
from apps.catalog.services.option_group_service import OptionGroupService
from apps.catalog.services.product_service import CategoryService, ProductService
from core.exceptions.domain import DomainException
from core.permissions.rbac import HasPermission


class AdminCatalogMixin:
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get_tenant(self):
        return self.request.user.employee.tenant


class AdminCategoryViewSet(AdminCatalogMixin, viewsets.ViewSet):
    def list(self, request):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        categories = Category.objects.filter().order_by("sort_order", "name")
        return Response(CategoryAdminSerializer(categories, many=True).data)

    def create(self, request):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = CategoryAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = CategoryService.create(tenant=self.get_tenant(), data=serializer.validated_data)
        return Response(CategoryAdminSerializer(category).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        category = Category.objects.get(pk=pk)
        serializer = CategoryAdminSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = CategoryService.update(category=category, data=serializer.validated_data)
        return Response(CategoryAdminSerializer(category).data)

    def destroy(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        category = Category.objects.get(pk=pk)
        try:
            CategoryService.soft_delete(category)
        except DomainException as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminProductViewSet(AdminCatalogMixin, viewsets.ViewSet):
    def list(self, request):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        qs = Product.all_objects.filter(tenant=self.get_tenant(), deleted_at__isnull=True)
        qs = qs.select_related("category").prefetch_related("images")

        if category := request.query_params.get("category"):
            qs = qs.filter(category__slug=category)
        if request.query_params.get("is_active") is not None:
            qs = qs.filter(is_active=request.query_params.get("is_active") == "true")
        if request.query_params.get("is_available") is not None:
            qs = qs.filter(is_available=request.query_params.get("is_available") == "true")
        if search := request.query_params.get("search"):
            qs = qs.filter(name__icontains=search)

        from core.pagination import StandardPagination

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs.order_by("sort_order", "name"), request)
        return paginator.get_paginated_response(ProductAdminListSerializer(page, many=True).data)

    def create(self, request):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = ProductAdminDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductService.create(tenant=self.get_tenant(), data=serializer.validated_data)
        product = Product.all_objects.prefetch_related("images", "product_option_groups").get(
            id=product.id,
        )
        return Response(ProductAdminDetailSerializer(product).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.prefetch_related(
            "images",
            "product_option_groups",
        ).get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        return Response(ProductAdminDetailSerializer(product).data)

    def partial_update(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        serializer = ProductAdminDetailSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = ProductService.update(product=product, data=serializer.validated_data)
        product = Product.all_objects.prefetch_related("images", "product_option_groups").get(
            id=product.id,
        )
        return Response(ProductAdminDetailSerializer(product).data)

    def destroy(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        ProductService.soft_delete(product)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="images")
    def upload_image(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Campo image é obrigatório"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            image = ProductImageService.add_image(
                product=product,
                image_file=image_file,
                alt_text=request.data.get("alt_text", ""),
                is_primary=str(request.data.get("is_primary", "")).lower() == "true",
            )
        except DomainException as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(ProductImageSerializer(image).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>[^/.]+)")
    def delete_image(self, request, pk=None, image_id=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        ProductImageService.delete_image(product=product, image_id=image_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminOptionGroupViewSet(AdminCatalogMixin, viewsets.ViewSet):
    def list(self, request):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        groups = OptionGroup.objects.prefetch_related("options").order_by("sort_order", "name")
        return Response(OptionGroupAdminSerializer(groups, many=True).data)

    def create(self, request):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = OptionGroupAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = OptionGroupService.create(tenant=self.get_tenant(), data=serializer.validated_data)
        return Response(OptionGroupAdminSerializer(group).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.prefetch_related("options").get(pk=pk)
        return Response(OptionGroupAdminSerializer(group).data)

    def partial_update(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.get(pk=pk)
        serializer = OptionGroupAdminSerializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        group = OptionGroupService.update(group=group, data=serializer.validated_data)
        return Response(OptionGroupAdminSerializer(group).data)

    def destroy(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.get(pk=pk, tenant=self.get_tenant())
        OptionGroupService.delete(group)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="options")
    def create_option(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.get(pk=pk)
        serializer = OptionAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        option = OptionGroupService.create_option(group=group, data=serializer.validated_data)
        return Response(OptionAdminSerializer(option).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"options/(?P<option_id>[^/.]+)",
    )
    def manage_option(self, request, pk=None, option_id=None):
        group = OptionGroup.objects.get(pk=pk)
        option = Option.objects.get(pk=option_id, option_group=group)

        if request.method == "DELETE":
            if not HasPermission("catalog.manage").has_permission(request, self):
                return Response(status=status.HTTP_403_FORBIDDEN)
            OptionGroupService.delete_option(option)
            return Response(status=status.HTTP_204_NO_CONTENT)

        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = OptionAdminSerializer(option, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        option = OptionGroupService.update_option(option=option, data=serializer.validated_data)
        return Response(OptionAdminSerializer(option).data)
