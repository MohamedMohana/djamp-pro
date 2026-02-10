import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()

from certificates.models_role import Role

# Update super_admin role
super_admin = Role.objects.get(name_en='super_admin')
for field in Role._meta.fields:
    if field.name.startswith('can_'):
        setattr(super_admin, field.name, True)
super_admin.save()

# Update admin role
admin = Role.objects.get(name_en='admin')
admin.can_view_templates = True
admin.can_create_templates = True
admin.can_edit_templates = True
admin.can_view_certificates = True
admin.can_create_certificates = True
admin.can_verify_certificates = True
admin.can_view_users = True
admin.save()

# Update user role
user = Role.objects.get(name_en='user')
user.can_view_certificates = True
user.can_verify_certificates = True
user.save()