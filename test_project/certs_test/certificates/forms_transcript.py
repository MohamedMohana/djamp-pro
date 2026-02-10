"""
Forms for Transcript (سجل المقررات) System
Supports dynamic course fields and Excel bulk upload
"""
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import pandas as pd
from .models_transcript import TranscriptTemplate
from .constants_transcript import (
    TRANSCRIPT_FIELDS,
    TRANSCRIPT_TYPE_CHOICES,
    DEFAULT_TRANSCRIPT_FIELD_SETTINGS,
    MAX_COURSES,
    get_base_fields,
    get_course_fields_for_count
)


class TranscriptTemplateForm(forms.ModelForm):
    """Form for creating/editing transcript templates"""
    
    # Transcript Type
    transcript_type = forms.ChoiceField(
        choices=TRANSCRIPT_TYPE_CHOICES,
        label='نوع السجل',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Number of courses
    active_course_count = forms.IntegerField(
        label='عدد المقررات',
        min_value=1,
        max_value=MAX_COURSES,
        initial=8,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': f'1 - {MAX_COURSES}'
        }),
        help_text=f'عدد المقررات التي سيتم عرضها في السجل (الحد الأقصى {MAX_COURSES})'
    )
    
    class Meta:
        model = TranscriptTemplate
        fields = ['name', 'pdf_file', 'transcript_type', 'active_course_count']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثال: سجل مقررات دبلوم الحوكمة'
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
    
    def clean_active_course_count(self):
        """Validate course count"""
        count = self.cleaned_data.get('active_course_count')
        if count is None:
            return 8  # Default
        if count < 1:
            raise forms.ValidationError('يجب أن يكون عدد المقررات 1 على الأقل')
        if count > MAX_COURSES:
            raise forms.ValidationError(f'الحد الأقصى لعدد المقررات هو {MAX_COURSES}')
        return count


class TranscriptForm(forms.Form):
    """Dynamic form for creating transcripts"""
    
    # Template selection
    template = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        label='قالب السجل',
        empty_label='اختر قالب السجل',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': 'required',
            'id': 'transcript_template_select'
        })
    )
    
    # Excel file upload
    excel_file = forms.FileField(
        label='رفع ملف Excel',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xls,.xlsx',
            'id': 'transcript_excel_file'
        })
    )
    
    # Email column (for Excel)
    email_column = forms.CharField(
        label='عمود البريد الإلكتروني',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'اسم العمود في Excel',
            'id': 'transcript_email_column'
        })
    )
    
    # Individual email (for manual entry)
    individual_email = forms.EmailField(
        label='البريد الإلكتروني',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: user@kku.edu.sa',
            'id': 'transcript_individual_email'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        template_id = kwargs.pop('template_id', None)
        super().__init__(*args, **kwargs)
        
        # Set template queryset based on user permissions
        if user and (user.is_superuser or (hasattr(user, 'profile') and user.profile and user.profile.is_super_admin())):
            templates = TranscriptTemplate.objects.all()
        elif user:
            templates = TranscriptTemplate.objects.filter(created_by=user)
        else:
            templates = TranscriptTemplate.objects.none()
        
        self.fields['template'].queryset = templates
        self.fields['template'].label_from_instance = lambda obj: obj.get_display_name()
        
        # If template is pre-selected, add dynamic fields
        if template_id:
            try:
                template = TranscriptTemplate.objects.get(id=template_id)
                self._add_dynamic_fields(template)
            except TranscriptTemplate.DoesNotExist:
                pass
    
    def _add_dynamic_fields(self, template):
        """Add dynamic fields based on template's active fields"""
        active_fields = template.active_fields or {}
        
        for field_name, is_active in active_fields.items():
            if not is_active:
                continue
            
            # Get field configuration
            field_config = TRANSCRIPT_FIELDS.get(field_name, {})
            label_ar = field_config.get('label_ar', field_name)
            placeholder_ar = field_config.get('placeholder_ar', '')
            direction = field_config.get('direction', 'rtl')
            
            # Add individual field
            self.fields[f'single_{field_name}'] = forms.CharField(
                label=label_ar,
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'form-control dynamic-field',
                    'placeholder': placeholder_ar,
                    'data-field': field_name,
                    'dir': direction
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
        
        if not template:
            raise ValidationError('يرجى اختيار قالب السجل')
        
        active_fields = template.active_fields or {}
        
        # Check if we have either individual fields or Excel file
        has_single_data = any(
            cleaned_data.get(f'single_{field_name}')
            for field_name in active_fields.keys()
            if active_fields.get(field_name)
        )
        
        if not excel_file and not has_single_data:
            raise ValidationError('يرجى إدخال البيانات يدوياً أو رفع ملف Excel')
        
        # Require email when creating a single transcript
        if not excel_file and not cleaned_data.get('individual_email'):
            raise ValidationError('يرجى إدخال البريد الإلكتروني عند إنشاء سجل فردي')
        
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
                        field_config = TRANSCRIPT_FIELDS.get(field_name, {})
                        label = field_config.get('label_ar', field_name)
                        raise ValidationError(f"العمود '{column_name}' لـ '{label}' غير موجود في الملف")
                
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f'خطأ في قراءة ملف Excel: {str(e)}')
        
        return cleaned_data


def build_template_field_map(templates):
    """Return serializable map of template ids to active field metadata"""
    template_map = {}
    for template in templates:
        active_config = {}
        template_fields = template.active_fields or {}
        
        # Get base fields first
        base_fields = get_base_fields()
        for field_name in base_fields.keys():
            if not template_fields.get(field_name):
                continue
            field_config = TRANSCRIPT_FIELDS.get(field_name, {})
            active_config[field_name] = {
                'label': field_config.get('label_ar', field_name),
                'placeholder': field_config.get('placeholder_ar', ''),
                'direction': field_config.get('direction', 'rtl'),
                'category': field_config.get('category', 'other')
            }
        
        # Get course fields based on template's course count
        course_fields = get_course_fields_for_count(template.active_course_count)
        for field_name in course_fields.keys():
            if not template_fields.get(field_name):
                continue
            field_config = TRANSCRIPT_FIELDS.get(field_name, {})
            active_config[field_name] = {
                'label': field_config.get('label_ar', field_name),
                'placeholder': field_config.get('placeholder_ar', ''),
                'direction': field_config.get('direction', 'rtl'),
                'category': field_config.get('category', 'courses'),
                'course_number': field_config.get('course_number')
            }
        
        template_map[str(template.id)] = {
            'name': template.get_display_name(),
            'course_count': template.active_course_count,
            'fields': active_config
        }
    return template_map
