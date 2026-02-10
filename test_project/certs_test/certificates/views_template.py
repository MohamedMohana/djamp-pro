from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .decorators import role_required
from django.contrib import messages
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt
from .forms_template import CertificateTemplateForm
from .models_template import CertificateTemplate
from .certificate_generator import generate_certificate
import os
import json
import tempfile
import time
import re


def sanitize_error_message(error_message):
    """
    Remove sensitive file paths from error messages for security.
    Replaces absolute paths with generic messages.
    """
    # Remove any absolute paths (starting with / or drive letters)
    sanitized = re.sub(r'/[\w/.-]+', '', str(error_message))
    sanitized = re.sub(r'[A-Za-z]:\\[\w\\.-]+', '', sanitized)
    # Remove "at:" artifacts
    sanitized = re.sub(r'\s+at:\s*', '', sanitized)
    # Clean up extra spaces
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized if sanitized else "حدث خطأ"

@login_required(login_url='/login/')
@role_required('can_view_templates')
def template_list(request):
    # Super admin can see all templates
    if request.user.is_superuser or request.user.profile.is_super_admin():
        templates = list(CertificateTemplate.objects.all().order_by('-created_at'))
    else:
        # Others can only see their own templates
        templates = list(CertificateTemplate.objects.filter(created_by=request.user).order_by('-created_at'))
    
    context = {
        'templates': templates,
        'can_create': request.user.profile.has_permission('can_create_templates'),
        'can_edit': request.user.profile.has_permission('can_edit_templates'),
        'can_delete': request.user.profile.has_permission('can_delete_templates'),
        'has_templates': bool(templates)  # Add this to check if there are any templates
    }
    return render(request, 'template_list.html', context)

@login_required(login_url='/login/')
@role_required('can_create_templates')
def template_create(request):
    if request.method == 'POST':
        form = CertificateTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                template = form.save(commit=False)
                template.created_by = request.user
                template.save()
                messages.success(request, 'تم حفظ القالب بنجاح')
                return redirect('template_list')
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f'حدث خطأ أثناء حفظ القالب: {error_msg}')
                return redirect('template_create')
        else:
            errors = []
            for field, error_list in form.errors.items():
                errors.append(f"{form.fields[field].label}: {', '.join(error_list)}")
            messages.error(request, '\n'.join(errors))
            return redirect('template_create')
    else:
        form = CertificateTemplateForm()

    context = {
        'form': form,
        'example_name': 'محمد أسامه محمد مهنا',
        'example_course': 'الذكاء الاصطناعي بلغة Python',
        'example_duration': '5 أيام'
    }
    return render(request, 'template_create.html', context)

@login_required(login_url='/login/')
@role_required('can_edit_templates')
def template_edit(request, template_id):
    template = get_object_or_404(CertificateTemplate, id=template_id)
    
    if request.method == 'POST':
        # If no new file is uploaded, use the existing one
        if not request.FILES.get('pdf_file'):
            request.POST = request.POST.copy()
            request.POST['pdf_file'] = template.pdf_file
        
        form = CertificateTemplateForm(request.POST, request.FILES, instance=template)
        if form.is_valid():
            try:
                # Save without committing to handle file
                new_template = form.save(commit=False)
                
                # If no new file was uploaded, keep the old one
                if not request.FILES.get('pdf_file'):
                    new_template.pdf_file = template.pdf_file
                
                # Save with the user
                new_template.created_by = request.user
                new_template.save()
                
                messages.success(request, 'تم تحديث القالب بنجاح')
                return redirect('template_list')
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f'حدث خطأ أثناء تحديث القالب: {error_msg}')
        else:
            errors = []
            for field, error_list in form.errors.items():
                errors.append(f"{form.fields[field].label}: {', '.join(error_list)}")
            messages.error(request, '\n'.join(errors))
    else:
        # Pre-fill the form with existing data
        initial_data = {
            'name': template.get_display_name(),  # Use display name with spaces
            'font_name': template.font_name,
            'font_color': template.font_color,
            'name_x': template.name_x,
            'name_y': template.name_y,
            'name_font_size': template.name_font_size,
            'course_x': template.course_x,
            'course_y': template.course_y,
            'course_font_size': template.course_font_size,
            'date_x': template.date_x,
            'date_y': template.date_y,
            'date_font_size': template.date_font_size,
            'qr_x': template.qr_x,
            'qr_y': template.qr_y,
            'qr_size': template.qr_size,
            'qr_rotation': template.qr_rotation,
        }
        form = CertificateTemplateForm(instance=template, initial=initial_data)

    context = {
        'form': form,
        'template': template,
        'example_name': 'محمد أسامه محمد مهنا',
        'example_course': 'الذكاء الاصطناعي بلغة Python',
        'example_duration': '5 أيام',
        'is_edit': True  # Flag to indicate this is an edit form
    }
    return render(request, 'template_create.html', context)

@login_required(login_url='/login/')
@role_required('can_delete_templates')
def template_delete(request, template_id):
    if request.method == 'POST':
        template = get_object_or_404(CertificateTemplate, id=template_id)
        try:
            # Delete the template files
            if template.pdf_file:
                if os.path.exists(template.pdf_file.path):
                    os.remove(template.pdf_file.path)
                json_path = os.path.splitext(template.pdf_file.path)[0] + '.json'
                if os.path.exists(json_path):
                    os.remove(json_path)
            
            # Delete the database record
            template.delete()
            messages.success(request, 'تم حذف القالب بنجاح')
        except Exception as e:
            error_msg = sanitize_error_message(str(e))
            messages.error(request, f'حدث خطأ أثناء حذف القالب: {error_msg}')
    
    return redirect('template_list')

