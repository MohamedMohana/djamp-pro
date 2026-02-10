from django.contrib.auth.backends import ModelBackend

class APIUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        allowed_api_users = [
            'hash_api',
            'event_api',
            'kkux_api',
            'block_listed_api',
            'laravel',
            # Add any other service/API usernames here as needed
        ]
        if username not in allowed_api_users:
            return None
        return super().authenticate(request, username, password, **kwargs) 