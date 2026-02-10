# Advanced Certificate Field Definitions for KKUx
# Each field can be independently enabled/disabled per template

ADVANCED_CERTIFICATE_FIELDS = {
    'arabic_name': {
        'label_ar': 'الاسم باللغة العربية',
        'label_en': 'Arabic Name',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: محمد أحمد علي السعيد',
        'placeholder_en': 'Example: Mohammed Ahmed Ali'
    },
    'english_name': {
        'label_ar': 'الاسم باللغة الإنجليزية',
        'label_en': 'English Name',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: Mohammed Ahmed Ali',
        'placeholder_en': 'Example: Mohammed Ahmed Ali'
    },
    'national_id_ar': {
        'label_ar': 'رقم السجل المدني بالعربي',
        'label_en': 'National ID (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ١٠٨٥٤٣٢١٠٩',
        'placeholder_en': 'Example: ١٠٨٥٤٣٢١٠٩'
    },
    'national_id_en': {
        'label_ar': 'رقم السجل المدني بالإنجليزي',
        'label_en': 'National ID (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 1085432109',
        'placeholder_en': 'Example: 1085432109'
    },
    'program_name_ar': {
        'label_ar': 'اسم البرنامج باللغة العربية',
        'label_en': 'Program Name (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: إدارة الأعمال',
        'placeholder_en': 'Example: Business Administration'
    },
    'program_name_en': {
        'label_ar': 'اسم البرنامج باللغة الإنجليزية',
        'label_en': 'Program Name (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: Business Administration',
        'placeholder_en': 'Example: Business Administration'
    },
    'courses_count_ar': {
        'label_ar': 'عدد المقررات بالعربي',
        'label_en': 'Courses Count (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ٢٤ مقرر',
        'placeholder_en': 'Example: ٢٤ مقرر'
    },
    'courses_count_en': {
        'label_ar': 'عدد المقررات بالإنجليزي',
        'label_en': 'Courses Count (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 24 Courses',
        'placeholder_en': 'Example: 24 Courses'
    },
    'duration_ar': {
        'label_ar': 'المدة باللغة العربية',
        'label_en': 'Duration (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: سنتان دراسيتان',
        'placeholder_en': 'Example: سنتان دراسيتان'
    },
    'duration_en': {
        'label_ar': 'المدة باللغة الإنجليزية',
        'label_en': 'Duration (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: Two Academic Years',
        'placeholder_en': 'Example: Two Academic Years'
    },
    'grade_ar': {
        'label_ar': 'التقدير العام باللغة العربية',
        'label_en': 'Grade (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ممتاز',
        'placeholder_en': 'Example: ممتاز'
    },
    'grade_en': {
        'label_ar': 'التقدير العام باللغة الإنجليزية',
        'label_en': 'Grade (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: Excellent',
        'placeholder_en': 'Example: Excellent'
    },
    'gpa_ar': {
        'label_ar': 'المعدل التراكمي باللغة العربية',
        'label_en': 'GPA (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ٤.٥ من ٥',
        'placeholder_en': 'Example: ٤.٥ من ٥'
    },
    'gpa_en': {
        'label_ar': 'المعدل التراكمي باللغة الإنجليزية',
        'label_en': 'GPA (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 4.5 out of 5',
        'placeholder_en': 'Example: 4.5 out of 5'
    },
    'issue_date': {
        'label_ar': 'تاريخ إصدار الشهادة بالميلادي',
        'label_en': 'Issue Date (Gregorian)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 2024-01-15',
        'placeholder_en': 'Example: 2024-01-15'
    }
}

# Certificate type choices
CERTIFICATE_TYPE_CHOICES = [
    ('arabic', 'عربي'),
    ('english', 'إنجليزي'),
    ('bilingual', 'ثنائي اللغة (عربي + إنجليزي)')
]

# Available fonts for advanced certificates
ADVANCED_FONTS = [
    ('IBM_Plex_Sans_Arabic_Bold', 'IBM Plex Sans Arabic - Bold'),
    ('IBM_Plex_Sans_Arabic_Regular', 'IBM Plex Sans Arabic - Regular'),
    ('din-next-lt-w23-bold', 'Din Next LT - Bold'),
    ('GESS', 'GESS'),
    ('Bressay-Bold', 'Bressay Bold'),
    ('majallab', 'Majalla'),
]

# Default field settings
DEFAULT_FIELD_SETTINGS = {
    'x': 15.0,
    'y': 10.0,
    'font_size': 18,
    'font_name': 'IBM_Plex_Sans_Arabic_Regular',
    'font_color': '#000000',
    'text_direction': 'rtl',
    'text_anchor': 'left',
    'enabled': True
}

# Default QR settings
DEFAULT_QR_SETTINGS = {
    'x': 6.9,
    'y': 1.2,
    'size': 5.0,
    'rotation_angle': 0
}

