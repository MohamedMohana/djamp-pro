from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import pandas as pd
from .models_advanced import AdvancedCertificateTemplate
from .constants import (
    ADVANCED_CERTIFICATE_FIELDS,
    CERTIFICATE_TYPE_CHOICES,
    ADVANCED_FONTS,
    DEFAULT_FIELD_SETTINGS
)


class AdvancedTemplateForm(forms.ModelForm):
    """Form for creating/editing advanced certificate templates"""
    
    # Certificate Type
    certificate_type = forms.ChoiceField(
        choices=CERTIFICATE_TYPE_CHOICES,
        label='نوع الشهادة',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = AdvancedCertificateTemplate
        fields = ['name', 'pdf_file', 'certificate_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثال: شهادة KKUx إدارة الأعمال'
            }),
            'pdf_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf'
            }),
        }
        labels = {
            'name': 'اسم القالب',
            'pdf_file': 'ملف القالب (PDF)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make pdf_file optional when editing
        if self.instance and self.instance.pk:
            self.fields['pdf_file'].required = False
    
    def clean_pdf_file(self):
        """Validate PDF file"""
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file:
            # Check file extension
            if not pdf_file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('يرجى تحميل ملف PDF فقط')
            
            # Check file size (500KB max)
            max_size = 500 * 1024  # 500KB in bytes
            if pdf_file.size > max_size:
                raise forms.ValidationError('حجم الملف يتجاوز المساحة المسموحة (500 كيلوبايت)')
        
        return pdf_file


class AdvancedCertificateForm(forms.Form):
    """Dynamic form for creating advanced certificates"""
    
    # Template selection
    template = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        label='القالب المتقدم',
        empty_label='اختر القالب المتقدم',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': 'required',
            'id': 'advanced_template_select'
        })
    )
    
    # Excel file upload
    excel_file = forms.FileField(
        label='رفع ملف Excel',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xls,.xlsx',
            'id': 'advanced_excel_file'
        })
    )
    
    # Email column (for Excel)
    email_column = forms.CharField(
        label='عمود البريد الإلكتروني',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'اسم العمود في Excel',
            'id': 'advanced_email_column'
        })
    )
    
    # Individual email (for manual entry)
    individual_email = forms.EmailField(
        label='البريد الإلكتروني',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: user@kku.edu.sa',
            'id': 'advanced_individual_email'
        })
    )
    
    course_name = forms.CharField(
        label='اسم الدورة',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: الذكاء الاصطناعي'
        })
    )
    
    duration = forms.CharField(
        label='المدة',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: ٣ أيام من تاريخ ٢٠٢٢/١٢/١٩ حتى ٢٠٢٢/١٢/٢٢'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        template_id = kwargs.pop('template_id', None)
        super().__init__(*args, **kwargs)
        
        # Set template queryset based on user permissions
        if user and (user.is_superuser or (hasattr(user, 'profile') and user.profile.is_super_admin())):
            templates = AdvancedCertificateTemplate.objects.all()
        elif user:
            templates = AdvancedCertificateTemplate.objects.filter(created_by=user)
        else:
            templates = AdvancedCertificateTemplate.objects.none()
        
        self.fields['template'].queryset = templates
        self.fields['template'].label_from_instance = lambda obj: obj.get_display_name()
        
        # If template is pre-selected, add dynamic fields
        if template_id:
            try:
                template = AdvancedCertificateTemplate.objects.get(id=template_id)
                self._add_dynamic_fields(template)
            except AdvancedCertificateTemplate.DoesNotExist:
                pass
    
    def _add_dynamic_fields(self, template):
        """Add dynamic fields based on template's active fields"""
        active_fields = template.active_fields
        
        for field_name, is_active in active_fields.items():
            if not is_active:
                continue
            
            # Get field configuration
            field_config = ADVANCED_CERTIFICATE_FIELDS.get(field_name, {})
            label_ar = field_config.get('label_ar', field_name)
            placeholder_ar = field_config.get('placeholder_ar', '')
            
            # Add individual field
            self.fields[f'single_{field_name}'] = forms.CharField(
                label=label_ar,
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'form-control dynamic-field',
                    'placeholder': placeholder_ar,
                    'data-field': field_name
                })
            )
            
            # Add Excel column mapping field
            self.fields[f'column_{field_name}'] = forms.CharField(
                label=f'عمود {label_ar}',
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'form-control column-mapping',
                    'placeholder': f'اسم عمود {label_ar} في Excel',
                    'data-field': field_name,
                    'disabled': 'disabled'  # Enabled via JavaScript when Excel is uploaded
                })
            )
    
    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        excel_file = cleaned_data.get('excel_file')
        template = cleaned_data.get('template')
        course_name = (cleaned_data.get('course_name') or '').strip()
        duration = (cleaned_data.get('duration') or '').strip()
        
        if not template:
            raise ValidationError('يرجى اختيار قالب متقدم')
        active_fields = template.active_fields or {}
        
        # Check if we have either individual fields or Excel file
        has_single_data = any(
            cleaned_data.get(f'single_{field_name}')
            for field_name in active_fields.keys()
            if active_fields.get(field_name)
        )
        
        if not excel_file and not has_single_data:
            raise ValidationError('يرجى إدخال البيانات يدوياً أو رفع ملف Excel')
        
        # Require email when creating a single certificate
        if not excel_file and not cleaned_data.get('individual_email'):
            raise ValidationError('يرجى إدخال البريد الإلكتروني عند إنشاء شهادة فردية')
        
        # Validate Excel file if provided
        if excel_file:
            try:
                if str(excel_file).lower().endswith(('.xls', '.xlsx')):
                    df = pd.read_excel(excel_file)
                else:
                    raise ValidationError('نوع الملف غير مدعوم. يرجى تحميل ملف Excel')
                
                # Check if required column mappings are provided
                for field_name, is_active in active_fields.items():
                    if not is_active:
                        continue
                    
                    column_name = cleaned_data.get(f'column_{field_name}')
                    if column_name and column_name not in df.columns:
                        field_config = ADVANCED_CERTIFICATE_FIELDS.get(field_name, {})
                        label = field_config.get('label_ar', field_name)
                        raise ValidationError(f"العمود '{column_name}' لـ '{label}' غير موجود في الملف")
                
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f'خطأ في قراءة ملف Excel: {str(e)}')
        
        cleaned_data['course_name'] = course_name
        cleaned_data['duration'] = duration
        
        requires_course_name = not active_fields.get('program_name_ar')
        requires_duration = not active_fields.get('duration_ar')
        
        if requires_course_name and not course_name:
            self.add_error('course_name', 'يرجى إدخال اسم الدورة لعدم توفر حقل اسم البرنامج في القالب.')
        if requires_duration and not duration:
            self.add_error('duration', 'يرجى إدخال المدة لعدم توفر حقل المدة في القالب.')
        
        return cleaned_data

