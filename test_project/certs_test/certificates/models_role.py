from django.db import models
from django.contrib.auth.models import User

class Role(models.Model):
    name_ar = models.CharField(max_length=50, verbose_name="اسم الصلاحية بالعربي")
    name_en = models.CharField(max_length=50, verbose_name="اسم الصلاحية بالإنجليزي")
    
    # Permissions for templates
    can_view_templates = models.BooleanField(default=False, verbose_name="عرض القوالب")
    can_create_templates = models.BooleanField(default=False, verbose_name="إنشاء القوالب")
    can_edit_templates = models.BooleanField(default=False, verbose_name="تعديل القوالب")
    can_delete_templates = models.BooleanField(default=False, verbose_name="حذف القوالب")
    
    # Permissions for certificates
    can_view_certificates = models.BooleanField(default=True, verbose_name="عرض الشهادات")
    can_create_certificates = models.BooleanField(default=False, verbose_name="إنشاء الشهادات")
    can_verify_certificates = models.BooleanField(default=True, verbose_name="التحقق من الشهادات")
    
    # Permissions for users
    can_view_users = models.BooleanField(default=False, verbose_name="عرض المستخدمين")
    can_create_users = models.BooleanField(default=False, verbose_name="إنشاء المستخدمين")
    can_edit_users = models.BooleanField(default=False, verbose_name="تعديل المستخدمين")
    can_delete_users = models.BooleanField(default=False, verbose_name="حذف المستخدمين")
    
    # Permissions for roles
    can_view_roles = models.BooleanField(default=False, verbose_name="عرض الصلاحيات")
    can_create_roles = models.BooleanField(default=False, verbose_name="إنشاء الصلاحيات")
    can_edit_roles = models.BooleanField(default=False, verbose_name="تعديل الصلاحيات")
    can_delete_roles = models.BooleanField(default=False, verbose_name="حذف الصلاحيات")
    
    # Permissions for advanced templates (KKUx)
    can_view_advanced_templates = models.BooleanField(default=False, verbose_name="عرض القوالب المتقدمة")
    can_create_advanced_templates = models.BooleanField(default=False, verbose_name="إنشاء القوالب المتقدمة")
    can_edit_advanced_templates = models.BooleanField(default=False, verbose_name="تعديل القوالب المتقدمة")
    can_delete_advanced_templates = models.BooleanField(default=False, verbose_name="حذف القوالب المتقدمة")
    
    # Permissions for advanced certificates (KKUx)
    can_view_advanced_certificates = models.BooleanField(default=False, verbose_name="عرض الشهادات المتقدمة")
    can_create_advanced_certificates = models.BooleanField(default=False, verbose_name="إنشاء الشهادات المتقدمة")
    
    # Permissions for transcript templates (سجل المقررات)
    can_view_transcript_templates = models.BooleanField(default=False, verbose_name="عرض قوالب السجلات")
    can_create_transcript_templates = models.BooleanField(default=False, verbose_name="إنشاء قوالب السجلات")
    can_edit_transcript_templates = models.BooleanField(default=False, verbose_name="تعديل قوالب السجلات")
    can_delete_transcript_templates = models.BooleanField(default=False, verbose_name="حذف قوالب السجلات")
    
    # Permissions for transcripts (سجل المقررات)
    can_view_transcripts = models.BooleanField(default=False, verbose_name="عرض السجلات")
    can_create_transcripts = models.BooleanField(default=False, verbose_name="إنشاء السجلات")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name_ar

    class Meta:
        verbose_name = "صلاحية"
        verbose_name_plural = "الصلاحيات"
        ordering = ['id']
        
    @property
    def permissions_summary(self):
        """Get a summary of permissions for display"""
        permissions = []
        if self.can_view_templates: permissions.append("عرض القوالب")
        if self.can_create_templates: permissions.append("إنشاء القوالب")
        if self.can_edit_templates: permissions.append("تعديل القوالب")
        if self.can_delete_templates: permissions.append("حذف القوالب")
        if self.can_view_certificates: permissions.append("عرض الشهادات")
        if self.can_create_certificates: permissions.append("إنشاء الشهادات")
        if self.can_verify_certificates: permissions.append("التحقق من الشهادات")
        if self.can_view_users: permissions.append("عرض المستخدمين")
        if self.can_create_users: permissions.append("إنشاء المستخدمين")
        if self.can_edit_users: permissions.append("تعديل المستخدمين")
        if self.can_delete_users: permissions.append("حذف المستخدمين")
        if self.can_view_roles: permissions.append("عرض الصلاحيات")
        if self.can_create_roles: permissions.append("إنشاء الصلاحيات")
        if self.can_edit_roles: permissions.append("تعديل الصلاحيات")
        if self.can_delete_roles: permissions.append("حذف الصلاحيات")
        if self.can_view_advanced_templates: permissions.append("عرض القوالب المتقدمة")
        if self.can_create_advanced_templates: permissions.append("إنشاء القوالب المتقدمة")
        if self.can_edit_advanced_templates: permissions.append("تعديل القوالب المتقدمة")
        if self.can_delete_advanced_templates: permissions.append("حذف القوالب المتقدمة")
        if self.can_view_advanced_certificates: permissions.append("عرض الشهادات المتقدمة")
        if self.can_create_advanced_certificates: permissions.append("إنشاء الشهادات المتقدمة")
        if self.can_view_transcript_templates: permissions.append("عرض قوالب السجلات")
        if self.can_create_transcript_templates: permissions.append("إنشاء قوالب السجلات")
        if self.can_edit_transcript_templates: permissions.append("تعديل قوالب السجلات")
        if self.can_delete_transcript_templates: permissions.append("حذف قوالب السجلات")
        if self.can_view_transcripts: permissions.append("عرض السجلات")
        if self.can_create_transcripts: permissions.append("إنشاء السجلات")
        return permissions

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Legacy field - kept for backwards compatibility during migration
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    # New multi-role field
    roles = models.ManyToManyField(Role, related_name='user_profiles', blank=True, verbose_name="الصلاحيات")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="رقم الجوال")
    
    # Temporary role fields
    is_temporary_role = models.BooleanField(default=False, verbose_name="صلاحية مؤقتة")
    role_start_date = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ بداية الصلاحية")
    role_end_date = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ نهاية الصلاحية")
    previous_roles = models.ManyToManyField(Role, related_name='previous_user_profiles', blank=True, verbose_name="الصلاحيات السابقة")
    # Legacy field - kept for backwards compatibility during migration
    previous_role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_profiles', verbose_name="الصلاحية السابقة")
    
    # Supervisor organization field (only for admin roles)
    supervisor_organization = models.CharField(max_length=200, null=True, blank=True, verbose_name="اسم جهة المشرف")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        roles_list = self.roles.all()
        if roles_list.exists():
            role_names = ', '.join([r.name_ar for r in roles_list[:3]])
            if roles_list.count() > 3:
                role_names += f' (+{roles_list.count() - 3})'
            return f"{self.user.get_full_name()} ({role_names})"
        return f"{self.user.get_full_name()} (بدون صلاحية)"

    class Meta:
        verbose_name = "ملف المستخدم"
        verbose_name_plural = "ملفات المستخدمين"
        ordering = ['-created_at']

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def username(self):
        return self.user.username
    
    def has_permission(self, permission_name):
        """Check if user has permission from any of their roles"""
        if not self.roles.exists():
            return False
        return self.roles.filter(**{permission_name: True}).exists()
    
    def is_super_admin(self):
        """Check if user has super_admin role"""
        return self.roles.filter(name_en='super_admin').exists()
    
    def get_roles_display(self):
        """Get a comma-separated list of role names in Arabic"""
        roles_list = self.roles.all()
        if roles_list.exists():
            return ', '.join([r.name_ar for r in roles_list])
        return 'بدون صلاحية'
    
    def get_primary_role(self):
        """Get the primary role (first role or super_admin if present)"""
        # Super admin takes priority
        super_admin = self.roles.filter(name_en='super_admin').first()
        if super_admin:
            return super_admin
        return self.roles.first()
    
    def is_role_expired(self):
        """Check if the temporary role has expired"""
        if not self.is_temporary_role or not self.role_end_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.role_end_date
    
    def check_and_expire_role(self):
        """Check if role has expired and revert to previous roles if needed"""
        if self.is_role_expired():
            # Store the expired roles for notification purposes
            expired_roles = list(self.roles.all())
            
            # Revert to previous roles
            self.roles.clear()
            for prev_role in self.previous_roles.all():
                self.roles.add(prev_role)
            
            self.is_temporary_role = False
            self.role_start_date = None
            self.role_end_date = None
            self.previous_roles.clear()
            
            # Update superuser status based on new roles
            if self.is_super_admin():
                self.user.is_superuser = True
                self.user.is_staff = True
            else:
                self.user.is_superuser = False
                self.user.is_staff = False
            
            self.user.save()
            self.save()
            
            return expired_roles
        return None
