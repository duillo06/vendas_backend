from rest_framework import serializers


class CustomerRegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    first_name = serializers.CharField(min_length=2, max_length=100)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get("email") == "":
            attrs["email"] = None
        return attrs


class CustomerLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=128, write_only=True)


class CustomerRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class CustomerLogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
