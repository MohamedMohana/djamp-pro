#!/usr/bin/env python
"""
Check if Advanced Certificate System is properly set up
Run this before testing: python check_advanced_setup.py
"""
import os
import sys

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
END = '\033[0m'

def check_item(name, condition, success_msg, error_msg):
    """Check a condition and print result"""
    if condition:
        print(f"{GREEN}✓{END} {name}: {success_msg}")
        return True
    else:
        print(f"{RED}✗{END} {name}: {error_msg}")
        return False

def main():
    print(f"\n{BLUE}{'='*60}{END}")
    print(f"{BLUE}KKU Advanced Certificate System - Setup Checker{END}")
    print(f"{BLUE}{'='*60}{END}\n")
    
    all_good = True
    
    # Check 1: Python files
    print(f"{YELLOW}[1] Checking Python Files...{END}")
    files_to_check = [
        'certificates/constants.py',
        'certificates/models_advanced.py',
        'certificates/forms_advanced.py',
        'certificates/views_advanced_template.py',
        'certificates/views_advanced.py',
        'certificates/advanced_generator.py',
        'create_advanced_role.py',
    ]
    
    for file_path in files_to_check:
        exists = os.path.exists(file_path)
        all_good &= check_item(
            f"  {file_path}",
            exists,
            "Found",
            "Missing!"
        )
    
    # Check 2: Fonts
    print(f"\n{YELLOW}[2] Checking IBM Plex Sans Arabic Fonts...{END}")
    fonts_dir = 'certificates/fonts'
    required_fonts = [
        'IBMPlexSansArabic-Bold.ttf',
        'IBMPlexSansArabic-Regular.ttf',
    ]
    
    for font in required_fonts:
        font_path = os.path.join(fonts_dir, font)
        exists = os.path.exists(font_path)
        all_good &= check_item(
            f"  {font}",
            exists,
            "Found",
            f"Missing! Download from Google Fonts"
        )
    
    if not all([os.path.exists(os.path.join(fonts_dir, f)) for f in required_fonts]):
        print(f"\n{RED}  → Download fonts from: https://fonts.google.com/specimen/IBM+Plex+Sans+Arabic{END}")
        print(f"{RED}  → Save to: {os.path.abspath(fonts_dir)}/{END}\n")
    
    # Check 3: Template directories
    print(f"\n{YELLOW}[3] Checking Template Directories...{END}")
    template_dirs = [
        'certificates/templates/advanced',
        'media/advanced_templates',
        'media/preview',
    ]
    
    for dir_path in template_dirs:
        exists = os.path.exists(dir_path)
        if not exists:
            try:
                os.makedirs(dir_path, exist_ok=True)
                check_item(f"  {dir_path}", True, "Created", "")
            except:
                all_good &= check_item(f"  {dir_path}", False, "", "Cannot create directory")
        else:
            check_item(f"  {dir_path}", True, "Exists", "")
    
    # Check 4: Django setup
    print(f"\n{YELLOW}[4] Checking Django Configuration...{END}")
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_certificates.settings')
        import django
        django.setup()
        check_item("  Django setup", True, "Success", "")
        
        # Check if models exist
        try:
            from certificates.models_advanced import AdvancedCertificateTemplate, AdvancedCertificate
            check_item("  Advanced models", True, "Imported successfully", "")
        except ImportError as e:
            all_good &= check_item("  Advanced models", False, "", f"Import error: {e}")
        
        # Check if Role model has new fields
        try:
            from certificates.models_role import Role
            role = Role()
            has_fields = (
                hasattr(role, 'can_view_advanced_templates') and
                hasattr(role, 'can_create_advanced_templates') and
                hasattr(role, 'can_view_advanced_certificates') and
                hasattr(role, 'can_create_advanced_certificates')
            )
            all_good &= check_item(
                "  Role permissions", 
                has_fields, 
                "All advanced permissions found",
                "Missing advanced permission fields - Run migrations!"
            )
        except Exception as e:
            all_good &= check_item("  Role permissions", False, "", f"Error: {e}")
        
        # Check if migrations are needed
        from django.core.management import call_command
        from io import StringIO
        buf = StringIO()
        try:
            call_command('makemigrations', '--dry-run', stdout=buf, no_input=True)
            output = buf.getvalue()
            needs_migration = 'No changes detected' not in output and len(output.strip()) > 0
            
            if needs_migration:
                all_good = False
                print(f"{RED}  ✗ Migrations needed: Run 'python manage.py makemigrations' then 'python manage.py migrate'{END}")
            else:
                check_item("  Database migrations", True, "Up to date", "")
        except Exception as e:
            print(f"{YELLOW}  ? Cannot check migrations: {e}{END}")
        
    except Exception as e:
        all_good &= check_item("  Django setup", False, "", f"Error: {e}")
    
    # Check 5: HTML Templates
    print(f"\n{YELLOW}[5] Checking HTML Templates...{END}")
    html_templates = [
        'certificates/templates/advanced/template_list.html',
        'certificates/templates/advanced/template_create.html',
        'certificates/templates/advanced/create_certificate.html',
        'certificates/templates/advanced/manage_certificates.html',
        'certificates/templates/advanced/success_redirect.html',
        'certificates/templates/validate_advanced.html',
    ]
    
    missing_templates = []
    for template in html_templates:
        exists = os.path.exists(template)
        if exists:
            check_item(f"  {os.path.basename(template)}", True, "Found", "")
        else:
            missing_templates.append(template)
            check_item(f"  {os.path.basename(template)}", False, "", "Missing - needs to be created")
    
    if missing_templates:
        all_good = False
        print(f"\n{YELLOW}  → {len(missing_templates)} HTML template(s) need to be created{END}")
    
    # Final Summary
    print(f"\n{BLUE}{'='*60}{END}")
    if all_good and not missing_templates:
        print(f"{GREEN}✓ All checks passed! System is ready to use.{END}")
        print(f"\n{BLUE}Next steps:{END}")
        print(f"  1. Run: python create_advanced_role.py")
        print(f"  2. Assign 'مشرف متقدم' role to users via /users/")
        print(f"  3. Test template creation: /advanced/templates/create/")
    elif missing_templates and not all_good:
        print(f"{RED}✗ Setup incomplete - Multiple issues found{END}")
        print(f"\n{YELLOW}Critical issues:{END}")
        print(f"  1. Download IBM Plex Sans Arabic fonts")
        print(f"  2. Run database migrations")
        print(f"  3. Create {len(missing_templates)} HTML templates")
    elif missing_templates:
        print(f"{YELLOW}⚠ Backend ready, but HTML templates missing{END}")
        print(f"\n{YELLOW}Next step:{END}")
        print(f"  Create {len(missing_templates)} HTML template files")
    else:
        print(f"{RED}✗ Setup incomplete - Check errors above{END}")
    
    print(f"{BLUE}{'='*60}{END}\n")
    
    return 0 if all_good else 1

if __name__ == '__main__':
    sys.exit(main())

