from rest_framework import serializers
from.models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"


class ExchangeRateSerializer(serializers.Serializer):
    customer_id = serializers.CharField(max_length=255)
    input_amount = serializers.DecimalField(required=True, max_digits=100, decimal_places=2)
    input_currency = serializers.CharField(max_length=3,required = True)
    output_currency = serializers.CharField(max_length=3, required = True)
