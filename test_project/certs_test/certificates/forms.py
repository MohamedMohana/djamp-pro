# forms.py
from django import forms
from django.core.exceptions import ValidationError
from datetime import datetime
import pandas as pd
from .models_template import CertificateTemplate

class CertificateForm(forms.Form):
    name = forms.CharField(
        label="الاسم",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: أسامة بن محمد'
        })
    )
    
    email = forms.EmailField(
        label="البريد الإلكتروني",
        max_length=200,
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: user@kku.edu.sa'
        })
    )
    
    course_name = forms.CharField(
        label="اسم الدورة",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: الذكاء الاصطناعي',
            'required': 'required',
            'oninvalid': "this.setCustomValidity('الرجاء ملء هذا الحقل')",
            'oninput': "this.setCustomValidity('')"
        })
    )
    
    duration = forms.CharField(
        label="المدة",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: ٣ أيام من تاريخ ٢٠٢٢/١٢/١٩ حتى٢٠٢٢/١٢/٢٢ أو ٣ ساعات في تاريخ ٢٠٢٢/١٢/١٩',
            'required': 'required',
            'oninvalid': "this.setCustomValidity('الرجاء ملء هذا الحقل')",
            'oninput': "this.setCustomValidity('')"
        })
    )
    
    names_file = forms.FileField(
        label="تحميل الملف",
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'style': 'display: none;'
        })
    )
    
    names_column = forms.CharField(
        label="عمود الأسماء",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل اسم العمود الذي يحتوي على أسماء الطلاب'
        })
    )
    
    emails_column = forms.CharField(
        label="عمود البريد الإلكتروني",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل اسم العمود الذي يحتوي على عناوين البريد الإلكتروني'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Get available templates based on user role
        if user and (user.is_superuser or (hasattr(user, 'profile') and user.profile.is_super_admin())):
            templates = CertificateTemplate.objects.all()
        elif user:
            templates = CertificateTemplate.objects.filter(created_by=user)
        else:
            templates = CertificateTemplate.objects.none()
            
        self.fields['template'] = forms.ModelChoiceField(
            queryset=templates,
            label='القالب',
            empty_label='اختر القالب',
            to_field_name='name',  # Use name field for value
            widget=forms.Select(attrs={
                'class': 'form-control',
                'required': 'required',
                'oninvalid': "this.setCustomValidity('الرجاء اختيار القالب')",
                'oninput': "this.setCustomValidity('')"
            })
        )
        # Update template choices to show display name
        self.fields['template'].label_from_instance = lambda obj: obj.get_display_name()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return email
            
        # Remove all spaces from email
        email = ''.join(email.split())
        
        # Basic email validation
        if '@' not in email or '.' not in email:
            raise ValidationError('البريد الإلكتروني غير صالح')
            
        return email

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        email = cleaned_data.get("email")
        names_file = cleaned_data.get("names_file")
        names_column = cleaned_data.get("names_column")
        duration = cleaned_data.get("duration")

        if not (name or names_file):
            raise ValidationError("يجب تقديم اسم أو ملف أسماء")

        if names_file:
            if str(names_file).lower().endswith(('.xls', '.xlsx')):
                df = pd.read_excel(names_file)
            else:
                raise ValidationError("نوع الملف غير مدعوم. يرجى تحميل ملف Excel.")

            columns = df.columns.tolist()
            if names_column and names_column not in columns:
                raise ValidationError(f"العمود '{names_column}' غير موجود في الملف المقدم.")

            emails_column = cleaned_data.get("emails_column")
            if emails_column and emails_column not in columns:
                raise ValidationError(f"العمود '{emails_column}' غير موجود في الملف المقدم.")

            # Clean emails in the Excel file
            if emails_column:
                df[emails_column] = df[emails_column].apply(lambda x: ''.join(str(x).split()) if pd.notna(x) else x)
                # Validate each email
                invalid_emails = []
                for idx, email in enumerate(df[emails_column]):
                    if pd.notna(email) and ('@' not in str(email) or '.' not in str(email)):
                        invalid_emails.append(f"الصف {idx + 2}: {email}")
                if invalid_emails:
                    raise ValidationError(f"البريد الإلكتروني غير صالح في الصفوف التالية:\n" + "\n".join(invalid_emails))
        else:
            if not name and not email:
                raise ValidationError("يجب تقديم اسم أو بريد إلكتروني")

            if not names_column and not email:
                raise ValidationError("يجب توفير اسم العمود إذا تم تحميل ملف الأسماء")

            if not duration:
                raise ValidationError("الرجاء تحديد المدة")

            if not names_column and not email:
                raise ValidationError("يجب توفير اسم العمود للبريد الإلكتروني إذا تم تحميل ملف الأسماء")

class CreateCertificateForm(forms.Form):
    certificate_name = forms.CharField(label='Certificate Name', max_length=100)
    certificate_description = forms.CharField(label='Certificate Description', widget=forms.Textarea)

class VerifyCertificateForm(forms.Form):
    certificate_hash = forms.CharField(
        label='هاش الشهادة',
        max_length=64,
        widget=forms.TextInput(attrs={'style': 'width: 510px;'})
    )