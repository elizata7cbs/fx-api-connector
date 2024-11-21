import requests
from decimal import Decimal
from rest_framework import status
from rest_framework.response import Response
from rest_framework import generics
from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from .models import Transaction, UserCurrencyPreference
from .serializers import TransactionSerializer, ExchangeRateSerializer, UserCurrencyPreferenceSerializer


class TransactionCreateView(generics.CreateAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Get the logged-in user
        user = request.user

        # Get the user's allowed currencies
        user_preferences = UserCurrencyPreference.objects.get(user=user)
        allowed_currencies = user_preferences.allowed_currencies

        # Validate the incoming data with ExchangeRateSerializer
        exchange_rate_serializer = ExchangeRateSerializer(data=request.data)
        if exchange_rate_serializer.is_valid():
            input_currency = exchange_rate_serializer.validated_data.get("input_currency")
            output_currency = exchange_rate_serializer.validated_data.get("output_currency")

            # Check if the user is allowed to use these currencies
            if input_currency not in allowed_currencies or output_currency not in allowed_currencies:
                return Response({
                    "message": "You are not allowed to convert between these currencies.",
                    "status": status.HTTP_403_FORBIDDEN
                }, status=status.HTTP_403_FORBIDDEN)

            # Handle exchange rate logic (using cache or fetch from API)
            cache_key = f"exchange_rate_{input_currency}_{output_currency}"
            exchange_rate = cache.get(cache_key)

            if not exchange_rate:
                # Fetch exchange rate from API
                api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
                response = requests.get(api_url, verify=False)

                if response.status_code == 200:
                    exchange_rates = response.json().get("conversion_rates", {})
                    exchange_rate = exchange_rates.get(output_currency)

                    if exchange_rate:
                        # Convert exchange_rate to Decimal for accurate calculations
                        exchange_rate = Decimal(str(exchange_rate))

                        # Cache the exchange rate
                        cache.set(cache_key, exchange_rate, timeout=3600)

                        # Convert input_amount to Decimal for multiplication
                        input_amount = Decimal(str(exchange_rate_serializer.validated_data['input_amount']))

                        # Calculate the output amount
                        output_amount = round(exchange_rate * input_amount, 2)

                        # Save the transaction
                        transaction_data = {
                            "input_amount": input_amount,
                            "input_currency": input_currency,
                            "output_currency": output_currency,
                            "output_amount": output_amount,
                            "customer_id": exchange_rate_serializer.validated_data['customer_id']
                        }
                        transaction_serializer = TransactionSerializer(data=transaction_data)
                        if transaction_serializer.is_valid():
                            transaction_serializer.save()
                            return Response({
                                "data": transaction_serializer.data,
                                "status": status.HTTP_201_CREATED,
                                "message": "Transaction created successfully"
                            }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        "message": "Error fetching exchange rate.",
                        "status": status.HTTP_502_BAD_GATEWAY
                    }, status=status.HTTP_502_BAD_GATEWAY)
            else:
                # Use cached exchange rate
                exchange_rate = Decimal(str(exchange_rate))  # Convert exchange_rate to Decimal
                input_amount = Decimal(str(exchange_rate_serializer.validated_data['input_amount']))  # Convert input_amount to Decimal

                # Calculate the output amount
                output_amount = round(exchange_rate * input_amount, 2)

                transaction_data = {
                    "input_amount": input_amount,
                    "input_currency": input_currency,
                    "output_currency": output_currency,
                    "output_amount": output_amount,
                    "customer_id": exchange_rate_serializer.validated_data['customer_id']
                }
                transaction_serializer = TransactionSerializer(data=transaction_data)
                if transaction_serializer.is_valid():
                    transaction_serializer.save()
                    return Response({
                        "data": transaction_serializer.data,
                        "status": status.HTTP_201_CREATED,
                        "message": "Transaction created successfully"
                    }, status=status.HTTP_201_CREATED)

        return Response({
            "errors": exchange_rate_serializer.errors,
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data"
        }, status=status.HTTP_400_BAD_REQUEST)


class UserCurrencyPreferenceView(generics.GenericAPIView):
    queryset = UserCurrencyPreference.objects.all()
    serializer_class = UserCurrencyPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Handle creating a new preference or saving the first one
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            preference = self.perform_create(serializer)
            return Response({
                "data": UserCurrencyPreferenceSerializer(preference).data,
                "status": status.HTTP_201_CREATED,
                "message": "Currency preference saved successfully."
            }, status=status.HTTP_201_CREATED)
        return Response({
            "data": None,
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data."
        }, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        # Get the user and check if they already have a preference
        user = self.request.user
        try:
            preference = UserCurrencyPreference.objects.get(user=user)
        except UserCurrencyPreference.DoesNotExist:
            return Response({
                "message": "Preference not found. Please create one first.",
                "status": status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)

        # Use the serializer to validate and update the data (partial update)
        serializer = self.get_serializer(preference, data=request.data,
                                         partial=True)  # 'partial=True' allows partial updates
        if serializer.is_valid():
            serializer.save()  # Save the updated data
            return Response({
                "data": serializer.data,
                "status": status.HTTP_200_OK,
                "message": "Currency preference updated successfully."
            }, status=status.HTTP_200_OK)

        return Response({
            "errors": serializer.errors,
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data."
        }, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        # Check if the user already has a currency preference
        user = self.request.user
        preference, created = UserCurrencyPreference.objects.get_or_create(user=user)

        # If the preference already exists, we update it
        if not created:
            serializer.update(preference, serializer.validated_data)
        else:
            # If not, we save the new preference
            serializer.save(user=user)

        return preference


class CurrencyListView(generics.ListAPIView):
    def get_queryset(self):
        api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
        response = requests.get(api_url, verify=False)

        if response.status_code == 200:
            # Fetching the conversion rates and organizing them as a dictionary of currencies and their rates
            conversion_rates = response.json().get("conversion_rates", {})
            currencies_with_rates = [
                {"currency": currency, "rate": rate} for currency, rate in conversion_rates.items()
            ]
            return currencies_with_rates

        # If API call fails, return an empty list
        return []

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset:
            return Response(
                {"error": "Error fetching data from external API"},
                status=status.HTTP_502_BAD_GATEWAY
            )
        return Response(queryset, status=status.HTTP_200_OK)


class TransactionListView(generics.ListAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response({
            "data": TransactionSerializer(queryset, many=True).data,
            "status": status.HTTP_200_OK,
            "message": "Transaction list fetched successfully"
        }, status=status.HTTP_200_OK)


class TransactionDetailView(generics.RetrieveAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    lookup_field = 'identifier'

    def retrieve(self, request, *args, **kwargs):
        transaction = self.get_object()
        return Response({
            "data": TransactionSerializer(transaction).data,
            "status": status.HTTP_200_OK,
            "message": "Transaction details fetched successfully"
        }, status=status.HTTP_200_OK)
