from rest_framework import serializers


class DiningTableWriteSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=20)
    label = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    capacity = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    is_active = serializers.BooleanField(required=False, default=True)
    sort_order = serializers.IntegerField(required=False)


class DiningTablePatchSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=20, required=False)
    label = serializers.CharField(max_length=100, required=False, allow_blank=True)
    capacity = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    is_active = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(required=False)


class DiningTableBulkSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=1, max_value=100)
    start = serializers.IntegerField(min_value=1, required=False, default=1)
