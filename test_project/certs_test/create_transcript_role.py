import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()

from certificates.models_role import Role

# Create or update transcript_admin role
transcript_admin, created = Role.objects.get_or_create(
    name_en='transcript_admin',
    defaults={
        'name_ar': 'مشرف سجلات',
        # Transcript permissions
        'can_view_transcript_templates': True,
        'can_create_transcript_templates': True,
        'can_edit_transcript_templates': True,
        'can_delete_transcript_templates': True,
        'can_view_transcripts': True,
        'can_create_transcripts': True,
        # Basic permissions
        'can_verify_certificates': True,
    }
)

if created:
    print("✅ Created new role: مشرف سجلات (transcript_admin)")
else:
    # Update existing role with transcript permissions
    transcript_admin.name_ar = 'مشرف سجلات'
    transcript_admin.can_view_transcript_templates = True
    transcript_admin.can_create_transcript_templates = True
    transcript_admin.can_edit_transcript_templates = True
    transcript_admin.can_delete_transcript_templates = True
    transcript_admin.can_view_transcripts = True
    transcript_admin.can_create_transcripts = True
    transcript_admin.can_verify_certificates = True
    transcript_admin.save()
    print("✅ Updated existing role: مشرف سجلات (transcript_admin)")

print(f"\nRole details:")
print(f"  - Name (AR): {transcript_admin.name_ar}")
print(f"  - Name (EN): {transcript_admin.name_en}")
print(f"  - Transcript Template Permissions: View={transcript_admin.can_view_transcript_templates}, Create={transcript_admin.can_create_transcript_templates}, Edit={transcript_admin.can_edit_transcript_templates}, Delete={transcript_admin.can_delete_transcript_templates}")
print(f"  - Transcript Permissions: View={transcript_admin.can_view_transcripts}, Create={transcript_admin.can_create_transcripts}")
