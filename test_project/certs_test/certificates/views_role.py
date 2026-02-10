from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from collections import defaultdict
from django.db.models import Count, Q, Case, When, IntegerField
from .models_role import Role, UserProfile
from .forms_role import RoleForm, UserProfileForm
from django.contrib.auth.models import User
from .models import Certificate
from django.db.models.functions import ExtractYear, ExtractMonth

def is_superuser(user):
    """Check if user is a superuser and has a profile with super_admin role"""
    if user.is_superuser:
        return True
    try:
        profile = user.profile
        return profile.is_super_admin()
    except:
        return False

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def role_list(request):
    importance_order = Case(
        When(name_en='super_admin', then=0),
        When(name_en='advanced_admin', then=1),
        When(name_en='admin', then=2),
        When(name_en='transcript_admin', then=3),
        When(name_en='user', then=4),
        default=99,
        output_field=IntegerField()
    )
    roles = (
        Role.objects
        .annotate(
            user_count=Count('user_profiles'),  # Use the new M2M relationship
            priority=importance_order
        )
        .order_by('priority', 'id')
    )
    context = {
        'roles': roles,
        'total_roles': roles.count(),
        'page_title': 'إدارة الصلاحيات',
        'page_subtitle': 'قائمة الصلاحيات'
    }
    return render(request, 'roles/role_list.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def role_create(request):
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء الصلاحية بنجاح')
            return redirect('role_list')
    else:
        form = RoleForm()
    
    context = {
        'form': form,
        'page_title': 'إدارة الصلاحيات',
        'page_subtitle': 'إضافة صلاحية جديدة'
    }
    return render(request, 'roles/role_form.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def role_edit(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if request.method == 'POST':
        # Get all permission fields
        permissions = {}
        for field in Role._meta.fields:
            if field.name.startswith('can_'):
                permissions[field.name] = field.name in request.POST
        
        # Update role permissions
        for perm, value in permissions.items():
            setattr(role, perm, value)
        role.save()
        
        messages.success(request, 'تم تحديث الصلاحيات بنجاح')
        return redirect('role_list')
    
    context = {
        'role': role,
        'page_title': 'إدارة الصلاحيات',
        'page_subtitle': f'تعديل صلاحيات: {role.name_ar}'
    }
    return render(request, 'roles/role_permissions.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if request.method == 'POST':
        role.delete()
        messages.success(request, 'تم حذف الصلاحية بنجاح')
        return redirect('role_list')
    
    context = {
        'role': role,
        'page_title': 'إدارة الصلاحيات',
        'page_subtitle': f'حذف صلاحية: {role.name_ar}'
    }
    return render(request, 'roles/role_delete.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def user_list(request):
    query = request.GET.get('q', '')
    users = UserProfile.objects.select_related('user').prefetch_related('roles').all()
    if query:
        users = users.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(user__username__icontains=query) |
            Q(phone__icontains=query) |
            Q(roles__name_ar__icontains=query) |
            Q(roles__name_en__icontains=query)
        ).distinct()
    paginator = Paginator(users, 10)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)
    
    context = {
        'users': users_page,
        'total_users': users.count(),
        'page_title': 'إدارة المستخدمين',
        'page_subtitle': 'قائمة المستخدمين',
        'request': request,
    }
    return render(request, 'roles/user_list.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def user_create(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء المستخدم بنجاح')
            return redirect('user_list')
    else:
        form = UserProfileForm()
    
    context = {
        'form': form,
        'page_title': 'إدارة المستخدمين',
        'page_subtitle': 'إضافة مستخدم جديد'
    }
    return render(request, 'roles/user_form.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def user_edit(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث المستخدم بنجاح')
            return redirect('user_list')
    else:
        form = UserProfileForm(instance=profile)
    
    context = {
        'form': form,
        'profile': profile,
        'page_title': 'إدارة المستخدمين',
        'page_subtitle': f'تعديل مستخدم: {profile.full_name}'
    }
    return render(request, 'roles/user_form.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def user_delete(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk)
    if request.method == 'POST':
        user = profile.user
        profile.delete()
        user.delete()
        messages.success(request, 'تم حذف المستخدم بنجاح')
        return redirect('user_list')
    
    context = {
        'profile': profile,
        'page_title': 'إدارة المستخدمين',
        'page_subtitle': f'حذف مستخدم: {profile.full_name}'
    }
    return render(request, 'roles/user_delete.html', context)

@login_required(login_url='/login/')
@user_passes_test(is_superuser)
def superadmin_dashboard(request):
    try:
        # Regular Certificate statistics
        total_certificates = Certificate.objects.count()
        certificates_by_course = Certificate.objects.values('course_name').annotate(count=Count('id')).order_by('-count')[:5]
        certificates_by_creator = Certificate.objects.values('created_by__username').annotate(count=Count('id')).order_by('-count')[:5]
        top_recipients = Certificate.objects.values('name').annotate(count=Count('id')).order_by('-count')[:5]
        recent_regular_certificates = Certificate.objects.select_related('created_by').order_by('-date')[:10]
        certificates_per_month = (
            Certificate.objects
            .annotate(year=ExtractYear('date'), month=ExtractMonth('date'))
            .values('year', 'month')
            .annotate(count=Count('id'))
            .order_by('year', 'month')
        )

        # Advanced Certificate statistics (KKUx)
        advanced_certificates_per_month = []
        try:
            from .models_advanced import AdvancedCertificate, AdvancedCertificateTemplate
            total_advanced_certificates = AdvancedCertificate.objects.count()
            total_advanced_templates = AdvancedCertificateTemplate.objects.count()
            recent_advanced_certificates = AdvancedCertificate.objects.select_related('created_by', 'template').order_by('-date')[:10]
            advanced_by_creator = AdvancedCertificate.objects.values('created_by__username').annotate(count=Count('id')).order_by('-count')[:5]
            advanced_certificates_per_month = (
                AdvancedCertificate.objects
                .annotate(year=ExtractYear('date'), month=ExtractMonth('date'))
                .values('year', 'month')
                .annotate(count=Count('id'))
                .order_by('year', 'month')
            )
        except:
            # If advanced system not migrated yet, set to 0
            total_advanced_certificates = 0
            total_advanced_templates = 0
            recent_advanced_certificates = []
            advanced_by_creator = []
            advanced_certificates_per_month = []

        # Transcript statistics
        transcripts_per_month = []
        try:
            from .models_transcript import Transcript, TranscriptTemplate
            total_transcripts = Transcript.objects.count()
            total_transcript_templates = TranscriptTemplate.objects.count()
            recent_transcripts = Transcript.objects.select_related('created_by', 'template').order_by('-date')[:10]
            transcripts_by_creator = Transcript.objects.values('created_by__username').annotate(count=Count('id')).order_by('-count')[:5]
            transcripts_per_month = (
                Transcript.objects
                .annotate(year=ExtractYear('date'), month=ExtractMonth('date'))
                .values('year', 'month')
                .annotate(count=Count('id'))
                .order_by('year', 'month')
            )
        except:
            # If transcript system not migrated yet, set to 0
            total_transcripts = 0
            total_transcript_templates = 0
            recent_transcripts = []
            transcripts_by_creator = []
            transcripts_per_month = []

        # Merge regular, advanced, and transcript statistics for summary widgets
        combined_total_documents = total_certificates + total_advanced_certificates + total_transcripts
        monthly_certificate_counts = defaultdict(int)
        for entry in certificates_per_month:
            monthly_certificate_counts[(entry['year'], entry['month'])] += entry['count']
        for entry in advanced_certificates_per_month:
            monthly_certificate_counts[(entry['year'], entry['month'])] += entry['count']
        for entry in transcripts_per_month:
            monthly_certificate_counts[(entry['year'], entry['month'])] += entry['count']
        combined_certificates_per_month = [
            {'year': year, 'month': month, 'count': count}
            for (year, month), count in sorted(monthly_certificate_counts.items())
        ]

        # Ensure we always have a list (even if no certificates exist)
        if not combined_certificates_per_month:
            combined_certificates_per_month = []

        # User statistics
        total_users = User.objects.count()
        users_by_role = Role.objects.annotate(count=Count('user_profiles')).values('name_ar', 'count').order_by('-count')
        recent_users = User.objects.order_by('-date_joined')[:10]
        roles = Role.objects.annotate(user_count=Count('user_profiles'))

        def _resolve_first_value(data, keys, fallback='-'):
            for key in keys:
                value = data.get(key)
                if value:
                    return value
            return fallback

        recent_regular_certificates_data = [
            {
                'type': 'regular',
                'date': cert.date,
                'name': cert.name,
                'course_name': cert.course_name or '-',
                'duration': cert.duration or '-',
                'certificate_hash': cert.certificate_hash or '',
                'created_by': cert.created_by.username if getattr(cert, 'created_by', None) else '-',
            }
            for cert in recent_regular_certificates
        ]

        recent_advanced_certificates_data = []
        for cert in recent_advanced_certificates:
            data = cert.certificate_data or {}
            recent_advanced_certificates_data.append({
                'type': 'advanced',
                'date': cert.date,
                'name': cert.get_display_name(),
                'course_name': _resolve_first_value(
                    data,
                    ['course_name', 'program_name_ar', 'program_name_en'],
                    cert.template.get_display_name()
                ),
                'duration': _resolve_first_value(
                    data,
                    ['duration', 'duration_ar', 'duration_en', 'program_duration'],
                    '-'
                ),
                'certificate_hash': cert.certificate_hash or cert.hash_value or '',
                'created_by': cert.created_by.username if getattr(cert, 'created_by', None) else '-',
            })

        combined_recent_certificates = sorted(
            recent_regular_certificates_data + recent_advanced_certificates_data,
            key=lambda c: c['date'],
            reverse=True
        )[:10]

        context = {
            # Combined totals
            'total_documents': combined_total_documents,
            'total_certificates': combined_total_documents,  # Keep for backward compatibility
            
            # Regular certificates
            'total_regular_certificates': total_certificates,
            'certificates_by_course': certificates_by_course,
            'certificates_by_creator': certificates_by_creator,
            'top_recipients': top_recipients,
            'recent_certificates': combined_recent_certificates,
            'certificates_per_month': combined_certificates_per_month,
            
            # Advanced certificates (KKUx)
            'total_advanced_certificates': total_advanced_certificates,
            'total_advanced_templates': total_advanced_templates,
            'recent_advanced_certificates': recent_advanced_certificates,
            'advanced_by_creator': advanced_by_creator,
            
            # Transcripts
            'total_transcripts': total_transcripts,
            'total_transcript_templates': total_transcript_templates,
            'recent_transcripts': recent_transcripts,
            'transcripts_by_creator': transcripts_by_creator,
            
            # Users
            'total_users': total_users,
            'users_by_role': users_by_role,
            'recent_users': recent_users,
            'roles': roles,
            
            'page_title': 'لوحة تحكم مدير النظام',
            'page_subtitle': 'نظرة شاملة على النظام',
        }
        return render(request, 'superadmin_dashboard.html', context)
    except Exception as e:
        error_message = str(e)
        return render(request, 'superadmin_dashboard.html', {'error': error_message})