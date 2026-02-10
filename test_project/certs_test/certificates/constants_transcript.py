# Transcript Field Definitions for سجل المقررات
# Each field can be independently enabled/disabled per template
# Supports dynamic course fields (1-30) for flexible transcript layouts

# Maximum number of courses supported
MAX_COURSES = 30

# Base transcript fields (non-course related)
TRANSCRIPT_BASE_FIELDS = {
    'arabic_name': {
        'label_ar': 'الاسم باللغة العربية',
        'label_en': 'Arabic Name',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: محمد أحمد علي السعيد',
        'placeholder_en': 'Example: Mohammed Ahmed Ali',
        'category': 'student_info'
    },
    'english_name': {
        'label_ar': 'الاسم باللغة الإنجليزية',
        'label_en': 'English Name',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: Mohammed Ahmed Ali',
        'placeholder_en': 'Example: Mohammed Ahmed Ali',
        'category': 'student_info'
    },
    'national_id_ar': {
        'label_ar': 'رقم الهوية بالعربي',
        'label_en': 'National ID (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ١٠٨٥٤٣٢١٠٩',
        'placeholder_en': 'Example: ١٠٨٥٤٣٢١٠٩',
        'category': 'student_info'
    },
    'national_id_en': {
        'label_ar': 'رقم الهوية بالإنجليزي',
        'label_en': 'National ID (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 1085432109',
        'placeholder_en': 'Example: 1085432109',
        'category': 'student_info'
    },
    'program_name_ar': {
        'label_ar': 'اسم البرنامج باللغة العربية',
        'label_en': 'Program Name (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: إدارة الأعمال',
        'placeholder_en': 'Example: Business Administration',
        'category': 'program_info'
    },
    'program_name_en': {
        'label_ar': 'اسم البرنامج باللغة الإنجليزية',
        'label_en': 'Program Name (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: Business Administration',
        'placeholder_en': 'Example: Business Administration',
        'category': 'program_info'
    },
    'issue_date_ar': {
        'label_ar': 'تاريخ إصدار السجل بالعربي',
        'label_en': 'Issue Date (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ١٤٤٥/٠٦/١٥',
        'placeholder_en': 'Example: ١٤٤٥/٠٦/١٥',
        'category': 'program_info'
    },
    'issue_date_en': {
        'label_ar': 'تاريخ إصدار السجل بالإنجليزي',
        'label_en': 'Issue Date (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 2024-01-15',
        'placeholder_en': 'Example: 2024-01-15',
        'category': 'program_info'
    },
    'credit_hours_ar': {
        'label_ar': 'عدد الساعات الدراسية المعتمدة بالعربي',
        'label_en': 'Credit Hours (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ١٢٠ ساعة',
        'placeholder_en': 'Example: ١٢٠ ساعة',
        'category': 'program_info'
    },
    'credit_hours_en': {
        'label_ar': 'عدد الساعات الدراسية المعتمدة بالإنجليزي',
        'label_en': 'Credit Hours (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 120 Hours',
        'placeholder_en': 'Example: 120 Hours',
        'category': 'program_info'
    },
    'gpa': {
        'label_ar': 'المعدل التراكمي',
        'label_en': 'GPA',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: 4.5',
        'placeholder_en': 'Example: 4.5',
        'category': 'summary'
    },
    'overall_grade_ar': {
        'label_ar': 'التقدير العام بالعربي',
        'label_en': 'Overall Grade (Arabic)',
        'type': 'text',
        'required': False,
        'direction': 'rtl',
        'placeholder_ar': 'مثال: ممتاز',
        'placeholder_en': 'Example: ممتاز',
        'category': 'summary'
    },
    'overall_grade_en': {
        'label_ar': 'التقدير العام بالإنجليزي',
        'label_en': 'Overall Grade (English)',
        'type': 'text',
        'required': False,
        'direction': 'ltr',
        'placeholder_ar': 'مثال: Excellent',
        'placeholder_en': 'Example: Excellent',
        'category': 'summary'
    },
}


