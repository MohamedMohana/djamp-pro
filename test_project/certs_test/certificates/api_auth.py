from rest_framework.authentication import BasicAuthentication
from django.contrib.auth import authenticate
from rest_framework import exceptions

class APIBasicAuthentication(BasicAuthentication):
    def authenticate_credentials(self, userid, password, request=None):
        user = authenticate(request=request, username=userid, password=password, backend='django.contrib.auth.backends.ModelBackend')
        if user is None:
            raise exceptions.AuthenticationFailed('Invalid username/password.')
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted.')
        return (user, None) 