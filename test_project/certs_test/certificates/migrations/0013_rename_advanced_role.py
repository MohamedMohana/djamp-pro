from django.db import migrations


def upgrade_role(apps, schema_editor):
    Role = apps.get_model('certificates', 'Role')
    Role.objects.filter(name_en='advanced_user').update(
        name_en='advanced_admin',
        name_ar='مشرف متقدم'
    )


def downgrade_role(apps, schema_editor):
    Role = apps.get_model('certificates', 'Role')
    Role.objects.filter(name_en='advanced_admin').update(
        name_en='advanced_user',
        name_ar='صلاحيات متقدمة'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0012_userprofile_is_temporary_role_and_more'),
    ]

    operations = [
        migrations.RunPython(upgrade_role, downgrade_role),
    ]

