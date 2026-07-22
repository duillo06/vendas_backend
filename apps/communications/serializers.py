from rest_framework import serializers

from apps.communications.domain.enums import PHASE1_EVENT_KEYS, ProviderKey
from apps.communications.services.connection_service import ConnectionService


class ConnectWhatsAppSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(
        choices=[ConnectionService.MODE_HOSTED, ConnectionService.MODE_BYO],
        default=ConnectionService.MODE_BYO,
        required=False,
    )
    base_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    api_key = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    provider_key = serializers.ChoiceField(
        choices=[ProviderKey.EVOLUTION],
        default=ProviderKey.EVOLUTION,
        required=False,
    )

    def validate(self, attrs):
        mode = attrs.get("mode") or ConnectionService.MODE_BYO
        if mode == ConnectionService.MODE_BYO:
            if not (attrs.get("base_url") or "").strip() or not (attrs.get("api_key") or "").strip():
                raise serializers.ValidationError(
                    {"base_url": "Informe o endereço e a chave de acesso."},
                )
        return attrs


class SituationBulkSerializer(serializers.Serializer):
    situations = serializers.DictField(
        child=serializers.BooleanField(),
        help_text="mapa event_key → enabled",
    )

    def validate_situations(self, value):
        unknown = [k for k in value if k not in PHASE1_EVENT_KEYS]
        if unknown:
            raise serializers.ValidationError(f"Situações desconhecidas: {unknown}")
        return value


class TemplateWriteSerializer(serializers.Serializer):
    body = serializers.CharField()


class TemplatePreviewSerializer(serializers.Serializer):
    body = serializers.CharField(required=False, allow_blank=True)


class TemplateTestSerializer(serializers.Serializer):
    body = serializers.CharField(required=False, allow_blank=True)


class ConnectionTestSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        default="Olá! 🎉 Seu WhatsApp foi conectado com sucesso ao sistema.",
    )