@login_required(login_url='/login/')
@xframe_options_exempt
def template_preview(request):
    """Generate a preview of the certificate with current settings"""
    preview_dir = os.path.join(settings.MEDIA_ROOT, 'preview')
    temp_pdf_path = os.path.join(preview_dir, 'temp_template.pdf')
    temp_json_path = os.path.join(preview_dir, 'temp_template.json')

    if request.method == 'POST':
        try:
            # Create temporary directory for preview files
            os.makedirs(preview_dir, exist_ok=True)

            # Get the PDF file from either the uploaded file or the existing file URL
            pdf_file = request.FILES.get('pdf_file')
            pdf_url = request.POST.get('pdf_url')

            if not pdf_file and not pdf_url:
                return JsonResponse({'error': 'لم يتم توفير ملف PDF'}, status=400)

            # Create temporary directory for preview files
            preview_dir = os.path.join(settings.MEDIA_ROOT, 'preview')
            os.makedirs(preview_dir, exist_ok=True)
            temp_pdf_path = os.path.join(preview_dir, 'temp_template.pdf')
            temp_json_path = os.path.join(preview_dir, 'temp_template.json')

            # Get the settings from the form data
            settings_str = request.POST.get('settings', '{}')
            template_settings = json.loads(settings_str)
            
            if pdf_file:
                # If a new file was uploaded
                with open(temp_pdf_path, 'wb+') as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)
            elif pdf_url:
                # If using an existing file URL
                template_id = request.POST.get('template_id')
                if template_id:
                    try:
                        # Get the template object
                        template = CertificateTemplate.objects.get(id=template_id)
                        # Use the template's PDF file directly
                        import shutil
                        shutil.copy2(template.pdf_file.path, temp_pdf_path)
                        # Also copy the JSON config file if it exists
                        json_path = os.path.splitext(template.pdf_file.path)[0] + '.json'
                        if os.path.exists(json_path):
                            shutil.copy2(json_path, temp_json_path)
                        found = True
                    except CertificateTemplate.DoesNotExist:
                        return JsonResponse({'error': 'القالب غير موجود'}, status=404)
                else:
                    # If no template_id, try to find the file from the URL
                    if pdf_url.startswith('/'):
                        pdf_url = pdf_url.lstrip('/')
                    paths_to_try = [
                        os.path.join(settings.BASE_DIR, pdf_url),
                        os.path.join(settings.BASE_DIR, 'workspace', pdf_url)
                    ]
                    found = False
                    for pdf_path in paths_to_try:
                        if os.path.exists(pdf_path):
                            import shutil
                            shutil.copy2(pdf_path, temp_pdf_path)
                            # Also copy the JSON config file if it exists
                            json_path = os.path.splitext(pdf_path)[0] + '.json'
                            if os.path.exists(json_path):
                                shutil.copy2(json_path, temp_json_path)
                            found = True
                            break
                    if not found:
                        return JsonResponse({'error': 'ملف PDF غير موجود'}, status=400)

            # Make sure the file exists
            if not os.path.exists(temp_pdf_path):
                return JsonResponse({'error': 'فشل في حفظ ملف PDF'}, status=400)

            # Generate preview certificate
            preview_path = os.path.join(preview_dir, 'preview.pdf')
            
            # Convert color from hex to RGB
            color_hex = template_settings.get('font_color', '000000')
            if color_hex.startswith('#'):
                color_hex = color_hex[1:]
            rgb = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))

            # Save template settings as JSON
            temp_json_path = os.path.join(preview_dir, 'temp_template.json')
            with open(temp_json_path, 'w') as f:
                json.dump({
                    'font_name': template_settings['font_name'] or 'din-next-lt-w23-bold',
                    'font_color': rgb,
                    'name': template_settings['name'],
                    'course_name': template_settings['course_name'],
                    'date_text': template_settings['date_text'],
                    'qr_code': template_settings['qr_code']
                }, f)

            # Generate the preview
            generate_certificate(
                request.POST.get('example_name', 'محمد أسامه محمد مهنا'),
                request.POST.get('example_course', 'الذكاء الاصطناعي'),
                request.POST.get('example_duration', '5 أيام'),
                'preview',  # This is just for preview
                'temp_template',  # This will look for temp_template.pdf and temp_template.json
                preview_path
            )

            # Return the preview URL
            preview_url = f'/template/preview_pdf/?t={int(time.time())}'
            return JsonResponse({'preview_url': preview_url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'طلب غير صالح'}, status=400)

@login_required(login_url='/login/')
@xframe_options_exempt
def preview_pdf(request):
    """Serve the preview PDF file"""
    preview_path = os.path.join(settings.MEDIA_ROOT, 'preview', 'preview.pdf')
    if os.path.exists(preview_path):
        response = FileResponse(open(preview_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="preview.pdf"'
        return response
    return JsonResponse({'error': 'المعاينة غير موجودة'}, status=404)