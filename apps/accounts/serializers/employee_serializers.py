from rest_framework import serializers

from apps.accounts.models import Employee


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    subdomain = serializers.CharField(required=False, allow_blank=True)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class EmployeeSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "is_owner",
            "permissions",
        ]

    def to_representation(self, instance):
        permissions = self.context.get("permissions")
        if permissions is None:
            from apps.accounts.services.auth_service import AuthService

            permissions = AuthService.get_permissions(instance)

        return {
            "id": str(instance.id),
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "is_owner": instance.is_owner,
            "permissions": permissions,
        }
