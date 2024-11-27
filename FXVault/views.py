import logging
import requests
import time  # Import the time module for measuring time
from decimal import Decimal
from rest_framework import status
from rest_framework.response import Response
from rest_framework import generics
from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from .models import Transaction, UserCurrencyPreference
from .serializers import TransactionSerializer, ExchangeRateSerializer, UserCurrencyPreferenceSerializer

# Initialize logger for FXVault app
logger = logging.getLogger('FXVault')

# Log a message
logger.debug("This is a debug message")
logger.info("This is an info message")
logger.error("This is an error message")


class TransactionCreateView(generics.CreateAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        logger.debug("TransactionCreateView.create called with data: %s", request.data)
        user = request.user

        try:
            user_preferences = UserCurrencyPreference.objects.get(user=user)
            allowed_currencies = user_preferences.allowed_currencies
            logger.info("User %s has allowed currencies: %s", user.username, allowed_currencies)

            exchange_rate_serializer = ExchangeRateSerializer(data=request.data)
            if exchange_rate_serializer.is_valid():
                input_currency = exchange_rate_serializer.validated_data.get("input_currency")
                output_currency = exchange_rate_serializer.validated_data.get("output_currency")

                if input_currency not in allowed_currencies or output_currency not in allowed_currencies:
                    logger.warning(
                        "User %s tried converting unauthorized currencies: %s to %s",
                        user.username, input_currency, output_currency
                    )
                    return Response({
                        "message": "You are not allowed to convert between these currencies.",
                        "status": status.HTTP_403_FORBIDDEN
                    }, status=status.HTTP_403_FORBIDDEN)

                cache_key = f"exchange_rate_{input_currency}_{output_currency}"
                start_time = time.time()  # Start the timer

                exchange_rate = cache.get(cache_key)

                if exchange_rate:
                    elapsed_time = time.time() - start_time  # Calculate time taken for cache retrieval
                    logger.info("Cache hit for exchange rate %s to %s. Time taken: %.4f seconds", input_currency,
                                output_currency, elapsed_time)
                    exchange_rate = Decimal(str(exchange_rate))
                else:
                    api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
                    response = requests.get(api_url, verify=False)

                    if response.status_code == 200:
                        exchange_rates = response.json().get("conversion_rates", {})
                        exchange_rate = exchange_rates.get(output_currency)

                        if exchange_rate:
                            exchange_rate = Decimal(str(exchange_rate))
                            cache.set(cache_key, exchange_rate, timeout=3600)  # Cache the rate for 1 hour
                            elapsed_time = time.time() - start_time  # Time taken for external API request
                            logger.info(
                                "Fetched exchange rate from external API for %s to %s. Time taken: %.4f seconds",
                                input_currency, output_currency, elapsed_time)

                            input_amount = Decimal(str(exchange_rate_serializer.validated_data['input_amount']))
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
                                logger.info("Transaction created successfully for user %s", user.username)
                                return Response({
                                    "data": transaction_serializer.data,
                                    "status": status.HTTP_201_CREATED,
                                    "message": "Transaction created successfully"
                                }, status=status.HTTP_201_CREATED)
                    logger.error("Failed to fetch exchange rate from external API")
                    return Response({
                        "message": "Error fetching exchange rate.",
                        "status": status.HTTP_502_BAD_GATEWAY
                    }, status=status.HTTP_502_BAD_GATEWAY)

                # Process transaction using cached rate
                input_amount = Decimal(str(exchange_rate_serializer.validated_data['input_amount']))
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
                    logger.info("Transaction created successfully for user %s using cached rate", user.username)
                    return Response({
                        "data": transaction_serializer.data,
                        "status": status.HTTP_201_CREATED,
                        "message": "Transaction created successfully"
                    }, status=status.HTTP_201_CREATED)

            logger.warning("Invalid data provided for transaction creation: %s", exchange_rate_serializer.errors)
            return Response({
                "errors": exchange_rate_serializer.errors,
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid data"
            }, status=status.HTTP_400_BAD_REQUEST)

        except UserCurrencyPreference.DoesNotExist:
            logger.error("User %s does not have currency preferences configured", user.username)
            return Response({
                "message": "Currency preferences not found for this user.",
                "status": status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("An unexpected error occurred during transaction creation: %s", str(e))
            return Response({
                "message": "An error occurred while processing your request.",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserCurrencyPreferenceView(generics.GenericAPIView):
    queryset = UserCurrencyPreference.objects.all()
    serializer_class = UserCurrencyPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.debug("UserCurrencyPreferenceView.post called with data: %s", request.data)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            preference = self.perform_create(serializer)
            logger.info("Currency preference created for user %s", request.user.username)
            return Response({
                "data": UserCurrencyPreferenceSerializer(preference).data,
                "status": status.HTTP_201_CREATED,
                "message": "Currency preference saved successfully."
            }, status=status.HTTP_201_CREATED)
        logger.warning("Invalid data for currency preference creation: %s", serializer.errors)
        return Response({
            "data": None,
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data."
        }, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, *args, **kwargs):
        user = self.request.user
        logger.debug("UserCurrencyPreferenceView.patch called for user %s", user.username)
        try:
            preference = UserCurrencyPreference.objects.get(user=user)
        except UserCurrencyPreference.DoesNotExist:
            logger.error("Currency preference not found for user %s", user.username)
            return Response({
                "message": "Preference not found. Please create one first.",
                "status": status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(preference, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info("Currency preference updated for user %s", user.username)
            return Response({
                "data": serializer.data,
                "status": status.HTTP_200_OK,
                "message": "Currency preference updated successfully."
            }, status=status.HTTP_200_OK)
        logger.warning("Invalid data for currency preference update: %s", serializer.errors)
        return Response({
            "errors": serializer.errors,
            "status": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data."
        }, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        user = self.request.user
        preference, created = UserCurrencyPreference.objects.get_or_create(user=user)
        if not created:
            serializer.update(preference, serializer.validated_data)
        else:
            serializer.save(user=user)
        return preference


class CurrencyListView(generics.ListAPIView):
    def get_queryset(self):
        logger.debug("CurrencyListView.get_queryset called")
        api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
        response = requests.get(api_url, verify=False)

        if response.status_code == 200:
            conversion_rates = response.json().get("conversion_rates", {})
            currencies_with_rates = [
                {"currency": currency, "rate": rate} for currency, rate in conversion_rates.items()
            ]
            logger.info("Fetched conversion rates successfully.")
            return currencies_with_rates

        logger.error("Failed to fetch conversion rates from external API")
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
        logger.debug("TransactionListView.list called")
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
        logger.debug("TransactionDetailView.retrieve called with identifier: %s", kwargs.get('identifier'))
        transaction = self.get_object()
        return Response({
            "data": TransactionSerializer(transaction).data,
            "status": status.HTTP_200_OK,
            "message": "Transaction details fetched successfully"
        }, status=status.HTTP_200_OK)