def _generate_course_fields(course_number):
    """Generate field definitions for a single course"""
    return {
        f'course_{course_number}_name_ar': {
            'label_ar': f'اسم المقرر {course_number} بالعربي',
            'label_en': f'Course {course_number} Name (Arabic)',
            'type': 'text',
            'required': False,
            'direction': 'rtl',
            'placeholder_ar': 'مثال: مقدمة في البرمجة',
            'placeholder_en': 'Example: مقدمة في البرمجة',
            'category': 'courses',
            'course_number': course_number
        },
        f'course_{course_number}_name_en': {
            'label_ar': f'اسم المقرر {course_number} بالإنجليزي',
            'label_en': f'Course {course_number} Name (English)',
            'type': 'text',
            'required': False,
            'direction': 'ltr',
            'placeholder_ar': 'مثال: Introduction to Programming',
            'placeholder_en': 'Example: Introduction to Programming',
            'category': 'courses',
            'course_number': course_number
        },
        f'course_{course_number}_percentage': {
            'label_ar': f'النسبة المئوية للمقرر {course_number}',
            'label_en': f'Course {course_number} Percentage',
            'type': 'text',
            'required': False,
            'direction': 'ltr',
            'placeholder_ar': 'مثال: 95%',
            'placeholder_en': 'Example: 95%',
            'category': 'courses',
            'course_number': course_number
        },
        f'course_{course_number}_grade': {
            'label_ar': f'الدرجة للمقرر {course_number}',
            'label_en': f'Course {course_number} Grade',
            'type': 'text',
            'required': False,
            'direction': 'ltr',
            'placeholder_ar': 'مثال: A+',
            'placeholder_en': 'Example: A+',
            'category': 'courses',
            'course_number': course_number
        },
        f'course_{course_number}_credit_hours': {
            'label_ar': f'ساعات المقرر {course_number}',
            'label_en': f'Course {course_number} Credit Hours',
            'type': 'text',
            'required': False,
            'direction': 'ltr',
            'placeholder_ar': 'مثال: 3',
            'placeholder_en': 'Example: 3',
            'category': 'courses',
            'course_number': course_number
        },
    }


def _build_transcript_fields():
    """Build complete TRANSCRIPT_FIELDS dictionary with all base and course fields"""
    fields = dict(TRANSCRIPT_BASE_FIELDS)
    
    # Add course fields for courses 1 to MAX_COURSES
    for i in range(1, MAX_COURSES + 1):
        fields.update(_generate_course_fields(i))
    
    return fields


# Complete transcript fields dictionary
TRANSCRIPT_FIELDS = _build_transcript_fields()


# Transcript type choices (same as certificate types)
TRANSCRIPT_TYPE_CHOICES = [
    ('arabic', 'عربي'),
    ('english', 'إنجليزي'),
    ('bilingual', 'ثنائي اللغة (عربي + إنجليزي)')
]


# Default field settings for transcript
DEFAULT_TRANSCRIPT_FIELD_SETTINGS = {
    'x': 15.0,
    'y': 10.0,
    'font_size': 12,
    'font_name': 'IBM_Plex_Sans_Arabic_Regular',
    'font_color': '#000000',
    'text_direction': 'rtl',
    'text_anchor': 'left',
    'enabled': True
}


# Default QR settings for transcript
DEFAULT_TRANSCRIPT_QR_SETTINGS = {
    'x': 6.9,
    'y': 1.2,
    'size': 4.0,
    'rotation_angle': 0
}


# Field categories for UI organization
TRANSCRIPT_FIELD_CATEGORIES = {
    'student_info': {
        'label_ar': 'معلومات الطالب',
        'label_en': 'Student Information',
        'order': 1
    },
    'program_info': {
        'label_ar': 'معلومات البرنامج',
        'label_en': 'Program Information',
        'order': 2
    },
    'courses': {
        'label_ar': 'المقررات',
        'label_en': 'Courses',
        'order': 3
    },
    'summary': {
        'label_ar': 'الملخص',
        'label_en': 'Summary',
        'order': 4
    }
}


def get_fields_by_category(category):
    """Get all fields belonging to a specific category"""
    return {
        key: value for key, value in TRANSCRIPT_FIELDS.items()
        if value.get('category') == category
    }


def get_course_fields_for_count(course_count):
    """Get course fields for a specific number of courses"""
    fields = {}
    for i in range(1, min(course_count + 1, MAX_COURSES + 1)):
        fields.update(_generate_course_fields(i))
    return fields


def get_base_fields():
    """Get only the base (non-course) fields"""
    return dict(TRANSCRIPT_BASE_FIELDS)
