"""
Views for Transcript Creation and Management (سجل المقررات)
Supports dynamic course fields, bulk generation, and email sending
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
from .models_transcript import Transcript, TranscriptTemplate
from .forms_transcript import TranscriptForm, build_template_field_map
from .transcript_generator import generate_transcript
from .email_service import send_email
from .constants_transcript import TRANSCRIPT_FIELDS
from hashlib import sha256
from datetime import datetime
import re
import pandas as pd
import os
import json


def sanitize_error_message(error_message):
    """Remove sensitive file paths from error messages for security."""
    sanitized = re.sub(r'/[\w/.-]+', '', str(error_message))
    sanitized = re.sub(r'[A-Za-z]:\\[\w\\.-]+', '', sanitized)
    sanitized = re.sub(r'\s+at:\s*', '', sanitized)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized if sanitized else "حدث خطأ أثناء إنشاء السجل"


def _normalize_percentage_from_excel(value):
    """
    Convert Excel percentage value to display string (e.g. '100%', '200%').
    Excel stores percentages as a ratio: 100% -> 1, 200% -> 2, 90% -> 0.9.
    So we always treat the number as ratio and display as (num * 100)%.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    s = str(value).strip()
    if '%' in s:
        return s
    try:
        num = float(value)
        return f"{int(round(num * 100))}%"
    except (ValueError, TypeError):
        return s


# Excel date columns that should be stored as date-only (no time)
TRANSCRIPT_DATE_FIELDS = {'issue_date_ar', 'issue_date_en'}


