# views.py
from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .views_base import check_permission
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib import messages
from .decorators import role_required
from urllib.parse import urljoin
from hashlib import sha256
import pandas as pd
import time
import os
import re
# import logging
from datetime import datetime

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q


from .forms import CreateCertificateForm, VerifyCertificateForm, CertificateForm
from .blockchain import create_new_block, is_chain_valid
from .models import Block, Certificate
from .certificate_generator import generate_certificate
from .email_service import send_email
from .models_advanced import AdvancedCertificate
from .models_transcript import Transcript
from .constants import ADVANCED_CERTIFICATE_FIELDS

# logger = logging.getLogger(__name__)

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

def welcome(request):
    if request.user.is_authenticated:
        return redirect('index')  # or redirect('/index/')
    return render(request, 'welcome.html')

@login_required(login_url='/login/')
def index(request):
    context = add_username_to_context(request)
    return render(request, 'index.html', context)

@login_required(login_url='/login/')
@role_required('can_create_certificates')
def create_certificate(request):
    # Initialize form with user to filter templates
    form = CertificateForm(user=request.user)
    if request.method == 'POST':
        form = CertificateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                course_name = form.cleaned_data['course_name']
                duration = form.cleaned_data['duration']
                arabic_date_text = duration
                success = False  # Flag to track if any certificate was created successfully

                try:
                    names_column = form.cleaned_data['names_column']
                    emails_column = form.cleaned_data['emails_column']
                    names_file = form.cleaned_data['names_file']
                    if names_file:
                        if str(names_file).lower().endswith(('.xls', '.xlsx')):
                            df = pd.read_excel(names_file)
                        else:
                            raise ValidationError("نوع الملف غير مدعوم. يرجى تحميل ملف Excel.")

                        if names_column not in df.columns:
                            raise ValidationError(f"العمود '{names_column}' غير موجود في الملف المقدم.")
                        if emails_column not in df.columns:
                            raise ValidationError(f"العمود '{emails_column}' غير موجود في الملف المقدم.")

                        names = df[names_column].tolist()
                        emails = df[emails_column].tolist()
                    else:
                        names = [form.cleaned_data['name']]
                        emails = [form.cleaned_data['email']]

                    output_files = []  # Store output file paths
                    template_obj = form.cleaned_data['template']


                    for name, email in zip(names, emails):
                        try:
                            current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                            hash_input = name + course_name + duration + email + current_timestamp
                            hash_value = sha256(hash_input.encode('utf-8')).hexdigest()

                            # Create output directory if it doesn't exist
                            output_dir = os.path.join(settings.MEDIA_ROOT)
                            os.makedirs(output_dir, exist_ok=True)
                            
                            # Full path for the output file
                            output_file = os.path.join(output_dir, f'{hash_value}.pdf')
                            
                            try:
                                # Get template display name
                                template_name = template_obj.get_display_name()
                                
                                # Generate the certificate
                                generate_certificate(name, course_name, arabic_date_text, hash_value, template_name, output_file)
                                
                                # Verify the file was created
                                if not os.path.exists(output_file):
                                    raise Exception('فشل في إنشاء ملف الشهادة')
                                    
                            except Exception as e:
                                # logger.error(f"Error generating certificate for {name}: {str(e)}")
                                error_msg = sanitize_error_message(str(e))
                                messages.error(request, f"حدث خطأ أثناء إنشاء شهادة {name}: {error_msg}")
                                continue
                                
                            output_files.append(output_file)

                            # Create certificate record
                            Certificate.objects.create(
                                name=name,
                                email=email,
                                course_name=course_name,
                                duration=duration,
                                hash_value=hash_value,
                                certificate_hash=hash_value,
                                created_by=request.user
                            )

                            # Send email
                            # Clean and send email
                            # subject = "شهادة حضور دورة " + course_name
                            # email_body = "سعدنا بحضوركم .. ونتطلع لرؤيتكم في دورات قادمة"
                            # clean_email = ''.join(str(email).split()) if email else None
                            
                            # if clean_email:
                            #     if send_email(clean_email, subject, email_body, output_file):
                            #         request.session.setdefault('success_list', []).append({
                            #             'name': name,
                            #             'email': clean_email
                            #         })
                            #     else:
                            #         request.session.setdefault('error_list', []).append({
                            #             'name': name,
                            #             'email': clean_email,
                            #             'reason': 'فشل إرسال البريد الإلكتروني'
                            #         })
                            # else:
                            #     request.session.setdefault('error_list', []).append({
                            #         'name': name,
                            #         'email': email,
                            #         'reason': 'البريد الإلكتروني غير صالح'
                            #     })

                            # Generate certificate download link
                            certificate_link = request.build_absolute_uri(reverse('download_certificate', args=[hash_value]))

                            # Keep clean_email handling as it is
                            clean_email = ''.join(str(email).split()) if email else None

                            # Send email with HTML template
                            if clean_email:
                                email_sent = send_email(
                                    to=clean_email,
                                    subject=f"شهادة حضور - {course_name}",
                                    attachment_path=output_file,
                                    course_name=course_name,
                                    certificate_link=certificate_link,
                                    name=name,
                                    certificate_hash=hash_value,
                                )

                                if email_sent:
                                    request.session.setdefault('success_list', []).append({
                                        'name': name,
                                        'email': clean_email
                                    })
                                else:
                                    request.session.setdefault('error_list', []).append({
                                        'name': name,
                                        'email': clean_email,
                                        'reason': 'فشل إرسال البريد الإلكتروني'
                                    })
                            else:
                                request.session.setdefault('error_list', []).append({
                                    'name': name,
                                    'email': email,  # Keeping the original email variable here
                                    'reason': 'البريد الإلكتروني غير صالح'
                                })

                            success = True  # At least one certificate was created successfully

                        except Exception as e:
                            # logger.error(f"Error generating certificate for {name}: {str(e)}")
                            error_msg = sanitize_error_message(str(e))
                            messages.error(request, f"حدث خطأ أثناء إنشاء شهادة {name}: {error_msg}")

                    if success:
                        messages.success(request, "تم إنشاء الشهادات بنجاح")
                        return redirect('success_redirect')
                    else:
                        messages.error(request, "فشل إنشاء جميع الشهادات")
                        return redirect('create_certificate')

                except ValidationError as e:
                    error_msg = sanitize_error_message(str(e))
                    messages.error(request, error_msg)
                    return redirect('create_certificate')

            except Exception as e:
                # logger.error(f"Error in create_certificate: {str(e)}")
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f"حدث خطأ أثناء إنشاء الشهادة: {error_msg}")
                return redirect('create_certificate')

    context = {'form': form}
    context.update(add_username_to_context(request))
    context.update({"messages": messages.get_messages(request)})
    return render(request, 'create_certificate.html', context)

