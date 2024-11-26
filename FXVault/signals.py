from django.contrib.auth.models import User
from .models import UserCurrencyPreference

# Example for adding user preferences when a new user is created
user = User.objects.create_user(username='newuser', password='password123')
UserCurrencyPreference.objects.create(user=user, allowed_currencies=['USD', 'KES', 'EUR'])
