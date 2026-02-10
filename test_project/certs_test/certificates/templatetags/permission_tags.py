"""
Custom template tags for checking user permissions with multi-role support.
"""
from django import template

register = template.Library()


@register.filter
def has_perm(profile, permission_name):
    """
    Check if user profile has a specific permission from any of their roles.
    
    Usage in templates:
        {% load permission_tags %}
        {% if user.profile|has_perm:'can_view_templates' %}
            ... show content ...
        {% endif %}
    """
    if not profile:
        return False
    try:
        return profile.has_permission(permission_name)
    except AttributeError:
        return False


@register.filter
def is_super_admin(profile):
    """
    Check if user profile has super_admin role.
    
    Usage in templates:
        {% load permission_tags %}
        {% if user.profile|is_super_admin %}
            ... show admin content ...
        {% endif %}
    """
    if not profile:
        return False
    try:
        return profile.is_super_admin()
    except AttributeError:
        return False


@register.filter
def has_role(profile, role_name):
    """
    Check if user profile has a specific role by name_en.
    
    Usage in templates:
        {% load permission_tags %}
        {% if user.profile|has_role:'admin' %}
            ... show content ...
        {% endif %}
    """
    if not profile:
        return False
    try:
        return profile.roles.filter(name_en=role_name).exists()
    except AttributeError:
        return False


@register.simple_tag
def user_has_any_permission(profile, *permissions):
    """
    Check if user has any of the given permissions.
    
    Usage in templates:
        {% load permission_tags %}
        {% user_has_any_permission user.profile 'can_view_templates' 'can_create_templates' as can_access_templates %}
        {% if can_access_templates %}
            ... show content ...
        {% endif %}
    """
    if not profile:
        return False
    try:
        for perm in permissions:
            if profile.has_permission(perm):
                return True
        return False
    except AttributeError:
        return False


@register.filter
def lookup(dictionary, key):
    """
    Look up a key in a dictionary.
    
    Usage in templates:
        {% load permission_tags %}
        {{ my_dict|lookup:key_variable }}
        {% if my_dict|lookup:key_variable %}...{% endif %}
    """
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None
