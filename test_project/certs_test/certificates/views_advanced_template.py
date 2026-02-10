"""
Views for Advanced Certificate Template Management (KKUx)
5-Step Template Creation Wizard with Dynamic Field Configuration
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt
from django.db import transaction
from .decorators import role_required
from .models_advanced import AdvancedCertificateTemplate
from .forms_advanced import AdvancedTemplateForm
from .advanced_generator import generate_advanced_certificate
from .constants import ADVANCED_CERTIFICATE_FIELDS, ADVANCED_FONTS, DEFAULT_FIELD_SETTINGS
import os
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


def _get_designer_dimension(value, default):
    try:
        dim = float(value)
    except (TypeError, ValueError):
        dim = default
    if dim <= 0:
        dim = default
    return dim
import json
import tempfile
import time
import shutil


@login_required(login_url='/login/')
@role_required('can_view_advanced_templates')
def template_list(request):
    """List all advanced templates"""
    # Super admin can see all templates
    if request.user.is_superuser or request.user.profile.is_super_admin():
        templates = list(AdvancedCertificateTemplate.objects.all().order_by('-created_at'))
    else:
        # Others can only see their own templates
        templates = list(AdvancedCertificateTemplate.objects.filter(created_by=request.user).order_by('-created_at'))
    
    context = {
        'templates': templates,
        'can_create': request.user.profile.has_permission('can_create_advanced_templates'),
        'can_edit': request.user.profile.has_permission('can_edit_advanced_templates'),
        'can_delete': request.user.profile.has_permission('can_delete_advanced_templates'),
        'has_templates': bool(templates),
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    return render(request, 'advanced/template_list.html', context)


@login_required(login_url='/login/')
@role_required('can_create_advanced_templates')
def template_create(request):
    """Create new advanced template - 5 Step Wizard"""
    if request.method == 'POST':
        form = AdvancedTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                template = form.save(commit=False)
                template.created_by = request.user
                
                designer_width = _get_designer_dimension(request.POST.get('designer_page_width_cm'), 29.7)
                designer_height = _get_designer_dimension(request.POST.get('designer_page_height_cm'), 21)
                designer_width_px = _get_designer_dimension(request.POST.get('designer_page_width_px'), 0)
                designer_height_px = _get_designer_dimension(request.POST.get('designer_page_height_px'), 0)
                designer_width_px = _get_designer_dimension(request.POST.get('designer_page_width_px'), 0)
                designer_height_px = _get_designer_dimension(request.POST.get('designer_page_height_px'), 0)
                designer_width_px = _get_designer_dimension(request.POST.get('designer_page_width_px'), 0)
                designer_height_px = _get_designer_dimension(request.POST.get('designer_page_height_px'), 0)
                designer_width_px = _get_designer_dimension(request.POST.get('designer_page_width_px'), 0)
                designer_height_px = _get_designer_dimension(request.POST.get('designer_page_height_px'), 0)
                
                # Get active fields from POST data
                active_fields = {}
                for field_name in ADVANCED_CERTIFICATE_FIELDS.keys():
                    active_fields[field_name] = request.POST.get(f'field_active_{field_name}') == 'on'
                template.active_fields = active_fields
                
                # Get field settings from POST data
                field_settings = {}
                for field_name in ADVANCED_CERTIFICATE_FIELDS.keys():
                    if active_fields.get(field_name):
                        field_settings[field_name] = {
                            'x': float(request.POST.get(f'field_x_{field_name}', 15)),
                            'y': float(request.POST.get(f'field_y_{field_name}', 10)),
                            'font_size': float(request.POST.get(f'field_font_size_{field_name}', 18)),
                            'font_name': request.POST.get(f'field_font_{field_name}', 'IBM_Plex_Sans_Arabic_Regular'),
                            'font_color': request.POST.get(f'field_color_{field_name}', '#000000'),
                            'text_direction': ADVANCED_CERTIFICATE_FIELDS[field_name]['direction'],
                            'base_width_cm': designer_width,
                            'base_height_cm': designer_height,
                            'base_width_px': designer_width_px or None,
                            'base_height_px': designer_height_px or None,
                            'text_anchor': 'left',
                            'enabled': True
                        }
                        x_px_val = request.POST.get(f'field_x_px_{field_name}')
                        y_px_val = request.POST.get(f'field_y_px_{field_name}')
                        width_px_val = request.POST.get(f'field_width_px_{field_name}')
                        height_px_val = request.POST.get(f'field_height_px_{field_name}')
                        font_size_px_val = request.POST.get(f'field_font_size_px_{field_name}')
                        if x_px_val not in [None, '']:
                            field_settings[field_name]['x_px'] = float(x_px_val)
                        if y_px_val not in [None, '']:
                            field_settings[field_name]['y_px'] = float(y_px_val)
                        width_px_val = request.POST.get(f'field_width_px_{field_name}')
                        height_px_val = request.POST.get(f'field_height_px_{field_name}')
                        font_size_px_val = request.POST.get(f'field_font_size_px_{field_name}')
                        if width_px_val not in [None, '']:
                            field_settings[field_name]['box_width_px'] = float(width_px_val)
                        if height_px_val not in [None, '']:
                            field_settings[field_name]['box_height_px'] = float(height_px_val)
                        if font_size_px_val not in [None, '']:
                            field_settings[field_name]['font_size_px'] = float(font_size_px_val)
                        if width_px_val not in [None, '']:
                            field_settings[field_name]['box_width_px'] = float(width_px_val)
                        if height_px_val not in [None, '']:
                            field_settings[field_name]['box_height_px'] = float(height_px_val)
                        if font_size_px_val not in [None, '']:
                            field_settings[field_name]['font_size_px'] = float(font_size_px_val)
                template.field_settings = field_settings
                
                # Get QR settings
                qr_settings = {
                    'x': float(request.POST.get('qr_x', 6.9)),
                    'y': float(request.POST.get('qr_y', 1.2)),
                    'size': float(request.POST.get('qr_size', 5)),
                    'rotation_angle': float(request.POST.get('qr_rotation', 0)),
                    'base_width_cm': designer_width,
                    'base_height_cm': designer_height,
                    'base_width_px': designer_width_px or None,
                    'base_height_px': designer_height_px or None
                }
                qr_x_px = request.POST.get('qr_x_px')
                qr_y_px = request.POST.get('qr_y_px')
                qr_size_px = request.POST.get('qr_size_px')
                if qr_x_px not in [None, '']:
                    qr_settings['x_px'] = float(qr_x_px)
                if qr_y_px not in [None, '']:
                    qr_settings['y_px'] = float(qr_y_px)
                if qr_size_px not in [None, '']:
                    qr_settings['size_px'] = float(qr_size_px)
                template.qr_settings = qr_settings
                
                template.save()
                messages.success(request, 'تم حفظ القالب المتقدم بنجاح')
                return redirect('advanced_template_list')
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f'حدث خطأ أثناء حفظ القالب: {error_msg}')
                return redirect('advanced_template_create')
        else:
            errors = []
            for field, error_list in form.errors.items():
                errors.append(f"{form.fields.get(field, field).label if field != '__all__' else 'خطأ'}: {', '.join(error_list)}")
            messages.error(request, '\n'.join(errors))
            return redirect('advanced_template_create')
    else:
        form = AdvancedTemplateForm()

    # Pre-filled example data for all 15 fields
    example_data = {
        'arabic_name': 'محمد أسامه محمد مهنا',
        'english_name': 'Mohamed Osama Mohamed Mohana',
        'national_id_ar': '١٢٣٤٥٦٧٨٩',
        'national_id_en': '123456789',
        'program_name_ar': 'دبـلــوم الحوكمــــة',
        'program_name_en': 'Diploma in Governance',
        'courses_count_ar': '٨',
        'courses_count_en': '8',
        'duration_ar': '١٢',
        'duration_en': '12',
        'grade_ar': 'ممتاز',
        'grade_en': 'Excellent',
        'gpa_ar': '٤.٥',
        'gpa_en': '4.5',
        'issue_date': '15-02-2024'
    }
    
    context = {
        'form': form,
        'fields': ADVANCED_CERTIFICATE_FIELDS,
        'fields_json': json.dumps(ADVANCED_CERTIFICATE_FIELDS),
        'fonts': ADVANCED_FONTS,
        'example_data': json.dumps(example_data),
        'designer_width_cm': 29.7,
        'designer_height_cm': 21,
        'designer_width_px': 0,
        'designer_height_px': 0,
        'template_active_fields_json': json.dumps({}),
        'template_field_settings_json': json.dumps({}, ensure_ascii=False),
        'template_qr_settings_json': json.dumps({}, ensure_ascii=False),
        'template_pdf_url': '',
        'is_edit': False,
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    return render(request, 'advanced/template_create.html', context)


@login_required(login_url='/login/')
@role_required('can_edit_advanced_templates')
def template_edit(request, template_id):
    """Edit existing advanced template"""
    template = get_object_or_404(AdvancedCertificateTemplate, id=template_id)
    
    # Check permissions
    if not (request.user.is_superuser or template.created_by == request.user):
        messages.error(request, 'ليس لديك صلاحية لتعديل هذا القالب')
        return redirect('advanced_template_list')
    
    if request.method == 'POST':
        # If no new file is uploaded, use the existing one
        if not request.FILES.get('pdf_file'):
            request.POST = request.POST.copy()
            request.POST['pdf_file'] = template.pdf_file
        
        form = AdvancedTemplateForm(request.POST, request.FILES, instance=template)
        if form.is_valid():
            try:
                new_template = form.save(commit=False)
                
                designer_width = _get_designer_dimension(request.POST.get('designer_page_width_cm'), 29.7)
                designer_height = _get_designer_dimension(request.POST.get('designer_page_height_cm'), 21)
                designer_width_px = _get_designer_dimension(request.POST.get('designer_page_width_px'), 0)
                designer_height_px = _get_designer_dimension(request.POST.get('designer_page_height_px'), 0)
                
                # If no new file was uploaded, keep the old one
                if not request.FILES.get('pdf_file'):
                    new_template.pdf_file = template.pdf_file
                
                new_template.created_by = request.user
                
                # Update active fields
                active_fields = {}
                for field_name in ADVANCED_CERTIFICATE_FIELDS.keys():
                    active_fields[field_name] = request.POST.get(f'field_active_{field_name}') == 'on'
                new_template.active_fields = active_fields
                
                # Update field settings
                field_settings = {}
                for field_name in ADVANCED_CERTIFICATE_FIELDS.keys():
                    if active_fields.get(field_name):
                        field_settings[field_name] = {
                            'x': float(request.POST.get(f'field_x_{field_name}', 15)),
                            'y': float(request.POST.get(f'field_y_{field_name}', 10)),
                            'font_size': float(request.POST.get(f'field_font_size_{field_name}', 18)),
                            'font_name': request.POST.get(f'field_font_{field_name}', 'IBM_Plex_Sans_Arabic_Regular'),
                            'font_color': request.POST.get(f'field_color_{field_name}', '#000000'),
                            'text_direction': ADVANCED_CERTIFICATE_FIELDS[field_name]['direction'],
                            'base_width_cm': designer_width,
                            'base_height_cm': designer_height,
                            'base_width_px': designer_width_px or None,
                            'base_height_px': designer_height_px or None,
                            'text_anchor': 'left',
                            'enabled': True
                        }
                        x_px_val = request.POST.get(f'field_x_px_{field_name}')
                        y_px_val = request.POST.get(f'field_y_px_{field_name}')
                        width_px_val = request.POST.get(f'field_width_px_{field_name}')
                        height_px_val = request.POST.get(f'field_height_px_{field_name}')
                        font_size_px_val = request.POST.get(f'field_font_size_px_{field_name}')
                        if x_px_val not in [None, '']:
                            field_settings[field_name]['x_px'] = float(x_px_val)
                        if y_px_val not in [None, '']:
                            field_settings[field_name]['y_px'] = float(y_px_val)
                        if width_px_val not in [None, '']:
                            field_settings[field_name]['box_width_px'] = float(width_px_val)
                        if height_px_val not in [None, '']:
                            field_settings[field_name]['box_height_px'] = float(height_px_val)
                        if font_size_px_val not in [None, '']:
                            field_settings[field_name]['font_size_px'] = float(font_size_px_val)
                new_template.field_settings = field_settings
                
                # Update QR settings
                qr_settings = {
                    'x': float(request.POST.get('qr_x', 6.9)),
                    'y': float(request.POST.get('qr_y', 1.2)),
                    'size': float(request.POST.get('qr_size', 5)),
                    'rotation_angle': float(request.POST.get('qr_rotation', 0)),
                    'base_width_cm': designer_width,
                    'base_height_cm': designer_height,
                    'base_width_px': designer_width_px or None,
                    'base_height_px': designer_height_px or None
                }
                qr_x_px = request.POST.get('qr_x_px')
                qr_y_px = request.POST.get('qr_y_px')
                qr_size_px = request.POST.get('qr_size_px')
                if qr_x_px not in [None, '']:
                    qr_settings['x_px'] = float(qr_x_px)
                if qr_y_px not in [None, '']:
                    qr_settings['y_px'] = float(qr_y_px)
                if qr_size_px not in [None, '']:
                    qr_settings['size_px'] = float(qr_size_px)
                new_template.qr_settings = qr_settings
                
                new_template.save()
                messages.success(request, 'تم تحديث القالب المتقدم بنجاح')
                return redirect('advanced_template_list')
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f'حدث خطأ أثناء تحديث القالب: {error_msg}')
        else:
            errors = []
            for field, error_list in form.errors.items():
                errors.append(f"{form.fields.get(field, field).label if field != '__all__' else 'خطأ'}: {', '.join(error_list)}")
            messages.error(request, '\n'.join(errors))
    else:
        # Pre-fill the form with existing data
        initial_data = {
            'name': template.get_display_name(),
            'certificate_type': template.certificate_type
        }
        form = AdvancedTemplateForm(instance=template, initial=initial_data)

    designer_width_cm = 29.7
    designer_height_cm = 21
    designer_width_px = 0
    designer_height_px = 0
    if template.field_settings:
        for settings in template.field_settings.values():
            designer_width_cm = settings.get('base_width_cm', designer_width_cm)
            designer_height_cm = settings.get('base_height_cm', designer_height_cm)
            designer_width_px = settings.get('base_width_px', designer_width_px)
            designer_height_px = settings.get('base_height_px', designer_height_px)
            break
    if template.qr_settings:
        designer_width_cm = template.qr_settings.get('base_width_cm', designer_width_cm)
        designer_height_cm = template.qr_settings.get('base_height_cm', designer_height_cm)
        designer_width_px = template.qr_settings.get('base_width_px', designer_width_px)
        designer_height_px = template.qr_settings.get('base_height_px', designer_height_px)

    # Pre-filled example data for all 15 fields
    example_data = {
        'arabic_name': 'محمد أسامه محمد مهنا',
        'english_name': 'Mohamed Osama Mohamed Mohana',
        'national_id_ar': '١٢٣٤٥٦٧٨٩',
        'national_id_en': '123456789',
        'program_name_ar': 'دبـلــوم الحوكمــــة',
        'program_name_en': 'Diploma in Governance',
        'courses_count_ar': '٨',
        'courses_count_en': '8',
        'duration_ar': '١٢',
        'duration_en': '12',
        'grade_ar': 'ممتاز',
        'grade_en': 'Excellent',
        'gpa_ar': '٤.٥',
        'gpa_en': '4.5',
        'issue_date': '15-02-2024'
    }
    
    context = {
        'form': form,
        'template': template,
        'fields': ADVANCED_CERTIFICATE_FIELDS,
        'fields_json': json.dumps(ADVANCED_CERTIFICATE_FIELDS),
        'fonts': ADVANCED_FONTS,
        'example_data': json.dumps(example_data),
        'is_edit': True,
        'designer_width_cm': designer_width_cm,
        'designer_height_cm': designer_height_cm,
        'designer_width_px': designer_width_px,
        'designer_height_px': designer_height_px,
        'template_active_fields_json': json.dumps(template.active_fields or {}, ensure_ascii=False),
        'template_field_settings_json': json.dumps(template.field_settings or {}, ensure_ascii=False),
        'template_qr_settings_json': json.dumps(template.qr_settings or {}, ensure_ascii=False),
        'template_pdf_url': template.pdf_file.url if template.pdf_file else '',
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    return render(request, 'advanced/template_create.html', context)


@login_required(login_url='/login/')
@role_required('can_delete_advanced_templates')
def template_delete(request, template_id):
    """Delete advanced template"""
    if request.method == 'POST':
        template = get_object_or_404(AdvancedCertificateTemplate, id=template_id)
        
        # Check permissions
        if not (request.user.is_superuser or template.created_by == request.user):
            messages.error(request, 'ليس لديك صلاحية لحذف هذا القالب')
            return redirect('advanced_template_list')
        
        try:
            template_name = template.get_display_name()
            with transaction.atomic():
                related_count = template.certificates.count()
                if related_count:
                    template.certificates.all().delete()
                template.delete()  # Signal will handle file deletion
            if related_count:
                messages.success(
                    request,
                    f'تم حذف القالب "{template_name}" وكل الشهادات المتقدمة المرتبطة به (عددها {related_count}) بنجاح'
                )
            else:
                messages.success(request, f'تم حذف القالب "{template_name}" بنجاح')
        except Exception as e:
            error_msg = sanitize_error_message(str(e))
            messages.error(request, f'حدث خطأ أثناء حذف القالب: {error_msg}')
    
    return redirect('advanced_template_list')


@login_required(login_url='/login/')
@xframe_options_exempt
def template_preview(request):
    """Generate preview of advanced certificate with current settings"""
    preview_dir = os.path.join(settings.MEDIA_ROOT, 'preview')
    temp_pdf_path = os.path.join(preview_dir, 'temp_advanced_template.pdf')
    temp_json_path = os.path.join(preview_dir, 'temp_advanced_template.json')

    if request.method == 'POST':
        try:
            # Create temporary directory for preview files
            os.makedirs(preview_dir, exist_ok=True)

            # Get the PDF file from either the uploaded file or the existing file URL
            pdf_file = request.FILES.get('pdf_file')
            pdf_url = request.POST.get('pdf_url')
            template_id = request.POST.get('template_id')

            if not pdf_file and not pdf_url:
                return JsonResponse({'error': 'لم يتم توفير ملف PDF'}, status=400)

            # Handle PDF file
            if pdf_file:
                # If a new file was uploaded
                with open(temp_pdf_path, 'wb+') as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)
            elif pdf_url and template_id:
                # If using an existing file URL
                try:
                    template = AdvancedCertificateTemplate.objects.get(id=template_id)
                    shutil.copy2(template.pdf_file.path, temp_pdf_path)
                except AdvancedCertificateTemplate.DoesNotExist:
                    return JsonResponse({'error': 'القالب غير موجود'}, status=404)

            # Make sure the file exists
            if not os.path.exists(temp_pdf_path):
                return JsonResponse({'error': 'فشل في حفظ ملف PDF'}, status=400)

            # Get settings from POST data
            settings_str = request.POST.get('settings', '{}')
            template_settings = json.loads(settings_str)
            
            # Get example data from POST
            example_data = {}
            active_fields = template_settings.get('active_fields', {})
            for field_name, is_active in active_fields.items():
                if is_active:
                    example_value = request.POST.get(f'example_{field_name}', '')
                    if example_value:
                        example_data[field_name] = example_value

            # Generate preview certificate
            preview_path = os.path.join(preview_dir, 'preview_advanced.pdf')
            
            # Create a mock template object for preview
            class MockTemplate:
                class MockPdfFile:
                    def __init__(self, file_path):
                        self.path = file_path
                
                def __init__(self, settings_data, pdf_path):
                    self.pdf_file = self.MockPdfFile(pdf_path)
                    self.active_fields = settings_data.get('active_fields', {})
                    self.field_settings = settings_data.get('field_settings', {})
                    self.qr_settings = settings_data.get('qr_settings', {})
            
            mock_template = MockTemplate(template_settings, temp_pdf_path)
            
            # Generate the preview
            generate_advanced_certificate(
                certificate_data=example_data,
                hash_value='preview',
                template=mock_template,
                output_file=preview_path
            )

            # Return the preview URL
            preview_url = f'/advanced/templates/preview_pdf/?t={int(time.time())}'
            return JsonResponse({'preview_url': preview_url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'طلب غير صالح'}, status=400)


@login_required(login_url='/login/')
@xframe_options_exempt
def preview_pdf(request):
    """Serve the preview PDF file"""
    preview_path = os.path.join(settings.MEDIA_ROOT, 'preview', 'preview_advanced.pdf')
    if os.path.exists(preview_path):
        response = FileResponse(open(preview_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="preview.pdf"'
        return response
    return JsonResponse({'error': 'المعاينة غير موجودة'}, status=404)

