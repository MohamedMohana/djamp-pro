"""
Views for Advanced Certificate Creation and Management (KKUx)
Supports dynamic fields, bulk generation, and email sending
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.urls import reverse
from .decorators import role_required
from .models_advanced import AdvancedCertificate, AdvancedCertificateTemplate
from .forms_advanced import AdvancedCertificateForm
from .advanced_generator import generate_advanced_certificate
from .email_service import send_email
from .constants import ADVANCED_CERTIFICATE_FIELDS
from hashlib import sha256
from datetime import datetime
import re
import pandas as pd
import os
import json


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
    return sanitized if sanitized else "حدث خطأ أثناء إنشاء الشهادة"


def _build_template_field_map(templates):
    """Return serializable map of template ids to active field metadata"""
    template_map = {}
    for template in templates:
        active_config = {}
        template_fields = template.active_fields or {}
        # Preserve the same field ordering used in the template wizard UI
        for field_name in ADVANCED_CERTIFICATE_FIELDS.keys():
            if not template_fields.get(field_name):
                continue
            field_config = ADVANCED_CERTIFICATE_FIELDS.get(field_name, {})
            active_config[field_name] = {
                'label': field_config.get('label_ar', field_name),
                'placeholder': field_config.get('placeholder_ar', ''),
                'direction': field_config.get('direction', 'rtl')
            }
        # Append any legacy/custom fields that are not part of the predefined set
        for field_name, is_active in template_fields.items():
            if field_name in ADVANCED_CERTIFICATE_FIELDS or not is_active:
                continue
            field_config = ADVANCED_CERTIFICATE_FIELDS.get(field_name, {})
            active_config[field_name] = {
                'label': field_config.get('label_ar', field_name),
                'placeholder': field_config.get('placeholder_ar', ''),
                'direction': field_config.get('direction', 'rtl')
            }
        template_map[str(template.id)] = {
            'name': template.get_display_name(),
            'fields': active_config
        }
    return template_map


@login_required(login_url='/login/')
@role_required('can_create_advanced_certificates')
def create_certificate(request):
    """Create advanced certificates - individual or bulk via Excel"""
    form = AdvancedCertificateForm(user=request.user)
    previous_post_data = {}
    input_method = 'individual'
    
    if request.method == 'POST':
        template_id = request.POST.get('template')
        form = AdvancedCertificateForm(request.POST, request.FILES, user=request.user, template_id=template_id)
        previous_post_data = request.POST.dict()
        input_method = previous_post_data.get('input_method', 'individual')
        
        if form.is_valid():
            try:
                template = form.cleaned_data['template']
                excel_file = form.cleaned_data.get('excel_file')
                email_column = form.cleaned_data.get('email_column', '')
                individual_email = form.cleaned_data.get('individual_email', '')
                course_name = form.cleaned_data.get('course_name', '').strip()
                duration = form.cleaned_data.get('duration', '').strip()
                
                success = False
                
                # Determine if we're processing Excel or individual certificate
                if excel_file:
                    # Bulk processing from Excel
                    try:
                        if str(excel_file).lower().endswith(('.xls', '.xlsx')):
                            df = pd.read_excel(excel_file)
                        else:
                            raise ValueError("نوع الملف غير مدعوم")
                        
                        # Remove duplicate rows to avoid generating/sending twice
                        # Prefer email for de-duplication; fall back to names only if no email column is provided
                        dedup_columns = []
                        if email_column and email_column in df.columns:
                            dedup_columns = [email_column]
                        else:
                            for name_field in ['arabic_name', 'english_name']:
                                column_name = form.cleaned_data.get(f'column_{name_field}', '')
                                if column_name and column_name in df.columns:
                                    dedup_columns.append(column_name)

                        if dedup_columns:
                            original_count = len(df)
                            df = df.drop_duplicates(subset=dedup_columns, keep='first')
                            removed = original_count - len(df)
                            if removed > 0:
                                messages.warning(
                                    request,
                                    f"تم تجاهل {removed} صف مكرر في ملف Excel لتجنب إنشاء شهادات مكررة"
                                )
                        
                        # Build list of certificate data from Excel
                        certificates_data = []
                        for index, row in df.iterrows():
                            cert_data = {}
                            email = None
                            
                            # Extract data for each active field
                            for field_name, is_active in template.active_fields.items():
                                if not is_active:
                                    continue
                                
                                column_name = form.cleaned_data.get(f'column_{field_name}', '')
                                if column_name and column_name in df.columns:
                                    value = row[column_name]
                                    if pd.notna(value):
                                        # Round GPA values to 2 decimal places to match Excel display
                                        if field_name in ['gpa_en', 'gpa_ar']:
                                            try:
                                                # Try to convert to float and round
                                                numeric_value = float(value)
                                                value = round(numeric_value, 2)
                                            except (ValueError, TypeError):
                                                # If conversion fails, use original value
                                                pass
                                        cert_data[field_name] = str(value).strip()
                            
                            cert_data['course_name'] = course_name
                            cert_data['duration'] = duration
                            
                            # Get email if column is specified
                            if email_column and email_column in df.columns:
                                email_value = row[email_column]
                                if pd.notna(email_value):
                                    email = ''.join(str(email_value).split())  # Remove spaces
                            
                            certificates_data.append((cert_data, email))
                        
                        # Generate certificates
                        for cert_data, email in certificates_data:
                            try:
                                success = _generate_and_save_certificate(
                                    request, template, cert_data, email
                                )
                            except Exception as e:
                                name = cert_data.get('arabic_name') or cert_data.get('english_name') or 'غير محدد'
                                error_msg = sanitize_error_message(str(e))
                                messages.error(request, f"خطأ في إنشاء شهادة {name}: {error_msg}")
                        
                        if success:
                            messages.success(request, f"تم إنشاء {len(certificates_data)} شهادة بنجاح")
                            return redirect('advanced_success_redirect')
                    
                    except Exception as e:
                        error_msg = sanitize_error_message(str(e))
                        messages.error(request, f"خطأ في معالجة ملف Excel: {error_msg}")
                        return redirect('advanced_create_certificate')
                
                else:
                    # Individual certificate
                    cert_data = {}
                    for field_name, is_active in template.active_fields.items():
                        if not is_active:
                            continue
                        
                        value = form.cleaned_data.get(f'single_{field_name}', '')
                        if value:
                            cert_data[field_name] = value.strip()
                    
                    # Check if we have any data
                    if not cert_data:
                        messages.error(request, 'يرجى إدخال بيانات الشهادة')
                        return redirect('advanced_create_certificate')
                    
                    cert_data['course_name'] = course_name
                    cert_data['duration'] = duration
                    
                    # Email for individual certificate
                    email = individual_email.strip() if individual_email else None
                    
                    success = _generate_and_save_certificate(request, template, cert_data, email)
                    
                    if success:
                        messages.success(request, "تم إنشاء الشهادة بنجاح")
                        return redirect('advanced_success_redirect')
                    else:
                        messages.error(request, "فشل إنشاء الشهادة")
                        return redirect('advanced_create_certificate')
            
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f"حدث خطأ: {error_msg}")
                return redirect('advanced_create_certificate')
    
    template_queryset = form.fields['template'].queryset
    template_fields_map = _build_template_field_map(template_queryset)
    
    context = {
        'form': form,
        'template_fields_json': json.dumps(template_fields_map, ensure_ascii=False),
        'previous_form_json': json.dumps(previous_post_data, ensure_ascii=False),
        'initial_input_method': input_method or 'individual',
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    context.update({"messages": messages.get_messages(request)})
    return render(request, 'advanced/create_certificate.html', context)


def _generate_and_save_certificate(request, template, cert_data, email=None):
    """Helper function to generate and save a single certificate"""
    try:
        # Generate unique hash
        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        hash_input = json.dumps(cert_data, sort_keys=True) + current_timestamp
        if email:
            hash_input += email
        hash_value = sha256(hash_input.encode('utf-8')).hexdigest()
        
        # Create output directory if it doesn't exist
        output_dir = os.path.join(settings.MEDIA_ROOT)
        os.makedirs(output_dir, exist_ok=True)
        
        # Full path for the output file
        output_file = os.path.join(output_dir, f'{hash_value}.pdf')
        
        # Generate the certificate
        generate_advanced_certificate(
            certificate_data=cert_data,
            hash_value=hash_value,
            template=template,
            output_file=output_file
        )
        
        # Verify the file was created
        if not os.path.exists(output_file):
            raise Exception('فشل في إنشاء ملف الشهادة')
        
        # Create certificate record
        AdvancedCertificate.objects.create(
            template=template,
            hash_value=hash_value,
            certificate_hash=hash_value,
            certificate_data=cert_data,
            email=email,
            created_by=request.user
        )
        
        # Send email if provided
        if email:
            name = cert_data.get('arabic_name') or cert_data.get('english_name') or 'المستلم'
            program = (
                cert_data.get('course_name') or
                cert_data.get('program_name_ar') or
                cert_data.get('program_name_en') or
                'البرنامج'
            )
            certificate_link = request.build_absolute_uri(reverse('advanced_download_certificate', args=[hash_value]))
            
            email_sent = send_email(
                to=email,
                subject=f"شهادة حضور - {program}",
                attachment_path=output_file,
                course_name=program,
                certificate_link=certificate_link,
                name=name,
                certificate_hash=hash_value,
            )
            
            if email_sent:
                request.session.setdefault('success_list', []).append({
                    'name': name,
                    'email': email
                })
            else:
                request.session.setdefault('error_list', []).append({
                    'name': name,
                    'email': email,
                    'reason': 'فشل إرسال البريد الإلكتروني'
                })
        
        return True
    
    except Exception as e:
        raise Exception(f"خطأ في إنشاء الشهادة: {str(e)}")


def _is_super_admin(user):
    """Check if user is a super admin with proper error handling"""
    # Check Django's is_superuser flag first
    if user.is_superuser:
        return True
    
    # Also check if user has super_admin role in profile
    try:
        if hasattr(user, 'profile') and user.profile:
            return user.profile.is_super_admin()
    except AttributeError:
        pass
    
    return False


@login_required(login_url='/login/')
@role_required('can_view_advanced_certificates')
def manage_certificates(request):
    """List and manage advanced certificates"""
    query = request.GET.get('q', '')
    
    # Super admin can see all certificates
    if _is_super_admin(request.user):
        certificates = AdvancedCertificate.objects.all()
    else:
        # Others can only see their own certificates
        certificates = AdvancedCertificate.objects.filter(created_by=request.user)
    
    # Search functionality
    if query:
        certificates = certificates.filter(
            Q(certificate_data__icontains=query) |
            Q(certificate_hash__icontains=query) |
            Q(email__icontains=query)
        )
    
    # Order certificates by id (newest first) - using id instead of date
    # because date is DateField without time component
    certificates = certificates.order_by('-id')
    
    # Pagination: 20 certificates per page
    page = request.GET.get('page', 1)
    paginator = Paginator(certificates, 20)
    try:
        certificates = paginator.page(page)
    except PageNotAnInteger:
        certificates = paginator.page(1)
    except EmptyPage:
        certificates = paginator.page(paginator.num_pages)
    
    context = {
        'certificates': certificates,
        'request': request,
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    return render(request, 'advanced/manage_certificates.html', context)


@login_required(login_url='/login/')
def download_certificate(request, certificate_hash):
    """Download advanced certificate PDF"""
    try:
        # Get the certificate object
        certificate = get_object_or_404(AdvancedCertificate, certificate_hash=certificate_hash)
        
        # Construct the file path
        file_name = f'{certificate_hash}.pdf'
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        
        # Check if file exists
        if not os.path.exists(file_path):
            messages.error(request, 'ملف الشهادة غير موجود')
            return redirect('advanced_manage_certificates')
        
        # Open and return the file
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{file_name}"'
        return response
    
    except Exception as e:
        error_msg = sanitize_error_message(str(e))
        messages.error(request, f'حدث خطأ أثناء تحميل الشهادة: {error_msg}')
        return redirect('advanced_manage_certificates')


@login_required(login_url='/login/')
def success_redirect(request):
    """Success page after creating certificates"""
    context = {
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    
    # Get success and error lists from session
    context['success_list'] = request.session.pop('success_list', [])
    context['error_list'] = request.session.pop('error_list', [])
    
    # Add summary messages
    if context['success_list']:
        messages.success(request, f"تم إنشاء وإرسال {len(context['success_list'])} شهادة بنجاح")
    if context['error_list']:
        messages.warning(request, f"فشل إرسال {len(context['error_list'])} شهادة")
    
    return render(request, 'advanced/success_redirect.html', context)

