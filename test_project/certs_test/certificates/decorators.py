from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import Http404

def role_required(permission_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'profile') or not request.user.profile.roles.exists():
                raise Http404()
            
            # Allow super_admin to access everything
            if request.user.profile.is_super_admin() or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if any of the user's roles has this permission
            if not request.user.profile.has_permission(permission_name):
                raise Http404()
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator