import requests
from decimal import Decimal
from rest_framework import status
from rest_framework.response import Response
from rest_framework import generics
from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from .models import Transaction
from .serializers import TransactionSerializer, ExchangeRateSerializer


class TransactionCreateView(generics.CreateAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Validate the incoming data with ExchangeRateSerializer
        exchange_rate_serializer = ExchangeRateSerializer(data=request.data)

        if exchange_rate_serializer.is_valid():
            customer_id = exchange_rate_serializer.validated_data.get("customer_id")
            input_amount = exchange_rate_serializer.validated_data.get("input_amount")
            input_currency = exchange_rate_serializer.validated_data.get("input_currency")
            output_currency = exchange_rate_serializer.validated_data.get("output_currency")

            # Step 2: Handle exchange rate logic (use cache or fetch from API)
            cache_key = f"exchange_rate_{input_currency}_{output_currency}"
            exchange_rate = cache.get(cache_key)

            if not exchange_rate:
                # If not cached, fetch it from the external API
                api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
                response = requests.get(api_url, verify=False)

                if response.status_code == 200:
                    exchange_rates = response.json().get("conversion_rates", {})
                    exchange_rate = exchange_rates.get(output_currency)

                    if exchange_rate:
                        # Cache the exchange rate for 1 hour
                        cache.set(cache_key, exchange_rate, timeout=3600)

                        # Calculate the output amount and round it to 2 decimal places
                        exchange_rate_decimal = Decimal(str(exchange_rate))
                        output_amount = round(input_amount * exchange_rate_decimal, 2)

                        # Create the transaction using the TransactionSerializer
                        transaction_data = {
                            "input_amount": input_amount,
                            "input_currency": input_currency,
                            "output_currency": output_currency,
                            "output_amount": output_amount,
                            "customer_id": customer_id
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
                                "data": {},
                                "errors": transaction_serializer.errors,
                                "status": status.HTTP_400_BAD_REQUEST,
                                "message": "Transaction creation failed"
                            }, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({
                            "data": {},
                            "error": f"Conversion rate for {output_currency} not available.",
                            "status": status.HTTP_400_BAD_REQUEST,
                            "message": f"Conversion rate for {output_currency} not available."
                        }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({
                        "data": {},
                        "error": "Error fetching exchange rate from external API",
                        "status": status.HTTP_502_BAD_GATEWAY,
                        "message": "Error fetching exchange rate from external API"
                    }, status=status.HTTP_502_BAD_GATEWAY)
            else:
                # If exchange rate is cached, use it
                exchange_rate_decimal = Decimal(str(exchange_rate))
                output_amount = round(input_amount * exchange_rate_decimal, 2)

                # Create the transaction using the TransactionSerializer
                transaction_data = {
                    "input_amount": input_amount,
                    "input_currency": input_currency,
                    "output_currency": output_currency,
                    "output_amount": output_amount,
                    "customer_id": customer_id
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
                        "data": {},
                        "errors": transaction_serializer.errors,
                        "status": status.HTTP_400_BAD_REQUEST,
                        "message": "Transaction creation failed"
                    }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "data": {},
            "errors": exchange_rate_serializer.errors,
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data"
        }, status=status.HTTP_400_BAD_REQUEST)


class CurrencyListView(generics.ListAPIView):
    def get_queryset(self):
        # Use a unique cache key for the list of currencies
        cache_key = 'currency_list'

        # Try to get the cached list of currencies
        currencies = cache.get(cache_key)

        if not currencies:
            # If not in cache, fetch it from the external API
            api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
            response = requests.get(api_url, verify=False)

            if response.status_code == 200:
                currencies = response.json().get("conversion_rates", {}).keys()

                # Cache the list of currencies for 1 hour (adjust as needed)
                cache.set(cache_key, currencies, timeout=3600)
            else:
                # If API call fails, return an empty list
                currencies = []

        return currencies

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset:
            return Response({
                "data": {},
                "error":"Error fetching data from external API",
                "status": status.HTTP_502_BAD_GATEWAY,
                "message": "Error fetching data from external API"
            }, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "data": queryset,
            "status": status.HTTP_200_OK,
            "message": "Currency list fetched successfully"
        }, status=status.HTTP_200_OK)


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