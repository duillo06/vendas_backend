from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.domain.constants import TOKEN_BLACKLIST_PREFIX
from apps.companies.models import Company
from apps.customers.domain.validators import normalize_phone
from apps.customers.models import Customer


class CustomerAuthService:
    @staticmethod
    def register(
        *,
        tenant: Company,
        phone: str,
        password: str,
        first_name: str,
        last_name: str = "",
        email: str | None = None,
    ) -> dict:
        if len(password) < 8:
            raise ValidationError({"password": "Senha deve ter pelo menos 8 caracteres"})

        normalized_phone = normalize_phone(phone)

        customer = Customer.all_objects.filter(tenant=tenant, phone=normalized_phone).first()
        if customer:
            if customer.password_hash:
                raise ValidationError({"phone": "Telefone já cadastrado. Faça login."})
            customer.set_password(password)
            customer.first_name = first_name.strip()
            customer.last_name = (last_name or "").strip()
            if email:
                customer.email = email
            customer.deleted_at = None
            customer.is_active = True
            customer.save(
                update_fields=[
                    "password_hash",
                    "first_name",
                    "last_name",
                    "email",
                    "deleted_at",
                    "is_active",
                    "updated_at",
                ],
            )
        else:
            customer = Customer.objects.create(
                tenant=tenant,
                phone=normalized_phone,
                first_name=first_name.strip(),
                last_name=(last_name or "").strip(),
                email=email or None,
            )
            customer.set_password(password)
            customer.save(update_fields=["password_hash", "updated_at"])

        return CustomerAuthService._build_auth_response(customer)

    @staticmethod
    def login(*, tenant: Company, phone: str, password: str) -> dict:
        normalized_phone = normalize_phone(phone)

        try:
            customer = Customer.all_objects.get(
                tenant=tenant,
                phone=normalized_phone,
                is_active=True,
                deleted_at__isnull=True,
            )
        except Customer.DoesNotExist:
            raise AuthenticationFailed("Credenciais inválidas") from None

        if not customer.password_hash or not customer.check_password(password):
            raise AuthenticationFailed("Credenciais inválidas")

        return CustomerAuthService._build_auth_response(customer)

    @staticmethod
    def refresh(*, refresh_token: str) -> dict:
        try:
            token = RefreshToken(refresh_token)
        except TokenError as exc:
            raise AuthenticationFailed("Refresh token inválido") from exc

        if token.get("type") != "customer":
            raise AuthenticationFailed("Refresh token inválido")

        if CustomerAuthService._is_blacklisted(str(token.get("jti", ""))):
            raise AuthenticationFailed("Refresh token inválido")

        customer_id = token.get("customer_id")
        if not customer_id:
            raise AuthenticationFailed("Refresh token inválido")

        try:
            customer = Customer.all_objects.select_related("tenant").get(
                id=customer_id,
                is_active=True,
                deleted_at__isnull=True,
            )
        except Customer.DoesNotExist:
            raise AuthenticationFailed("Refresh token inválido") from None

        new_refresh = CustomerAuthService._build_refresh_token(customer)
        return {
            "access": str(new_refresh.access_token),
            "refresh": str(new_refresh),
        }

    @staticmethod
    def logout(*, refresh_token: str) -> None:
        try:
            token = RefreshToken(refresh_token)
        except TokenError as exc:
            raise AuthenticationFailed("Refresh token inválido") from exc

        if token.get("type") != "customer":
            raise AuthenticationFailed("Refresh token inválido")

        jti = str(token.get("jti", ""))
        if not jti:
            return

        ttl = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
        cache.set(f"{TOKEN_BLACKLIST_PREFIX}{jti}", "1", timeout=ttl)

    @staticmethod
    def _build_auth_response(customer: Customer) -> dict:
        from apps.companies.serializers.company_serializers import CompanyMinimalSerializer
        from apps.customers.serializers.customer_serializers import CustomerSerializer

        refresh = CustomerAuthService._build_refresh_token(customer)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "customer": CustomerSerializer(customer).data,
            "tenant": CompanyMinimalSerializer(customer.tenant).data,
        }

    @staticmethod
    def _build_refresh_token(customer: Customer) -> RefreshToken:
        refresh = RefreshToken()
        refresh["customer_id"] = str(customer.id)
        refresh["tenant_id"] = str(customer.tenant_id)
        refresh["type"] = "customer"
        return refresh

    @staticmethod
    def _is_blacklisted(jti: str) -> bool:
        if not jti:
            return False
        return cache.get(f"{TOKEN_BLACKLIST_PREFIX}{jti}") is not None
