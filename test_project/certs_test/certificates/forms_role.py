from django import forms
from django.contrib.auth.models import User
from .models_role import Role, UserProfile

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = [
            'name_ar', 'name_en',
            'can_view_templates', 'can_create_templates', 'can_edit_templates', 'can_delete_templates',
            'can_view_certificates', 'can_create_certificates', 'can_verify_certificates',
            'can_view_users', 'can_create_users', 'can_edit_users', 'can_delete_users',
            'can_view_roles', 'can_create_roles', 'can_edit_roles', 'can_delete_roles',
            # Advanced certificates permissions
            'can_view_advanced_templates', 'can_create_advanced_templates', 
            'can_edit_advanced_templates', 'can_delete_advanced_templates',
            'can_view_advanced_certificates', 'can_create_advanced_certificates',
            # Transcript permissions
            'can_view_transcript_templates', 'can_create_transcript_templates',
            'can_edit_transcript_templates', 'can_delete_transcript_templates',
            'can_view_transcripts', 'can_create_transcripts',
        ]
        widgets = {
            'name_ar': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: مدير النظام'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Example: super_admin'}),
            'can_view_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_view_certificates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_certificates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_verify_certificates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_view_users': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_users': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit_users': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete_users': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_view_roles': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_roles': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit_roles': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete_roles': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Advanced certificates permissions
            'can_view_advanced_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_advanced_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit_advanced_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete_advanced_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_view_advanced_certificates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_advanced_certificates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Transcript permissions
            'can_view_transcript_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_transcript_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit_transcript_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete_transcript_templates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_view_transcripts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_create_transcripts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label="الاسم الأول",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'الاسم الأول'})
    )
    last_name = forms.CharField(
        label="الاسم الأخير",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'الاسم الأخير'})
    )
    email = forms.EmailField(
        label="البريد الإلكتروني",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@domain.com'})
    )
    username = forms.CharField(
        label="اسم المستخدم",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم المستخدم'})
    )
    # Changed from ModelChoiceField to ModelMultipleChoiceField for multi-role support
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        label="الصلاحيات",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="يمكنك اختيار أكثر من صلاحية للمستخدم"
    )
    phone = forms.CharField(
        label="رقم الجوال",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '05xxxxxxxx'})
    )
    
    # Temporary role fields
    is_temporary_role = forms.BooleanField(
        label="صلاحية مؤقتة",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'temporaryRoleCheck'})
    )
    role_start_date = forms.DateTimeField(
        label="تاريخ بداية الصلاحية",
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'id': 'roleStartDate'
        })
    )
    role_end_date = forms.DateTimeField(
        label="تاريخ نهاية الصلاحية",
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'id': 'roleEndDate'
        })
    )
    
    # Supervisor organization field (only for admin roles)
    supervisor_organization = forms.CharField(
        label="اسم جهة المشرف",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: وكالة التطوير الأكاديمي',
            'id': 'supervisorOrganization'
        })
    )

    class Meta:
        model = UserProfile
        fields = ['phone', 'is_temporary_role', 'role_start_date', 'role_end_date', 'supervisor_organization']

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        if instance:
            self.fields['first_name'].initial = instance.user.first_name
            self.fields['last_name'].initial = instance.user.last_name
            self.fields['email'].initial = instance.user.email
            self.fields['username'].initial = instance.user.username
            
            # Initialize roles field with current user roles
            self.fields['roles'].initial = instance.roles.all()
            
            # Initialize temporary role fields
            self.fields['is_temporary_role'].initial = instance.is_temporary_role
            self.fields['role_start_date'].initial = instance.role_start_date
            self.fields['role_end_date'].initial = instance.role_end_date
            self.fields['supervisor_organization'].initial = instance.supervisor_organization
    
    def clean(self):
        cleaned_data = super().clean()
        is_temporary = cleaned_data.get('is_temporary_role')
        start_date = cleaned_data.get('role_start_date')
        end_date = cleaned_data.get('role_end_date')
        
        # Validate temporary role fields
        if is_temporary:
            if not start_date:
                raise forms.ValidationError('يرجى تحديد تاريخ بداية الصلاحية للصلاحية المؤقتة')
            if not end_date:
                raise forms.ValidationError('يرجى تحديد تاريخ نهاية الصلاحية للصلاحية المؤقتة')
            if start_date and end_date and start_date >= end_date:
                raise forms.ValidationError('تاريخ البداية يجب أن يكون قبل تاريخ النهاية')
        
        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        roles_changed = False
        old_roles = []
        new_roles = self.cleaned_data.get('roles', [])
        
        if not profile.user_id:
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name']
            )
            profile.user = user
        else:
            # Check if roles are changing
            if profile.pk:
                old_profile = UserProfile.objects.get(pk=profile.pk)
                old_roles = list(old_profile.roles.all())
                old_roles_set = set(r.pk for r in old_roles)
                new_roles_set = set(r.pk for r in new_roles)
                roles_changed = old_roles_set != new_roles_set
            
            profile.user.username = self.cleaned_data['username']
            profile.user.email = self.cleaned_data['email']
            profile.user.first_name = self.cleaned_data['first_name']
            profile.user.last_name = self.cleaned_data['last_name']
            
            # Handle temporary role assignment
            is_temporary = self.cleaned_data.get('is_temporary_role', False)
            if is_temporary and roles_changed:
                # Store the previous roles if this is a temporary assignment
                profile.is_temporary_role = True
                profile.role_start_date = self.cleaned_data['role_start_date']
                profile.role_end_date = self.cleaned_data['role_end_date']
            elif not is_temporary:
                # Clear temporary role data if not temporary
                profile.is_temporary_role = False
                profile.role_start_date = None
                profile.role_end_date = None
            
            # Update superuser status based on roles
            has_super_admin = any(r.name_en == 'super_admin' for r in new_roles)
            if has_super_admin:
                profile.user.is_superuser = True
                profile.user.is_staff = True
            else:
                profile.user.is_superuser = False
                profile.user.is_staff = False
            
            profile.user.save()
        
        if commit:
            profile.save()
            
            # Handle ManyToMany roles assignment
            # For temporary roles, store previous roles first
            if self.cleaned_data.get('is_temporary_role', False) and roles_changed:
                profile.previous_roles.clear()
                for old_role in old_roles:
                    profile.previous_roles.add(old_role)
            elif not self.cleaned_data.get('is_temporary_role', False):
                profile.previous_roles.clear()
            
            # Set the new roles
            profile.roles.clear()
            for role in new_roles:
                profile.roles.add(role)
            
            # Send email notification if roles changed (both temporary and permanent)
            if roles_changed:
                self._send_role_notification_email(profile, old_roles)
        
        return profile
    
    def _send_role_notification_email(self, profile, old_roles):
        """Send email notification for role assignment"""
        try:
            from certificates.email_service import send_role_notification_email
            send_role_notification_email(profile, old_roles)
        except Exception as e:
            # Log error but don't fail the save operation
            pass
