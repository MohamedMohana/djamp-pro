from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.conf import settings
import requests
import json

class NafathBackend(BaseBackend):
    """Django authentication backend for Nafath/IAM."""
    def authenticate(self, request, nafath_token=None):
        """Authenticate a user using Nafath/IAM token."""
        if not nafath_token:
            return None

        # Call IAM/Nafath API to validate the token and get user info
        try:
            url = settings.KKU_IAM_WS_URL
            data = {
                "wsUsername": settings.KKU_SERVICES_USER,
                "wsPassword": settings.KKU_SERVICES_PASS,
                "token": nafath_token,
            }
            response = requests.post(url, json=data)
            if response.status_code != 200:
                return None
            user_info = response.json()
            
            # Extract user info
            username = user_info.get('data', {}).get('userNameE')
            full_name = user_info.get('data', {}).get('userNameA', '')
            phone = user_info.get('data', {}).get('mobileNo', '')
            email = user_info.get('data', {}).get('email', '') or f"iam.{username}@kku.edu.sa"
            names = full_name.split(' ', 1)

            if not username:
                return None

            user, created = User.objects.get_or_create(username=username)
            if len(names) >= 2:
                user.first_name = names[0]
                user.last_name = names[1]
            else:
                user.first_name = full_name
                user.last_name = ''
            
            # Update email only if user doesn't have one already
            if email and not user.email:
                user.email = email
                user.save()
            
            # Update or create UserProfile with phone number
            try:
                profile = user.profile
            except:
                # Create profile if it doesn't exist
                from certificates.models_role import UserProfile, Role
                default_role = Role.objects.filter(name_en='user').first()
                profile = UserProfile.objects.create(user=user, role=default_role)
            
            # Update phone if available
            if phone:
                profile.phone = phone
                profile.save()
            
            return user
        except Exception:
            return None

    def get_user(self, user_id):
        """Retrieve a user by their ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None 