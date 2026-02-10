import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
django.setup()

from django.contrib.auth.models import User
from certificates.models_template import CertificateTemplate
from django.conf import settings

def add_template(name, pdf_path, json_path, user):
    # Read JSON config
    with open(json_path, 'r') as f:
        config = json.load(f)
    
    # Convert hex color to RGB
    color_hex = config.get('font_color', [0, 0, 0])
    if isinstance(color_hex, list):
        color_hex = '#{:02x}{:02x}{:02x}'.format(*color_hex)
    
    # Copy file to media directory if needed
    if not pdf_path.startswith(str(settings.MEDIA_ROOT)):
        import shutil
        new_pdf_path = os.path.join(settings.MEDIA_ROOT, 'pdf_templates', os.path.basename(pdf_path))
        new_json_path = os.path.join(settings.MEDIA_ROOT, 'pdf_templates', os.path.basename(json_path))
        os.makedirs(os.path.dirname(new_pdf_path), exist_ok=True)
        shutil.copy2(pdf_path, new_pdf_path)
        shutil.copy2(json_path, new_json_path)
        pdf_path = new_pdf_path
    
    # Clean name
    clean_name = name.replace(' ', '_').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    
    # Check if template already exists
    try:
        template = CertificateTemplate.objects.get(name=clean_name)
        return
    except CertificateTemplate.DoesNotExist:
        pass
    
    # Create template
    template = CertificateTemplate(
        name=clean_name,
        pdf_file=pdf_path.replace(str(settings.MEDIA_ROOT) + '/', ''),
        font_name=config.get('font_name', 'din-next-lt-w23-bold'),
        font_color=color_hex,
        name_x=config['name']['x'],
        name_y=config['name']['y'],
        name_font_size=config['name']['font_size'],
        course_x=config['course_name']['x'],
        course_y=config['course_name']['y'],
        course_font_size=config['course_name']['font_size'],
        date_x=config['date_text']['x'],
        date_y=config['date_text']['y'],
        date_font_size=config['date_text']['font_size'],
        qr_x=config['qr_code']['x'],
        qr_y=config['qr_code']['y'],
        qr_size=config['qr_code']['size'],
        qr_rotation=config['qr_code'].get('rotation_angle', 0)
    )
    template.save()

def main():
    # Get or create admin user
    user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        user.set_password('admin')
        user.save()

    # Add templates from media/pdf_templates
    media_templates_dir = os.path.join(settings.MEDIA_ROOT, 'pdf_templates')
    for filename in os.listdir(media_templates_dir):
        if filename.endswith('.pdf'):
            name = os.path.splitext(filename)[0]
            pdf_path = os.path.join(media_templates_dir, filename)
            json_path = os.path.join(media_templates_dir, name + '.json')
            if os.path.exists(json_path):
                add_template(name, pdf_path, json_path, user)

    # Add templates from certificates/pdf_templates
    cert_templates_dir = os.path.join(settings.BASE_DIR, 'certificates/pdf_templates')
    for filename in os.listdir(cert_templates_dir):
        if filename.endswith('.pdf'):
            name = os.path.splitext(filename)[0]
            pdf_path = os.path.join(cert_templates_dir, filename)
            json_path = os.path.join(cert_templates_dir, name + '.json')
            if os.path.exists(json_path):
                add_template(name, pdf_path, json_path, user)

if __name__ == '__main__':
    main()