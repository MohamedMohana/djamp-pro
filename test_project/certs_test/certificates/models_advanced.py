from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os
import json
from .constants import (
    CERTIFICATE_TYPE_CHOICES, 
    DEFAULT_FIELD_SETTINGS, 
    DEFAULT_QR_SETTINGS,
    ADVANCED_CERTIFICATE_FIELDS
)


class AdvancedCertificateTemplate(models.Model):
    """
    Advanced template for KKUx certificates with flexible field configuration.
    Supports dynamic fields, multiple languages, and per-field styling.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم القالب")
    pdf_file = models.FileField(
        upload_to='advanced_templates/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        verbose_name="ملف القالب"
    )
    
    # Certificate Type (Arabic RTL, English LTR, or Bilingual)
    certificate_type = models.CharField(
        max_length=20,
        choices=CERTIFICATE_TYPE_CHOICES,
        default='bilingual',
        verbose_name="نوع الشهادة"
    )
    
    # Active Fields Configuration (JSON)
    # Stores which fields are enabled for this template
    # Example: {"arabic_name": true, "english_name": true, "national_id_ar": false, ...}
    active_fields = models.JSONField(
        default=dict,
        verbose_name="الحقول النشطة"
    )
    
    # Field Settings (JSON)
    # Stores position, font, color, size for each active field
    # Example: {
    #   "arabic_name": {
    #     "x": 17.3, "y": 12.4, "font_size": 21,
    #     "font_name": "IBM_Plex_Sans_Arabic_Bold",
    #     "font_color": "#000000",
    #     "text_direction": "rtl"
    #   },
    #   ...
    # }
    field_settings = models.JSONField(
        default=dict,
        verbose_name="إعدادات الحقول"
    )
    
    # QR Code Settings (JSON)
    qr_settings = models.JSONField(
        default=dict,
        verbose_name="إعدادات QR"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='advanced_templates',
        verbose_name="تم الإنشاء بواسطة"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")
    
    class Meta:
        verbose_name = "قالب شهادة متقدم"
        verbose_name_plural = "قوالب الشهادات المتقدمة"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.get_display_name()
    
    def get_display_name(self):
        """Return display name with spaces instead of underscores"""
        return self.name.replace('_', ' ')
    
    def save(self, *args, **kwargs):
        """Clean name and ensure defaults are set"""
        # Clean the name
        self.name = self.name.replace(' ', '_').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        
        # Ensure unique name
        original_name = self.name
        counter = 1
        while AdvancedCertificateTemplate.objects.filter(name=self.name).exclude(pk=self.pk).exists():
            self.name = f"{original_name}_{counter}"
            counter += 1
        
        # Set default QR settings if not provided
        if not self.qr_settings:
            self.qr_settings = DEFAULT_QR_SETTINGS
        
        # Save the model
        super().save(*args, **kwargs)
        
        # Generate and save JSON configuration file
        self._save_json_config()
    
    def _save_json_config(self):
        """Generate JSON configuration file for the template"""
        config = {
            'certificate_type': self.certificate_type,
            'active_fields': self.active_fields,
            'field_settings': self.field_settings,
            'qr_settings': self.qr_settings
        }
        
        # Save JSON file next to the PDF template
        if self.pdf_file:
            pdf_path = self.pdf_file.path
            json_path = os.path.splitext(pdf_path)[0] + '.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get_active_field_count(self):
        """Return count of active fields"""
        return sum(1 for v in self.active_fields.values() if v)
    
    def get_field_setting(self, field_name):
        """Get settings for a specific field with defaults"""
        return self.field_settings.get(field_name, DEFAULT_FIELD_SETTINGS.copy())


class AdvancedCertificate(models.Model):
    """
    KKUx Advanced Certificate with flexible field data.
    Stores certificate data as JSON for maximum flexibility.
    """
    # Template reference
    template = models.ForeignKey(
        AdvancedCertificateTemplate,
        on_delete=models.PROTECT,
        related_name='certificates',
        verbose_name="القالب"
    )
    
    # Unique identifiers
    hash_value = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="قيمة الهاش"
    )
    certificate_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name="هاش الشهادة"
    )
    
    # Certificate Data (JSON)
    # Stores all certificate field values dynamically
    # Example: {
    #   "arabic_name": "محمد أحمد علي",
    #   "english_name": "Mohammed Ahmed Ali",
    #   "program_name_ar": "إدارة الأعمال",
    #   "gpa_en": "4.5 out of 5",
    #   ...
    # }
    certificate_data = models.JSONField(
        verbose_name="بيانات الشهادة"
    )
    
    # Optional email for sending
    email = models.EmailField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name="البريد الإلكتروني"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='advanced_certificates',
        verbose_name="تم الإنشاء بواسطة"
    )
    date = models.DateField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    
    class Meta:
        verbose_name = "Advanced certificate"
        verbose_name_plural = "Advanced certificates"
        ordering = ['-date']
        indexes = [
            models.Index(fields=['certificate_hash']),
            models.Index(fields=['created_by', '-date']),
        ]
    
    def __str__(self):
        # Try to get a name from certificate data
        name = (
            self.certificate_data.get('arabic_name') or 
            self.certificate_data.get('english_name') or 
            'شهادة متقدمة'
        )
        return f"{name} - {self.template.name}"
    
    def get_field_value(self, field_name):
        """Get value for a specific field"""
        return self.certificate_data.get(field_name, '')
    
    def get_display_name(self):
        """Get the most appropriate name for display"""
        return (
            self.certificate_data.get('arabic_name') or 
            self.certificate_data.get('english_name') or 
            'غير محدد'
        )


@receiver(post_delete, sender=AdvancedCertificate)
def delete_advanced_certificate_pdf(sender, instance, **kwargs):
    """Delete the certificate PDF when the certificate record is deleted"""
    certificate_hash = instance.certificate_hash
    if certificate_hash:
        file_name = f'{certificate_hash}.pdf'
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass  # Silently fail if file can't be deleted


@receiver(post_delete, sender=AdvancedCertificateTemplate)
def delete_advanced_template_files(sender, instance, **kwargs):
    """Delete template PDF and JSON when template is deleted"""
    if instance.pdf_file:
        pdf_path = instance.pdf_file.path
        json_path = os.path.splitext(pdf_path)[0] + '.json'
        
        # Delete PDF
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
        
        # Delete JSON
        if os.path.exists(json_path):
            try:
                os.remove(json_path)
            except Exception:
                pass

