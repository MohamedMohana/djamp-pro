from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.conf import settings
import requests
import xml.etree.ElementTree as ET
import json

class CASBackend(BaseBackend):
    """Django authentication backend for CAS (Central Authentication Service)."""
    def authenticate(self, request, ticket=None, service=None):
        """Authenticate a user using CAS ticket and service URL."""
        if not ticket or not service:
            return None

        # Validate the ticket with the CAS server
        cas_url = (
            f"{settings.CAS_PROTOCOL}://{settings.CAS_HOST}{settings.CAS_CONTEXT}/serviceValidate"
            f"?service={service}&ticket={ticket}"
        )
        try:
            cas_response = requests.get(cas_url)
            cas_xml_response = cas_response.content.decode("utf-8")
            cas_xml = ET.fromstring(cas_xml_response)
            username_element = cas_xml.find(".//{http://www.yale.edu/tp/cas}user")
            if username_element is not None:
                username = username_element.text

                # Fetch user info from KKU service
                user_info_url = settings.KKU_SERVICES_USER_INFO_URL
                user_info_data = {
                    "wsUsername": settings.KKU_SERVICES_USER,
                    "wsPassword": settings.KKU_SERVICES_PASS,
                    "nickname": username
                }
                user_info_response = requests.post(user_info_url, json=user_info_data)
                user_info = json.loads(user_info_response.content)
                
                full_name = user_info.get('data', {}).get('userNameA', '')
                email = user_info.get('data', {}).get('email', '') or f"{username}@kku.edu.sa"
                phone = user_info.get('data', {}).get('mobileNo', '')
                names = full_name.split(' ', 1)

                # Get or create the user
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
                from certificates.models_role import UserProfile, Role
                try:
                    profile = user.profile
                except:
                    # Create profile if it doesn't exist
                    default_role = Role.objects.filter(name_en='user').first()
                    profile = UserProfile.objects.create(user=user, role=default_role)
                
                # Update phone if available (using correct field name from CAS)
                if phone:
                    profile.phone = phone
                    profile.save()
                
                return user
        except Exception:
            return None

        return None

    def get_user(self, user_id):
        """Retrieve a user by their ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None 