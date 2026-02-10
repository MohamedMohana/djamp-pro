"""
Views for Transcript Template Management (سجل المقررات)
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
from .models_transcript import TranscriptTemplate
from .forms_transcript import TranscriptTemplateForm
from .transcript_generator import generate_transcript
from .constants_transcript import (
    TRANSCRIPT_FIELDS,
    TRANSCRIPT_FIELD_CATEGORIES,
    DEFAULT_TRANSCRIPT_FIELD_SETTINGS,
    MAX_COURSES,
    get_base_fields,
    get_course_fields_for_count
)
from .constants import ADVANCED_FONTS
import os
import re
import json
import tempfile
import time
import shutil


def sanitize_error_message(error_message):
    """
    Remove sensitive file paths from error messages for security.
    """
    sanitized = re.sub(r'/[\w/.-]+', '', str(error_message))
    sanitized = re.sub(r'[A-Za-z]:\\[\w\\.-]+', '', sanitized)
    sanitized = re.sub(r'\s+at:\s*', '', sanitized)
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


def _is_super_admin(user):
    """Check if user is a super admin with proper error handling"""
    if user.is_superuser:
        return True
    try:
        if hasattr(user, 'profile') and user.profile:
            return user.profile.is_super_admin()
    except AttributeError:
        pass
    return False


@login_required(login_url='/login/')
@role_required('can_view_transcript_templates')
def template_list(request):
    """List all transcript templates"""
    if _is_super_admin(request.user):
        templates = list(TranscriptTemplate.objects.all().order_by('-created_at'))
    else:
        templates = list(TranscriptTemplate.objects.filter(created_by=request.user).order_by('-created_at'))
    
    context = {
        'templates': templates,
        'can_create': request.user.profile.has_permission('can_create_transcript_templates'),
        'can_edit': request.user.profile.has_permission('can_edit_transcript_templates'),
        'can_delete': request.user.profile.has_permission('can_delete_transcript_templates'),
        'has_templates': bool(templates),
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    return render(request, 'transcript/template_list.html', context)


@login_required(login_url='/login/')
@role_required('can_create_transcript_templates')
def template_create(request):
    """Create new transcript template - 5 Step Wizard"""
    if request.method == 'POST':
        form = TranscriptTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                template = form.save(commit=False)
                template.created_by = request.user
                
                designer_width = _get_designer_dimension(request.POST.get('designer_page_width_cm'), 29.7)
                designer_height = _get_designer_dimension(request.POST.get('designer_page_height_cm'), 21)
                designer_width_px = _get_designer_dimension(request.POST.get('designer_page_width_px'), 0)
                designer_height_px = _get_designer_dimension(request.POST.get('designer_page_height_px'), 0)
                
                # Get course count
                course_count = int(request.POST.get('active_course_count', 8))
                template.active_course_count = min(max(course_count, 1), MAX_COURSES)
                
                # Build available fields based on course count
                available_fields = get_base_fields()
                available_fields.update(get_course_fields_for_count(template.active_course_count))
                
                # Get active fields from POST data
                active_fields = {}
                for field_name in available_fields.keys():
                    active_fields[field_name] = request.POST.get(f'field_active_{field_name}') == 'on'
                template.active_fields = active_fields
                
                # Get field settings from POST data
                field_settings = {}
                for field_name in available_fields.keys():
                    if active_fields.get(field_name):
                        field_config = TRANSCRIPT_FIELDS.get(field_name, {})
                        field_settings[field_name] = {
                            'x': float(request.POST.get(f'field_x_{field_name}', 15)),
                            'y': float(request.POST.get(f'field_y_{field_name}', 10)),
                            'font_size': float(request.POST.get(f'field_font_size_{field_name}', 12)),
                            'font_name': request.POST.get(f'field_font_{field_name}', 'IBM_Plex_Sans_Arabic_Regular'),
                            'font_color': request.POST.get(f'field_color_{field_name}', '#000000'),
                            'text_direction': field_config.get('direction', 'rtl'),
                            'base_width_cm': designer_width,
                            'base_height_cm': designer_height,
                            'base_width_px': designer_width_px or None,
                            'base_height_px': designer_height_px or None,
                            'text_anchor': 'left',
                            'enabled': True
                        }
                        # Handle pixel-based values
                        for suffix, key in [('x_px', 'x_px'), ('y_px', 'y_px'), 
                                          ('width_px', 'box_width_px'), ('height_px', 'box_height_px'),
                                          ('font_size_px', 'font_size_px')]:
                            val = request.POST.get(f'field_{suffix}_{field_name}')
                            if val not in [None, '']:
                                field_settings[field_name][key] = float(val)
                        for suffix, key in [('x_ratio', 'x_ratio'), ('y_ratio', 'y_ratio'),
                                          ('width_ratio', 'width_ratio'), ('height_ratio', 'height_ratio'),
                                          ('font_size_ratio', 'font_size_ratio')]:
                            val = request.POST.get(f'field_{suffix}_{field_name}')
                            if val not in [None, '']:
                                field_settings[field_name][key] = float(val)
                template.field_settings = field_settings
                
                # Get QR settings
                qr_settings = {
                    'x': float(request.POST.get('qr_x', 6.9)),
                    'y': float(request.POST.get('qr_y', 1.2)),
                    'size': float(request.POST.get('qr_size', 4)),
                    'rotation_angle': float(request.POST.get('qr_rotation', 0)),
                    'base_width_cm': designer_width,
                    'base_height_cm': designer_height,
                    'base_width_px': designer_width_px or None,
                    'base_height_px': designer_height_px or None
                }
                for suffix, key in [('qr_x_px', 'x_px'), ('qr_y_px', 'y_px'), ('qr_size_px', 'size_px')]:
                    val = request.POST.get(suffix)
                    if val not in [None, '']:
                        qr_settings[key] = float(val)
                for suffix, key in [('qr_x_ratio', 'x_ratio'), ('qr_y_ratio', 'y_ratio'), ('qr_size_ratio', 'size_ratio')]:
                    val = request.POST.get(suffix)
                    if val not in [None, '']:
                        qr_settings[key] = float(val)
                template.qr_settings = qr_settings
                
                template.save()
                messages.success(request, 'تم حفظ قالب السجل بنجاح')
                return redirect('transcript_template_list')
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f'حدث خطأ أثناء حفظ القالب: {error_msg}')
                return redirect('transcript_template_create')
        else:
            errors = []
            for field, error_list in form.errors.items():
                errors.append(f"{form.fields.get(field, field).label if field != '__all__' else 'خطأ'}: {', '.join(error_list)}")
            messages.error(request, '\n'.join(errors))
            return redirect('transcript_template_create')
    else:
        form = TranscriptTemplateForm()

    # Pre-filled example data
    example_data = _build_example_data(8)
    
    # Build fields JSON with base fields only initially (course fields added dynamically)
    base_fields = get_base_fields()
    
    context = {
        'form': form,
        'fields': base_fields,
        'fields_json': json.dumps(TRANSCRIPT_FIELDS, ensure_ascii=False),
        'fonts': ADVANCED_FONTS,
        'example_data': json.dumps(example_data, ensure_ascii=False),
        'max_courses': MAX_COURSES,
        'field_categories': TRANSCRIPT_FIELD_CATEGORIES,
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
    return render(request, 'transcript/template_create.html', context)


@login_required(login_url='/login/')
@role_required('can_edit_transcript_templates')
def template_edit(request, template_id):
    """Edit existing transcript template"""
    template = get_object_or_404(TranscriptTemplate, id=template_id)
    
    # Check permissions
    if not (request.user.is_superuser or template.created_by == request.user):
        messages.error(request, 'ليس لديك صلاحية لتعديل هذا القالب')
        return redirect('transcript_template_list')
    
    if request.method == 'POST':
        if not request.FILES.get('pdf_file'):
            request.POST = request.POST.copy()
            request.POST['pdf_file'] = template.pdf_file
        
        form = TranscriptTemplateForm(request.POST, request.FILES, instance=template)
        if form.is_valid():
            try:
                new_template = form.save(commit=False)
                
                designer_width = _get_designer_dimension(request.POST.get('designer_page_width_cm'), 29.7)
                designer_height = _get_designer_dimension(request.POST.get('designer_page_height_cm'), 21)
                designer_width_px = _get_designer_dimension(request.POST.get('designer_page_width_px'), 0)
                designer_height_px = _get_designer_dimension(request.POST.get('designer_page_height_px'), 0)
                
                if not request.FILES.get('pdf_file'):
                    new_template.pdf_file = template.pdf_file
                
                new_template.created_by = request.user
                
                # Get course count
                course_count = int(request.POST.get('active_course_count', template.active_course_count))
                new_template.active_course_count = min(max(course_count, 1), MAX_COURSES)
                
                # Build available fields
                available_fields = get_base_fields()
                available_fields.update(get_course_fields_for_count(new_template.active_course_count))
                
                # Update active fields
                active_fields = {}
                for field_name in available_fields.keys():
                    active_fields[field_name] = request.POST.get(f'field_active_{field_name}') == 'on'
                new_template.active_fields = active_fields
                
                # Update field settings
                field_settings = {}
                for field_name in available_fields.keys():
                    if active_fields.get(field_name):
                        field_config = TRANSCRIPT_FIELDS.get(field_name, {})
                        field_settings[field_name] = {
                            'x': float(request.POST.get(f'field_x_{field_name}', 15)),
                            'y': float(request.POST.get(f'field_y_{field_name}', 10)),
                            'font_size': float(request.POST.get(f'field_font_size_{field_name}', 12)),
                            'font_name': request.POST.get(f'field_font_{field_name}', 'IBM_Plex_Sans_Arabic_Regular'),
                            'font_color': request.POST.get(f'field_color_{field_name}', '#000000'),
                            'text_direction': field_config.get('direction', 'rtl'),
                            'base_width_cm': designer_width,
                            'base_height_cm': designer_height,
                            'base_width_px': designer_width_px or None,
                            'base_height_px': designer_height_px or None,
                            'text_anchor': 'left',
                            'enabled': True
                        }
                        for suffix, key in [('x_px', 'x_px'), ('y_px', 'y_px'),
                                          ('width_px', 'box_width_px'), ('height_px', 'box_height_px'),
                                          ('font_size_px', 'font_size_px')]:
                            val = request.POST.get(f'field_{suffix}_{field_name}')
                            if val not in [None, '']:
                                field_settings[field_name][key] = float(val)
                        for suffix, key in [('x_ratio', 'x_ratio'), ('y_ratio', 'y_ratio'),
                                          ('width_ratio', 'width_ratio'), ('height_ratio', 'height_ratio'),
                                          ('font_size_ratio', 'font_size_ratio')]:
                            val = request.POST.get(f'field_{suffix}_{field_name}')
                            if val not in [None, '']:
                                field_settings[field_name][key] = float(val)
                new_template.field_settings = field_settings
                
                # Update QR settings
                qr_settings = {
                    'x': float(request.POST.get('qr_x', 6.9)),
                    'y': float(request.POST.get('qr_y', 1.2)),
                    'size': float(request.POST.get('qr_size', 4)),
                    'rotation_angle': float(request.POST.get('qr_rotation', 0)),
                    'base_width_cm': designer_width,
                    'base_height_cm': designer_height,
                    'base_width_px': designer_width_px or None,
                    'base_height_px': designer_height_px or None
                }
                for suffix, key in [('qr_x_px', 'x_px'), ('qr_y_px', 'y_px'), ('qr_size_px', 'size_px')]:
                    val = request.POST.get(suffix)
                    if val not in [None, '']:
                        qr_settings[key] = float(val)
                for suffix, key in [('qr_x_ratio', 'x_ratio'), ('qr_y_ratio', 'y_ratio'), ('qr_size_ratio', 'size_ratio')]:
                    val = request.POST.get(suffix)
                    if val not in [None, '']:
                        qr_settings[key] = float(val)
                new_template.qr_settings = qr_settings
                
                new_template.save()
                messages.success(request, 'تم تحديث قالب السجل بنجاح')
                return redirect('transcript_template_list')
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f'حدث خطأ أثناء تحديث القالب: {error_msg}')
        else:
            errors = []
            for field, error_list in form.errors.items():
                errors.append(f"{form.fields.get(field, field).label if field != '__all__' else 'خطأ'}: {', '.join(error_list)}")
            messages.error(request, '\n'.join(errors))
    else:
        initial_data = {
            'name': template.get_display_name(),
            'transcript_type': template.transcript_type,
            'active_course_count': template.active_course_count
        }
        form = TranscriptTemplateForm(instance=template, initial=initial_data)

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

    example_data = _build_example_data(template.active_course_count)
    base_fields = get_base_fields()
    
    context = {
        'form': form,
        'template': template,
        'fields': base_fields,
        'fields_json': json.dumps(TRANSCRIPT_FIELDS, ensure_ascii=False),
        'fonts': ADVANCED_FONTS,
        'example_data': json.dumps(example_data, ensure_ascii=False),
        'max_courses': MAX_COURSES,
        'field_categories': TRANSCRIPT_FIELD_CATEGORIES,
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
    return render(request, 'transcript/template_create.html', context)


@login_required(login_url='/login/')
@role_required('can_delete_transcript_templates')
def template_delete(request, template_id):
    """Delete transcript template"""
    if request.method == 'POST':
        template = get_object_or_404(TranscriptTemplate, id=template_id)
        
        if not (request.user.is_superuser or template.created_by == request.user):
            messages.error(request, 'ليس لديك صلاحية لحذف هذا القالب')
            return redirect('transcript_template_list')
        
        try:
            template_name = template.get_display_name()
            with transaction.atomic():
                related_count = template.transcripts.count()
                if related_count:
                    template.transcripts.all().delete()
                template.delete()
            if related_count:
                messages.success(
                    request,
                    f'تم حذف القالب "{template_name}" وكل السجلات المرتبطة به (عددها {related_count}) بنجاح'
                )
            else:
                messages.success(request, f'تم حذف القالب "{template_name}" بنجاح')
        except Exception as e:
            error_msg = sanitize_error_message(str(e))
            messages.error(request, f'حدث خطأ أثناء حذف القالب: {error_msg}')
    
    return redirect('transcript_template_list')


@login_required(login_url='/login/')
@xframe_options_exempt
def template_preview(request):
    """Generate preview of transcript with current settings"""
    preview_dir = os.path.join(settings.MEDIA_ROOT, 'preview')
    # Use unique filename per user to avoid race conditions
    user_id = request.user.id if request.user.is_authenticated else 'anonymous'
    temp_pdf_path = os.path.join(preview_dir, f'temp_transcript_template_{user_id}.pdf')

    if request.method == 'POST':
        try:
            os.makedirs(preview_dir, exist_ok=True)
            
            # Clean up old temp files first
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except:
                    pass

            pdf_file = request.FILES.get('pdf_file')
            pdf_url = request.POST.get('pdf_url')
            template_id = request.POST.get('template_id')

            if not pdf_file and not pdf_url:
                return JsonResponse({'error': 'لم يتم توفير ملف PDF'}, status=400)

            if pdf_file:
                # Write uploaded file in binary mode
                with open(temp_pdf_path, 'wb') as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)
            elif pdf_url and template_id:
                try:
                    template = TranscriptTemplate.objects.get(id=template_id)
                    if not os.path.exists(template.pdf_file.path):
                        return JsonResponse({'error': 'ملف القالب الأصلي غير موجود'}, status=404)
                    shutil.copy2(template.pdf_file.path, temp_pdf_path)
                except TranscriptTemplate.DoesNotExist:
                    return JsonResponse({'error': 'القالب غير موجود'}, status=404)

            if not os.path.exists(temp_pdf_path):
                return JsonResponse({'error': 'فشل في حفظ ملف PDF'}, status=400)
            
            # Check file size to ensure it's not empty
            if os.path.getsize(temp_pdf_path) < 100:
                return JsonResponse({'error': 'ملف PDF فارغ أو تالف'}, status=400)

            settings_str = request.POST.get('settings', '{}')
            template_settings = json.loads(settings_str)
            
            example_data = {}
            active_fields = template_settings.get('active_fields', {})
            for field_name, is_active in active_fields.items():
                if is_active:
                    example_value = request.POST.get(f'example_{field_name}', '')
                    if example_value:
                        example_data[field_name] = example_value

            preview_path = os.path.join(preview_dir, f'preview_transcript_{user_id}.pdf')
            
            class MockTemplate:
                class MockPdfFile:
                    def __init__(self, file_path):
                        self.path = file_path
                
                def __init__(self, settings_data, pdf_path):
                    self.pdf_file = self.MockPdfFile(pdf_path)
                    self.active_fields = settings_data.get('active_fields', {})
                    self.field_settings = settings_data.get('field_settings', {})
                    self.qr_settings = settings_data.get('qr_settings', {})
                    self.active_course_count = settings_data.get('active_course_count', 8)
                    # Store PDF dimensions from JavaScript (exact match)
                    pdf_dims = settings_data.get('pdf_dimensions', {})
                    self.pdf_width_cm = pdf_dims.get('width_cm')
                    self.pdf_height_cm = pdf_dims.get('height_cm')
                    # Store viewport dimensions for ratio conversion
                    self.pdf_width_px = pdf_dims.get('width_px')
                    self.pdf_height_px = pdf_dims.get('height_px')
            
            mock_template = MockTemplate(template_settings, temp_pdf_path)
            
            generate_transcript(
                transcript_data=example_data,
                hash_value='preview',
                template=mock_template,
                output_file=preview_path
            )

            preview_url = f'/transcript/templates/preview_pdf/?t={int(time.time())}&u={user_id}'
            return JsonResponse({'preview_url': preview_url})
        except Exception as e:
            error_msg = str(e)
            # Check for PDF format/compression errors
            if 'decompressing' in error_msg or 'invalid literal' in error_msg or 'قراءة ملف PDF' in error_msg:
                return JsonResponse({
                    'error': 'صيغة ملف PDF غير مدعومة. يرجى تصدير الملف بصيغة PDF 1.4 أو أقدم من برنامج التصميم.'
                }, status=400)
            return JsonResponse({'error': error_msg}, status=400)
    return JsonResponse({'error': 'طلب غير صالح'}, status=400)


@login_required(login_url='/login/')
@xframe_options_exempt
def preview_pdf(request):
    """Serve the preview PDF file"""
    user_id = request.GET.get('u', request.user.id if request.user.is_authenticated else 'anonymous')
    preview_path = os.path.join(settings.MEDIA_ROOT, 'preview', f'preview_transcript_{user_id}.pdf')
    if os.path.exists(preview_path):
        response = FileResponse(open(preview_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="preview.pdf"'
        return response
    return JsonResponse({'error': 'المعاينة غير موجودة'}, status=404)


def _build_example_data(course_count):
    """Build example data for transcript preview"""
    example_data = {
        'arabic_name': 'محمد أسامه محمد مهنا',
        'english_name': 'Mohamed Osama Mohamed Mohana',
        'national_id_ar': '١٢٣٤٥٦٧٨٩٠',
        'national_id_en': '1234567890',
        'program_name_ar': 'دبـلــوم الحوكمــــة',
        'program_name_en': 'Diploma in Governance',
        'issue_date_ar': '١٤٤٥/٠٦/١٥',
        'issue_date_en': '2024-01-15',
        'credit_hours_ar': '١٢٠ ساعة',
        'credit_hours_en': '120 Hours',
        'gpa': '4.5',
        'overall_grade_ar': 'ممتاز',
        'overall_grade_en': 'Excellent',
    }
    
    # Add course example data
    course_names_ar = ['مقدمة في البرمجة', 'قواعد البيانات', 'الشبكات', 'أمن المعلومات', 
                       'الذكاء الاصطناعي', 'تحليل البيانات', 'إدارة المشاريع', 'الحوكمة']
    course_names_en = ['Introduction to Programming', 'Databases', 'Networks', 'Information Security',
                       'Artificial Intelligence', 'Data Analysis', 'Project Management', 'Governance']
    grades = ['A+', 'A', 'A-', 'B+', 'B', 'A', 'A+', 'A']
    percentages = ['95%', '92%', '88%', '85%', '90%', '87%', '94%', '91%']
    
    for i in range(1, min(course_count + 1, len(course_names_ar) + 1)):
        idx = (i - 1) % len(course_names_ar)
        example_data[f'course_{i}_name_ar'] = course_names_ar[idx]
        example_data[f'course_{i}_name_en'] = course_names_en[idx]
        example_data[f'course_{i}_percentage'] = percentages[idx]
        example_data[f'course_{i}_grade'] = grades[idx]
        example_data[f'course_{i}_credit_hours'] = '3'
    
    return example_data
