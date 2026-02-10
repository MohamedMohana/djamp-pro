import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()

from django.contrib.auth.models import User
from certificates.models_role import Role, UserProfile

# Get or create the super_admin role
super_admin_role = Role.objects.get(name_en='super_admin')

# Get all superusers
superusers = User.objects.filter(is_superuser=True)

for user in superusers:
    # Create UserProfile if it doesn't exist
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Add super_admin role to the new roles M2M field
    if not profile.roles.filter(pk=super_admin_role.pk).exists():
        profile.roles.add(super_admin_role)
    
    # Also set legacy role field for backwards compatibility during migration
    if not profile.role:
        profile.role = super_admin_role
        profile.save()