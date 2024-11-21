import requests
from rest_framework import serializers
from .models import Transaction, UserCurrencyPreference


class TransactionSerializer(serializers.ModelSerializer):

    # Ensure the input and output currencies are valid
    def validate_input_currency(self, value):
        # Add validation logic if necessary
        return value

    def validate_output_currency(self, value):
        # Add validation logic if necessary
        return value
    class Meta:
        model = Transaction
        fields = "__all__"


class ExchangeRateSerializer(serializers.Serializer):
    customer_id = serializers.CharField(max_length=255)
    input_amount = serializers.DecimalField(required=True, max_digits=100, decimal_places=2)
    input_currency = serializers.CharField(max_length=3,required = True)
    output_currency = serializers.CharField(max_length=3, required = True)



class UserCurrencyPreferenceSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserCurrencyPreference
        fields = ['username', 'allowed_currencies']

    def create(self, validated_data):
        # Automatically set the user to the current authenticated user
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate_allowed_currencies(self, value):
        # Fetch the list of available currencies from the external API
        api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(api_url, verify=False)

        if response.status_code == 200:
            available_currencies = response.json().get('rates', {})

            # Validate if each currency is available
            for currency in value:
                if currency not in available_currencies:
                    raise serializers.ValidationError(f"{currency} is not a valid currency.")
        else:
            raise serializers.ValidationError("Error fetching available currencies from the external API.")

        return value