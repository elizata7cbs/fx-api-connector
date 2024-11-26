from django.urls import path
from .views import TransactionCreateView, TransactionListView, TransactionDetailView, CurrencyListView, \
    UserCurrencyPreferenceView

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='list_transactions'),
    path('transactions/create/', TransactionCreateView.as_view(), name='create_transaction'),
    path('transactions/<uuid:identifier>/', TransactionDetailView.as_view(), name='detail_transaction'),
    path('currencies/', CurrencyListView.as_view(), name='currency-list'),
    path('user-preferences/', UserCurrencyPreferenceView.as_view(), name='user-preferences')
]