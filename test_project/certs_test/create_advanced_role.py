import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()

from certificates.models_role import Role

# Create advanced admin role with all necessary permissions
role_data = {
    'name_ar': 'مشرف متقدم',
    'name_en': 'advanced_admin',
}

# Get or create the advanced role
role, created = Role.objects.get_or_create(
    name_en='advanced_admin',
    defaults=role_data
)

# Update permissions (whether created or already exists)
role.name_ar = 'مشرف متقدم'

# Advanced Template Permissions
role.can_view_advanced_templates = True
role.can_create_advanced_templates = True
role.can_edit_advanced_templates = True
role.can_delete_advanced_templates = True

# Advanced Certificate Permissions
role.can_view_advanced_certificates = True
role.can_create_advanced_certificates = True

# Standard Certificate Permissions (for verification)
role.can_view_certificates = True
role.can_verify_certificates = True

role.save()

if created:
    print(f"✅ Created new role: {role.name_ar} ({role.name_en})")
else:
    print(f"✅ Updated existing role: {role.name_ar} ({role.name_en})")

print(f"\nPermissions granted:")
print(f"  - عرض القوالب المتقدمة")
print(f"  - إنشاء القوالب المتقدمة")
print(f"  - تعديل القوالب المتقدمة")
print(f"  - حذف القوالب المتقدمة")
print(f"  - عرض الشهادات المتقدمة")
print(f"  - إنشاء الشهادات المتقدمة")
print(f"  - عرض الشهادات (العادية)")
print(f"  - التحقق من الشهادات")

