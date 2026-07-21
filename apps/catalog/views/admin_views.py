from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.catalog.models import Category, Option, OptionGroup, Product, ProductImage
from apps.catalog.selectors.catalog_selector import ProductImageService
from apps.catalog.serializers.admin_serializers import (
    CategoryAdminSerializer,
    CategoryRecipeWriteSerializer,
    OptionAdminSerializer,
    OptionGroupAdminSerializer,
    ProductAdminDetailSerializer,
    ProductAdminListSerializer,
    ProductImageSerializer,
)
from apps.catalog.services.category_recipe_service import (
    CategoryRecipeError,
    CategoryRecipeService,
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

    def recipe(self, request, pk=None):
        category = Category.objects.get(pk=pk)

        if request.method == "GET":
            if not HasPermission("catalog.view").has_permission(request, self):
                return Response(status=status.HTTP_403_FORBIDDEN)
            return Response(CategoryRecipeService.get(category))

        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = CategoryRecipeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recipe = CategoryRecipeService.replace(
                category,
                data=serializer.validated_data,
            )
        except CategoryRecipeError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(recipe)


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
        product = Product.all_objects.select_related("composition").prefetch_related(
            "images",
            "product_option_groups__option_group__options",
            "composition__custom_products",
        ).get(
            id=product.id,
        )
        return Response(
            ProductAdminDetailSerializer(product, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.select_related("composition").prefetch_related(
            "images",
            "product_option_groups__option_group__options",
            "composition__custom_products",
        ).get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        return Response(ProductAdminDetailSerializer(product, context={"request": request}).data)

    def partial_update(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        serializer = ProductAdminDetailSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = ProductService.update(product=product, data=serializer.validated_data)
        product = Product.all_objects.select_related("composition").prefetch_related(
            "images",
            "product_option_groups__option_group__options",
            "composition__custom_products",
        ).get(
            id=product.id,
        )
        return Response(ProductAdminDetailSerializer(product, context={"request": request}).data)

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

    @action(detail=True, methods=["patch"], url_path=r"images/(?P<image_id>[^/.]+)")
    def update_image(self, request, pk=None, image_id=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        is_primary = request.data.get("is_primary")
        if str(is_primary).lower() not in {"true", "1"}:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Apenas is_primary=true é suportado"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            image = ProductImageService.set_primary_image(product=product, image_id=image_id)
        except ProductImage.DoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Imagem não encontrada"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(ProductImageSerializer(image).data)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>[^/.]+)")
    def delete_image(self, request, pk=None, image_id=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        ProductImageService.delete_image(product=product, image_id=image_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="option-groups/reorder")
    def reorder_option_groups(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Campo ids é obrigatório"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = Product.all_objects.get(pk=pk, tenant=self.get_tenant(), deleted_at__isnull=True)
        try:
            OptionGroupService.reorder_product_groups(product=product, ids=ids)
        except ValueError as exc:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminOptionGroupViewSet(AdminCatalogMixin, viewsets.ViewSet):
    def list(self, request):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        groups = OptionGroup.objects.prefetch_related("options").order_by("sort_order", "name")
        return Response(
            OptionGroupAdminSerializer(groups, many=True, context={"request": request}).data,
        )

    def create(self, request):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = OptionGroupAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = OptionGroupService.create(tenant=self.get_tenant(), data=serializer.validated_data)
        return Response(
            OptionGroupAdminSerializer(group, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        if not HasPermission("catalog.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.prefetch_related("options").get(pk=pk)
        return Response(OptionGroupAdminSerializer(group, context={"request": request}).data)

    def partial_update(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.get(pk=pk)
        serializer = OptionGroupAdminSerializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        group = OptionGroupService.update(group=group, data=serializer.validated_data)
        return Response(OptionGroupAdminSerializer(group, context={"request": request}).data)

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
        return Response(OptionAdminSerializer(option, context={"request": request}).data)

    @action(detail=False, methods=["patch"], url_path="reorder")
    def reorder_groups(self, request):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Campo ids é obrigatório"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            OptionGroupService.reorder_groups(tenant=self.get_tenant(), ids=ids)
        except ValueError as exc:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate_group(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.get(pk=pk, tenant=self.get_tenant())
        new_group = OptionGroupService.duplicate_group(group=group)
        new_group = OptionGroup.objects.prefetch_related("options").get(pk=new_group.id)
        return Response(
            OptionGroupAdminSerializer(new_group, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["patch"], url_path="options/reorder")
    def reorder_options(self, request, pk=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Campo ids é obrigatório"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = OptionGroup.objects.get(pk=pk, tenant=self.get_tenant())
        try:
            OptionGroupService.reorder_options(group=group, ids=ids)
        except ValueError as exc:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"options/(?P<option_id>[^/.]+)/duplicate",
    )
    def duplicate_option(self, request, pk=None, option_id=None):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        group = OptionGroup.objects.get(pk=pk, tenant=self.get_tenant())
        option = Option.objects.get(pk=option_id, option_group=group)
        new_option = OptionGroupService.duplicate_option(option=option)
        return Response(
            OptionAdminSerializer(new_option, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
