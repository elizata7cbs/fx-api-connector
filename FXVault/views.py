from decimal import Decimal
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import requests
from FX_Transactions import settings
from.models import Transaction
from rest_framework import generics, status
from.serializers import TransactionSerializer


class TransactionCreateView(generics.CreateAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "You are authenticated!"})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            input_amount = serializer.validated_data.get("input_amount")
            input_currency = serializer.validated_data.get("input_currency")
            output_currency = serializer.validated_data.get("output_currency")
            api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
            response = requests.get(api_url, verify=False)

            if response.status_code == 200:
                exchange_rates = response.json().get("conversion_rates", {})
                exchange_rate = exchange_rates.get(output_currency)

                if exchange_rate:
                    exchange_rate_decimal = Decimal(str(exchange_rate))
                    output_amount = input_amount * exchange_rate_decimal
                    serializer.save(output_amount=output_amount)

                    headers = self.get_success_headers(serializer.data)
                    return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
                else:
                    return Response(
                        {"error": f"Conversion rate for {output_currency} not available."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"error": "Error fetching exchange rate from external API."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrencyListView(generics.ListAPIView):
    def get_queryset(self):
        api_url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
        response = requests.get(api_url, verify=False)

        if response.status_code == 200:
            currencies = response.json().get("conversion_rates", {}).keys()
            return currencies

        # If API call fails, return an empty queryset
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

class TransactionDetailView(generics.RetrieveAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    lookup_field = 'identifier'