# @login_required(login_url='/login/')
# @role_required('can_view_certificates')
# def manage_certificates(request):
#     # Super admin can see all certificates
#     if request.user.is_superuser and request.user.profile.role.name_en == 'super_admin':
#         certificates = Certificate.objects.all()
#     else:
#         # Others can only see their own certificates
#         certificates = Certificate.objects.filter(created_by=request.user)
    
#     certificates = certificates.order_by('-id')
#     context = {'certificates': certificates}
#     context.update(add_username_to_context(request))
#     return render(request, 'manage_certificates.html', context)


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
@role_required('can_view_certificates')
def manage_certificates(request):
    query = request.GET.get('q', '')
    # Super admin can see all certificates
    if _is_super_admin(request.user):
        certificates = Certificate.objects.all()
    else:
        # Others can only see their own certificates
        certificates = Certificate.objects.filter(created_by=request.user)

    if query:
        certificates = certificates.filter(
            Q(name__icontains=query) |
            Q(course_name__icontains=query) |
            Q(certificate_hash__icontains=query)
        )

    # Order certificates by id in descending order
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

    context = {'certificates': certificates, 'request': request}
    context.update(add_username_to_context(request))
    return render(request, 'manage_certificates.html', context)


@login_required(login_url='/login/')
def download_certificate(request, certificate_hash):
    try:
        # Get the certificate object
        certificate = get_object_or_404(Certificate, certificate_hash=certificate_hash)
        
        # Construct the file path
        file_name = f'{certificate_hash}.pdf'
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        
        # Check if file exists
        if not os.path.exists(file_path):
            # logger.error(f"Certificate file not found: {file_path}")
            messages.error(request, 'ملف الشهادة غير موجود')
            return redirect('manage_certificates')
            
        # Open and return the file
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{file_name}"'
        return response
            
    except Exception as e:
        # logger.error(f"Error downloading certificate: {str(e)}")
        error_msg = sanitize_error_message(str(e))
        messages.error(request, f'حدث خطأ أثناء تحميل الشهادة: {error_msg}')
        return redirect('manage_certificates')

