import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()

from django.contrib.auth.models import User
from certificates.models_role import Role, UserProfile

# Get the super_admin role
super_admin_role = Role.objects.get(name_en='super_admin')

# Update all superusers
superusers = User.objects.filter(is_superuser=True)
for user in superusers:
    # Make sure they have a profile
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Add super_admin role to the new roles M2M field
    if not profile.roles.filter(pk=super_admin_role.pk).exists():
        profile.roles.add(super_admin_role)
    
    # Also set legacy role field for backwards compatibility during migration
    if profile.role != super_admin_role:
        profile.role = super_admin_role
        profile.save()

    # Make sure they have all permissions
    if not user.is_staff:
        user.is_staff = True
        user.save()

# Remove or comment out all print statements in this file (continued)