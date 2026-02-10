import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()

from certificates.models_role import Role

# Create default roles
roles = [
    {'name_ar': 'مدير النظام', 'name_en': 'super_admin'},
    {'name_ar': 'مستخدم', 'name_en': 'user'},
    {'name_ar': 'مشرف', 'name_en': 'admin'}
]

for role_data in roles:
    role, created = Role.objects.get_or_create(
        name_ar=role_data['name_ar'],
        name_en=role_data['name_en']
    )
    # if created:
    #     print(f"Created role: {role.name_ar}")
    # else:
    #     print(f"Role already exists: {role.name_ar}")