@login_required(login_url='/login/')
@role_required('can_verify_certificates')
def verify_certificate(request):
    if request.method == 'POST':
        form = VerifyCertificateForm(request.POST)
        if form.is_valid():
            certificate_hash = form.cleaned_data['certificate_hash']
            certificate = Certificate.objects.filter(certificate_hash=certificate_hash).first()
            is_advanced_certificate = False
            is_transcript = False
            advanced_context = {}
            transcript_context = {}
            
            if certificate:
                certificate_found = True
            else:
                # Try advanced certificate
                advanced_cert = AdvancedCertificate.objects.filter(certificate_hash=certificate_hash).select_related('template').first()
                if advanced_cert:
                    certificate = advanced_cert
                    certificate_found = True
                    is_advanced_certificate = True
                    advanced_context = _build_advanced_display_context(advanced_cert)
                    advanced_context['advanced_download_url'] = reverse('advanced_download_certificate', args=[advanced_cert.certificate_hash])
                else:
                    # Try transcript
                    transcript = Transcript.objects.filter(certificate_hash=certificate_hash).select_related('template').first()
                    if transcript:
                        certificate_found = True
                        is_transcript = True
                        transcript_context = _build_transcript_display_context(transcript)
                        transcript_context['transcript'] = transcript
                        transcript_context['transcript_download_url'] = reverse('transcript_download', args=[transcript.certificate_hash])
                    else:
                        certificate_found = False
            
            context = {
                'form': form,
                'certificate_found': certificate_found,
                'certificate': certificate,
                'is_advanced_certificate': is_advanced_certificate,
                'is_transcript': is_transcript
            }
            context.update(advanced_context)
            context.update(transcript_context)
            context.update(add_username_to_context(request))
            return render(request, 'verify_certificate.html', context)
    else:
        form = VerifyCertificateForm()

    context = {'form': form}
    context.update(add_username_to_context(request))
    return render(request, 'verify_certificate.html', context)

