import os
from django.contrib import admin
from .models import Certificate
from .models_advanced import AdvancedCertificate
from .models_transcript import Transcript
from django.utils.html import format_html
from django.urls import reverse
from django.conf import settings
from urllib.parse import urljoin


class CertificateAdmin(admin.ModelAdmin):
    list_display = ('id', 'certificate_date', 'duration', 'name', 'course_name', 'certificate_hash', 'download_link', 'created_by', )
    list_display_links = ('id',)
    search_fields = ('name', 'course_name', 'hash_value')

    def certificate_date(self, obj):
        return obj.date.strftime('%Y-%m-%d')


    def download_link(self, obj):
        certificate_hash = obj.certificate_hash
        file_name = f'{certificate_hash}.pdf'
        download_url = urljoin(settings.MEDIA_URL, file_name)
        return format_html('<a href="{}" download>تحميل الشهادة</a>', download_url)


    certificate_date.short_description = 'Issue date'
    download_link.short_description = 'Download certificate'


admin.site.register(Certificate, CertificateAdmin)


class AdvancedCertificateAdmin(admin.ModelAdmin):
    readonly_fields = (
        'display_name',
        'course_name_display',
        'duration_display',
        'certificate_hash',
        'hash_value',
        'created_by',
        'date',
        'certificate_data_formatted'
    )
    fieldsets = (
        (None, {
            'fields': ('display_name', 'email', 'template', 'created_by', 'date')
        }),
        ('Certificate details', {
            'fields': ('course_name_display', 'duration_display', 'certificate_hash', 'hash_value')
        }),
        ('Raw data', {
            'classes': ('collapse',),
            'fields': ('certificate_data_formatted',)
        }),
    )
    list_display = (
        'id',
        'date',
        'display_name',
        'course_name_display',
        'duration_display',
        'email_display',
        'certificate_hash',
        'download_link',
        'created_by'
    )
    list_filter = ()
    search_fields = ('certificate_hash', 'email', 'certificate_data')
    ordering = ('-date',)

    def display_name(self, obj):
        return obj.get_display_name()
    display_name.short_description = 'Name'

    @staticmethod
    def _resolve_course_name(obj):
        return (
            obj.certificate_data.get('course_name') or
            obj.certificate_data.get('program_name_ar') or
            obj.certificate_data.get('program_name_en') or
            ''
        )

    @staticmethod
    def _resolve_duration(obj):
        return (
            obj.certificate_data.get('duration') or
            obj.certificate_data.get('duration_ar') or
            obj.certificate_data.get('duration_en') or
            ''
        )

    def course_name_display(self, obj):
        return self._resolve_course_name(obj)
    course_name_display.short_description = 'Course name'

    def duration_display(self, obj):
        return self._resolve_duration(obj)
    duration_display.short_description = 'Duration'

    def email_display(self, obj):
        return obj.email or ''
    email_display.short_description = 'Email'

    def download_link(self, obj):
        if not obj.certificate_hash:
            return ''
        url = reverse('advanced_download_certificate', args=[obj.certificate_hash])
        return format_html('<a href="{}" target="_blank">Download</a>', url)
    download_link.short_description = 'Download certificate'

    def certificate_data_formatted(self, obj):
        import json
        return json.dumps(obj.certificate_data, ensure_ascii=False, indent=2)
    certificate_data_formatted.short_description = 'Certificate data'


admin.site.register(AdvancedCertificate, AdvancedCertificateAdmin)


class TranscriptAdmin(admin.ModelAdmin):
    readonly_fields = (
        'display_name',
        'program_name_display',
        'gpa_display',
        'certificate_hash',
        'hash_value',
        'created_by',
        'date',
        'transcript_data_formatted'
    )
    fieldsets = (
        (None, {
            'fields': ('display_name', 'email', 'template', 'created_by', 'date')
        }),
        ('Transcript details', {
            'fields': ('program_name_display', 'gpa_display', 'certificate_hash', 'hash_value')
        }),
        ('Raw data', {
            'classes': ('collapse',),
            'fields': ('transcript_data_formatted',)
        }),
    )
    list_display = (
        'id',
        'date',
        'display_name',
        'program_name_display',
        'gpa_display',
        'email_display',
        'certificate_hash',
        'download_link',
        'created_by'
    )
    list_filter = ('template', 'date')
    search_fields = ('certificate_hash', 'email', 'transcript_data')
    ordering = ('-date',)

    def display_name(self, obj):
        return obj.get_display_name()
    display_name.short_description = 'Name'

    def program_name_display(self, obj):
        return obj.get_program_name()
    program_name_display.short_description = 'Program name'

    def gpa_display(self, obj):
        return obj.get_gpa()
    gpa_display.short_description = 'GPA'

    def email_display(self, obj):
        return obj.email or ''
    email_display.short_description = 'Email'

    def download_link(self, obj):
        if not obj.certificate_hash:
            return ''
        url = reverse('transcript_download', args=[obj.certificate_hash])
        return format_html('<a href="{}" target="_blank">Download</a>', url)
    download_link.short_description = 'Download transcript'

    def transcript_data_formatted(self, obj):
        import json
        return json.dumps(obj.transcript_data, ensure_ascii=False, indent=2)
    transcript_data_formatted.short_description = 'Transcript data'


admin.site.register(Transcript, TranscriptAdmin)

