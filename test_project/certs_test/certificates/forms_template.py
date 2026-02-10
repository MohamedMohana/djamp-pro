from django import forms
from .models_template import CertificateTemplate
import os

class CertificateTemplateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get available fonts from the static/fonts directory
        fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
        available_fonts = []
        if os.path.exists(fonts_dir):
            for file in os.listdir(fonts_dir):
                if file.endswith(('.ttf', '.otf')):
                    font_name = os.path.splitext(file)[0]
                    font_display = font_name.replace('-', ' ').title()
                    available_fonts.append((font_name, font_display))
        if not available_fonts:
            available_fonts = [('din-next-lt-w23-bold', 'Din Next Lt W23 Bold')]
        self.fields['font_name'].choices = sorted(available_fonts, key=lambda x: x[1])
        
        # Make pdf_file optional when editing
        if self.instance and self.instance.pk:
            self.fields['pdf_file'].required = False
        
        # Set initial values for all fields
        self.fields['name_x'].initial = 17.3
        self.fields['name_y'].initial = 12.4
        self.fields['name_font_size'].initial = 21
        self.fields['course_x'].initial = 18
        self.fields['course_y'].initial = 9.6
        self.fields['course_font_size'].initial = 21
        self.fields['date_x'].initial = 24.6
        self.fields['date_y'].initial = 6.9
        self.fields['date_font_size'].initial = 21
        self.fields['qr_x'].initial = 6.9
        self.fields['qr_y'].initial = 1.2
        self.fields['qr_size'].initial = 5
        self.fields['qr_rotation'].initial = 0
    
    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file:
            # Check file extension
            if not pdf_file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('يرجى تحميل ملف PDF فقط')
            
            # Check file size (500KB = 500 * 1024 bytes)
            max_size = 500 * 1024  # 500KB in bytes
            if pdf_file.size > max_size:
                raise forms.ValidationError('حجم الملف يتجاوز المساحة المسموحة (500 كيلوبايت). يرجى تحميل ملف أصغر.')
        
        return pdf_file
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pdf_file:
            # Generate a unique filename using timestamp and random string
            import time
            import random
            import string
            import os
            
            # Get the original filename without extension
            filename = os.path.splitext(instance.pdf_file.name)[0]
            # Generate random suffix
            suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            # Create new filename with timestamp and random suffix
            new_filename = f"{filename}_{suffix}.pdf"
            
            # Rename the file
            instance.pdf_file.name = new_filename
        
        if commit:
            instance.save()
        return instance

    font_name = forms.ChoiceField(choices=[], label='اختر الخط')
    font_color = forms.CharField(
        initial='#000000',
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        label='اختر اللون'
    )

    class Meta:
        model = CertificateTemplate
        fields = [
            'name', 'pdf_file', 'font_name', 'font_color',
            'name_x', 'name_y', 'name_font_size',
            'course_x', 'course_y', 'course_font_size',
            'date_x', 'date_y', 'date_font_size',
            'qr_x', 'qr_y', 'qr_size', 'qr_rotation'
        ]
        labels = {
            'name': 'اسم القالب',
            'pdf_file': 'ملف القالب',
            'name_x': 'موقع الاسم (X)',
            'name_y': 'موقع الاسم (Y)',
            'name_font_size': 'حجم خط الاسم',
            'course_x': 'موقع اسم الدورة (X)',
            'course_y': 'موقع اسم الدورة (Y)',
            'course_font_size': 'حجم خط اسم الدورة',
            'date_x': 'موقع المدة (X)',
            'date_y': 'موقع المدة (Y)',
            'date_font_size': 'حجم خط المدة',
            'qr_x': 'موقع QR (X)',
            'qr_y': 'موقع QR (Y)',
            'qr_size': 'حجم QR',
            'qr_rotation': 'دوران QR'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
            'name_x': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'name_y': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'name_font_size': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'course_x': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'course_y': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'course_font_size': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'date_x': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'date_y': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'date_font_size': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'qr_x': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'qr_y': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'qr_size': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'qr_rotation': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'})
        }