def validate(request):
    hash_value = request.GET.get('hash', None)
    certificate_type = 'regular'
    certificate = None
    transcript = None
    
    # Try regular certificate first
    try:
        certificate = Certificate.objects.get(certificate_hash=hash_value)
        certificate_type = 'regular'
    except Certificate.DoesNotExist:
        # Try advanced certificate
        try:
            certificate = AdvancedCertificate.objects.select_related('template').get(certificate_hash=hash_value)
            certificate_type = 'advanced'
        except AdvancedCertificate.DoesNotExist:
            # Try transcript
            try:
                transcript = Transcript.objects.select_related('template').get(certificate_hash=hash_value)
                certificate_type = 'transcript'
            except Transcript.DoesNotExist:
                certificate = None
    
    # Render appropriate template based on certificate/transcript type
    if certificate_type == 'transcript' and transcript:
        transcript_context = _build_transcript_display_context(transcript)
        context = {
            'transcript': transcript,
            'transcript_data': transcript.transcript_data,
            'template': transcript.template,
            'certificate_type': 'transcript',
            **transcript_context
        }
        return render(request, 'validate_transcript.html', context)
    elif certificate_type == 'advanced' and certificate:
        advanced_context = _build_advanced_display_context(certificate)
        context = {
            'certificate': certificate,
            'certificate_data': certificate.certificate_data,
            'template': certificate.template,
            'certificate_type': 'advanced',
            **advanced_context
        }
        return render(request, 'validate_advanced.html', context)
    else:
        context = {'certificate': certificate}
        return render(request, 'validate.html', context)

@login_required(login_url='/login/')
def success_redirect(request):
    context = add_username_to_context(request)
    
    # Get success and error lists from session
    context['success_list'] = request.session.pop('success_list', [])
    context['error_list'] = request.session.pop('error_list', [])
    
    # Add summary messages
    if context['success_list']:
        messages.success(request, f"تم إنشاء وإرسال {len(context['success_list'])} شهادة بنجاح")
    if context['error_list']:
        messages.warning(request, f"فشل إرسال {len(context['error_list'])} شهادة")
    
    return render(request, 'success_redirect.html', context)


@login_required(login_url='/login/')
def home(request):
    context = add_username_to_context(request)
    return render(request, 'new_template/home.html', context)

def custom_404(request, exception):
    return render(request, '404.html', status=404)

def add_username_to_context(request):
    username = request.user.username
    full_name = f"{request.user.first_name} {request.user.last_name}"
    return {'username': username, 'full_name': full_name}


ADVANCED_PRIMARY_NAME_KEYS = [
    'arabic_name',
    'english_name',
    'full_name',
    'name'
]

ADVANCED_PRIMARY_COURSE_KEYS = [
    'program_name_ar',
    'program_name_en',
    'course_name',
    'course_title'
]

ADVANCED_PRIMARY_DURATION_KEYS = [
    'duration_ar',
    'duration_en',
    'duration'
]

ADVANCED_EXTRA_FIELD_ORDER = [
    'english_name',
    'program_name_en',
    'program_name_ar',
    'arabic_name',
    'courses_count_en',
    'courses_count_ar',
    'duration_en',
    'duration_ar',
    'grade_en',
    'grade_ar',
    'gpa_en',
    'gpa_ar',
    'course_name',
    'duration',
    'issue_date'
]

ADVANCED_HIDDEN_EXTRA_FIELDS = {
    'national_id_ar',
    'national_id_en'
}


def _build_advanced_display_context(certificate):
    """Return primary display values and extra fields for advanced certificates."""
    certificate_data = certificate.certificate_data or {}
    used_keys = set()

    def pick_value(key_order):
        for key in key_order:
            value = certificate_data.get(key)
            if value:
                used_keys.add(key)
                return value
        return None

    primary_name = pick_value(ADVANCED_PRIMARY_NAME_KEYS)
    primary_course = pick_value(ADVANCED_PRIMARY_COURSE_KEYS)
    primary_duration = pick_value(ADVANCED_PRIMARY_DURATION_KEYS)

    template_display_name = certificate.template.get_display_name() if getattr(certificate, 'template', None) else ''
    if not primary_course:
        primary_course = template_display_name

    extra_fields = []
    for key, value in certificate_data.items():
        if (
            not value
            or key in used_keys
            or key in ADVANCED_HIDDEN_EXTRA_FIELDS
        ):
            continue
        label = ADVANCED_CERTIFICATE_FIELDS.get(key, {}).get('label_ar', key.replace('_', ' '))
        extra_fields.append({
            'key': key,
            'label': label,
            'value': value
        })

    def extra_sort_key(field):
        try:
            priority = ADVANCED_EXTRA_FIELD_ORDER.index(field['key'])
        except ValueError:
            priority = len(ADVANCED_EXTRA_FIELD_ORDER)
        return (priority, field['label'])

    extra_fields.sort(key=extra_sort_key)

    return {
        'primary_name': primary_name,
        'primary_course': primary_course,
        'primary_duration': primary_duration,
        'template_display_name': template_display_name,
        'certificate_type_label': _get_certificate_type_label(
            getattr(certificate.template, 'certificate_type', None)
        ),
        'advanced_extra_fields': extra_fields
    }


