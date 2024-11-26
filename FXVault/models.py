import uuid

from django.contrib.auth.models import User
from django.db import models

class Transaction(models.Model):
    identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer_id = models.CharField(max_length=255)
    input_amount = models.DecimalField(max_digits=100, decimal_places=2)
    input_currency = models.CharField(max_length=3)
    output_amount = models.DecimalField(max_digits=100, decimal_places=2,null = True, blank = True)
    output_currency = models.CharField(max_length=3)
    transaction_date = models.DateTimeField(auto_now_add=True)


class UserCurrencyPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    allowed_currencies = models.JSONField(default=list)  # Stores a list of allowed currencies

    def __str__(self):
        return f"Preferences for {self.user.username}"

