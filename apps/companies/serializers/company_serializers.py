from rest_framework import serializers


class CompanyMinimalSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    trade_name = serializers.CharField()
    slug = serializers.CharField()
    subdomain = serializers.CharField()

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "trade_name": instance.trade_name,
            "slug": instance.slug,
            "subdomain": instance.subdomain,
        }