def _get_certificate_type_label(certificate_type):
    mapping = {
        'arabic': 'شهادة عربية',
        'english': 'شهادة إنجليزية',
        'bilingual': 'شهادة ثنائية اللغة'
    }
    return mapping.get(certificate_type, 'شهادة متقدمة')


# Transcript display context keys
TRANSCRIPT_PRIMARY_NAME_KEYS = ['arabic_name', 'english_name']
TRANSCRIPT_HIDDEN_EXTRA_FIELDS = [
    'program_name_ar', 'program_name_en',
    'national_id_ar', 'national_id_en'  # Hide ID numbers for security
]

TRANSCRIPT_EXTRA_FIELD_ORDER = [
    'english_name',
    'arabic_name',
    'issue_date_en',
    'issue_date_ar',
    'credit_hours_en',
    'credit_hours_ar',
    'overall_grade_en',
    'overall_grade_ar',
    'gpa',
]


def _build_transcript_display_context(transcript):
    """Return primary display values and extra fields for transcripts."""
    transcript_data = transcript.transcript_data or {}
    used_keys = set()
    
    def pick_value(key_order):
        for key in key_order:
            value = transcript_data.get(key)
            if value:
                used_keys.add(key)
                return value
        return None
    
    # Get primary name (for main display)
    primary_name = pick_value(TRANSCRIPT_PRIMARY_NAME_KEYS)
    
    # Extract extra fields (non-course fields)
    extra_fields = []
    from .constants_transcript import TRANSCRIPT_FIELDS
    for key, value in transcript_data.items():
        if (
            not value
            or key in TRANSCRIPT_HIDDEN_EXTRA_FIELDS
            or key.startswith('course_')
        ):
            continue
        label = TRANSCRIPT_FIELDS.get(key, {}).get('label_ar', key.replace('_', ' '))
        extra_fields.append({
            'key': key,
            'label': label,
            'value': value
        })
    
    # Sort extra fields by order preference
    def extra_sort_key(field):
        try:
            priority = TRANSCRIPT_EXTRA_FIELD_ORDER.index(field['key'])
        except ValueError:
            priority = len(TRANSCRIPT_EXTRA_FIELD_ORDER)
        return (priority, field['label'])
    
    extra_fields.sort(key=extra_sort_key)
    
    # Extract course grades
    course_grades = []
    course_count = getattr(transcript.template, 'active_course_count', 30) if transcript.template else 30
    for i in range(1, course_count + 1):
        course_name = (
            transcript_data.get(f'course_{i}_name_ar') or
            transcript_data.get(f'course_{i}_name_en') or
            ''
        )
        percentage = transcript_data.get(f'course_{i}_percentage', '')
        grade = transcript_data.get(f'course_{i}_grade', '')
        credit_hours = transcript_data.get(f'course_{i}_credit_hours', '')
        
        # Include course if it has any data (name, percentage, or grade)
        if course_name or percentage or grade:
            course_grades.append({
                'number': i,
                'name': course_name if course_name else f'المقرر {i}',
                'percentage': percentage,
                'grade': grade,
                'credit_hours': credit_hours
            })
    
    return {
        'primary_name': primary_name,
        'transcript_extra_fields': extra_fields,
        'course_grades': course_grades
    }