def _normalize_date_from_excel(value):
    """
    Convert Excel date/datetime to date-only string; keep time stripped only.
    Keep the user's separator as-is: / or - or whatever they used (RTL/LTR).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    try:
        if hasattr(value, 'strftime'):
            return value.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        pass
    return str(value).strip()


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
@role_required('can_create_transcripts')
def create_transcript(request):
    """Create transcripts - individual or bulk via Excel"""
    form = TranscriptForm(user=request.user)
    previous_post_data = {}
    input_method = 'individual'
    
    if request.method == 'POST':
        template_id = request.POST.get('template')
        form = TranscriptForm(request.POST, request.FILES, user=request.user, template_id=template_id)
        previous_post_data = request.POST.dict()
        input_method = previous_post_data.get('input_method', 'individual')
        
        if form.is_valid():
            try:
                template = form.cleaned_data['template']
                excel_file = form.cleaned_data.get('excel_file')
                email_column = form.cleaned_data.get('email_column', '')
                individual_email = form.cleaned_data.get('individual_email', '')
                
                success = False
                
                if excel_file:
                    # Bulk processing from Excel
                    try:
                        if str(excel_file).lower().endswith(('.xls', '.xlsx')):
                            df = pd.read_excel(excel_file)
                        else:
                            raise ValueError("نوع الملف غير مدعوم")
                        
                        # Remove duplicate rows
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
                                    f"تم تجاهل {removed} صف مكرر في ملف Excel"
                                )
                        
                        # Build list of transcript data from Excel
                        transcripts_data = []
                        for index, row in df.iterrows():
                            trans_data = {}
                            email = None
                            
                            for field_name, is_active in template.active_fields.items():
                                if not is_active:
                                    continue
                                
                                column_name = form.cleaned_data.get(f'column_{field_name}', '')
                                if column_name and column_name in df.columns:
                                    value = row[column_name]
                                    if pd.notna(value):
                                        if field_name in ['gpa']:
                                            try:
                                                numeric_value = float(value)
                                                value = round(numeric_value, 2)
                                            except (ValueError, TypeError):
                                                pass
                                        elif field_name.endswith('_percentage'):
                                            value = _normalize_percentage_from_excel(value)
                                        elif field_name in TRANSCRIPT_DATE_FIELDS:
                                            value = _normalize_date_from_excel(value)
                                        trans_data[field_name] = str(value).strip()
                            
                            if email_column and email_column in df.columns:
                                email_value = row[email_column]
                                if pd.notna(email_value):
                                    email = ''.join(str(email_value).split())
                            
                            transcripts_data.append((trans_data, email))
                        
                        # Generate transcripts
                        for trans_data, email in transcripts_data:
                            try:
                                success = _generate_and_save_transcript(
                                    request, template, trans_data, email
                                )
                            except Exception as e:
                                name = trans_data.get('arabic_name') or trans_data.get('english_name') or 'غير محدد'
                                error_msg = sanitize_error_message(str(e))
                                messages.error(request, f"خطأ في إنشاء سجل {name}: {error_msg}")
                        
                        if success:
                            messages.success(request, f"تم إنشاء {len(transcripts_data)} سجل بنجاح")
                            return redirect('transcript_success')
                    
                    except Exception as e:
                        error_msg = sanitize_error_message(str(e))
                        messages.error(request, f"خطأ في معالجة ملف Excel: {error_msg}")
                        return redirect('transcript_create')
                
                else:
                    # Individual transcript
                    trans_data = {}
                    for field_name, is_active in template.active_fields.items():
                        if not is_active:
                            continue
                        
                        value = form.cleaned_data.get(f'single_{field_name}', '')
                        if value:
                            trans_data[field_name] = value.strip()
                    
                    if not trans_data:
                        messages.error(request, 'يرجى إدخال بيانات السجل')
                        return redirect('transcript_create')
                    
                    email = individual_email.strip() if individual_email else None
                    
                    success = _generate_and_save_transcript(request, template, trans_data, email)
                    
                    if success:
                        messages.success(request, "تم إنشاء السجل بنجاح")
                        return redirect('transcript_success')
                    else:
                        messages.error(request, "فشل إنشاء السجل")
                        return redirect('transcript_create')
            
            except Exception as e:
                error_msg = sanitize_error_message(str(e))
                messages.error(request, f"حدث خطأ: {error_msg}")
                return redirect('transcript_create')
    
    template_queryset = form.fields['template'].queryset
    template_fields_map = build_template_field_map(template_queryset)
    
    context = {
        'form': form,
        'template_fields_json': json.dumps(template_fields_map, ensure_ascii=False),
        'previous_form_json': json.dumps(previous_post_data, ensure_ascii=False),
        'initial_input_method': input_method or 'individual',
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    context.update({"messages": messages.get_messages(request)})
    return render(request, 'transcript/create_transcript.html', context)


def _sanitize_date_field_value(val):
    """
    Keep the user's separator (/, -, etc.). Only replace literal backslash (\)
    so it is not stored and shown as double backslash in JSON.
    """
    if not isinstance(val, str):
        return val
    return val.replace('\\', '/')


def _generate_and_save_transcript(request, template, trans_data, email=None):
    """Helper function to generate and save a single transcript"""
    try:
        for key in TRANSCRIPT_DATE_FIELDS:
            if key in trans_data and trans_data[key]:
                trans_data[key] = _sanitize_date_field_value(trans_data[key])
        # Generate unique hash
        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        hash_input = json.dumps(trans_data, sort_keys=True) + current_timestamp
        if email:
            hash_input += email
        hash_value = sha256(hash_input.encode('utf-8')).hexdigest()
        
        # Create output directory
        output_dir = os.path.join(settings.MEDIA_ROOT)
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, f'{hash_value}.pdf')
        
        # Generate the transcript
        generate_transcript(
            transcript_data=trans_data,
            hash_value=hash_value,
            template=template,
            output_file=output_file
        )
        
        if not os.path.exists(output_file):
            raise Exception('فشل في إنشاء ملف السجل')
        
        # Create transcript record
        Transcript.objects.create(
            template=template,
            hash_value=hash_value,
            certificate_hash=hash_value,
            transcript_data=trans_data,
            email=email,
            created_by=request.user
        )
        
        # Send email if provided
        if email:
            name = trans_data.get('arabic_name') or trans_data.get('english_name') or 'المستلم'
            program = (
                trans_data.get('program_name_ar') or
                trans_data.get('program_name_en') or
                'البرنامج'
            )
            transcript_link = request.build_absolute_uri(reverse('transcript_download', args=[hash_value]))
            
            email_sent = send_email(
                to=email,
                subject=f"سجل المقررات - {program}",
                attachment_path=output_file,
                course_name=program,
                certificate_link=transcript_link,
                name=name,
                custom_message="تم اصدار سجل المقررات - ",
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
        raise Exception(f"خطأ في إنشاء السجل: {str(e)}")


@login_required(login_url='/login/')
@role_required('can_view_transcripts')
def manage_transcripts(request):
    """List and manage transcripts"""
    query = request.GET.get('q', '')
    
    if _is_super_admin(request.user):
        transcripts = Transcript.objects.all()
    else:
        transcripts = Transcript.objects.filter(created_by=request.user)
    
    if query:
        transcripts = transcripts.filter(
            Q(transcript_data__icontains=query) |
            Q(certificate_hash__icontains=query) |
            Q(email__icontains=query)
        )
    
    transcripts = transcripts.order_by('-id')
    
    page = request.GET.get('page', 1)
    paginator = Paginator(transcripts, 20)
    try:
        transcripts = paginator.page(page)
    except PageNotAnInteger:
        transcripts = paginator.page(1)
    except EmptyPage:
        transcripts = paginator.page(paginator.num_pages)
    
    context = {
        'transcripts': transcripts,
        'request': request,
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    return render(request, 'transcript/manage_transcripts.html', context)


@login_required(login_url='/login/')
def download_transcript(request, certificate_hash):
    """Download transcript PDF"""
    try:
        transcript = get_object_or_404(Transcript, certificate_hash=certificate_hash)
        
        file_name = f'{certificate_hash}.pdf'
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        
        if not os.path.exists(file_path):
            messages.error(request, 'ملف السجل غير موجود')
            return redirect('transcript_manage')
        
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{file_name}"'
        return response
    
    except Exception as e:
        error_msg = sanitize_error_message(str(e))
        messages.error(request, f'حدث خطأ أثناء تحميل السجل: {error_msg}')
        return redirect('transcript_manage')


@login_required(login_url='/login/')
def success_redirect(request):
    """Success page after creating transcripts"""
    context = {
        'username': request.user.username,
        'full_name': f"{request.user.first_name} {request.user.last_name}"
    }
    
    context['success_list'] = request.session.pop('success_list', [])
    context['error_list'] = request.session.pop('error_list', [])
    
    if context['success_list']:
        messages.success(request, f"تم إنشاء وإرسال {len(context['success_list'])} سجل بنجاح")
    if context['error_list']:
        messages.warning(request, f"فشل إرسال {len(context['error_list'])} سجل")
    
    return render(request, 'transcript/success_redirect.html', context)
