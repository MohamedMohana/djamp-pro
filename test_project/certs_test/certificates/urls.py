from django.urls import path, re_path
from . import views
from . import views_template
from . import views_role
from . import views_advanced_template
from . import views_advanced
from . import views_transcript_template
from . import views_transcript
from blockchain_certificates import views as admin_view
from django.conf import settings
from django.conf.urls.static import static
from .api import generate_certificate_api, generate_hash_api, generate_kkux_api, block_listed_api
from django.views.static import serve

urlpatterns = [
    #Main
    path('', views.welcome, name='welcome'),  # Set welcome page as root URL

    # Authentication
    path('login/', admin_view.cas_login, {'page_type': 'default'}, name='default_login'),
    path('logout/', admin_view.cas_logout, name='logout'),

    # Certificate management
    path('index/', views.index, name='index'),
    path('create/', views.create_certificate, name='create_certificate'),
    path('manage/', views.manage_certificates, name='manage_certificates'),
    path('verify/', views.verify_certificate, name='verify_certificate'),
    path('validate/', views.validate, name='validate'),
    path('success_redirect/', views.success_redirect, name='success_redirect'),
    path('download-certificate/<str:certificate_hash>/', views.download_certificate, name='download_certificate'),

    # Home for Nafath
    path('home/', views.home, name='home'),

    # Template management
    path('template/', views_template.template_list, name='template_list'),
    path('template/create/', views_template.template_create, name='template_create'),
    path('template/edit/<int:template_id>/', views_template.template_edit, name='template_edit'),
    path('template/delete/<int:template_id>/', views_template.template_delete, name='template_delete'),
    path('template/preview/', views_template.template_preview, name='template_preview'),
    path('template/preview_pdf/', views_template.preview_pdf, name='preview_pdf'),

    # Role management
    path('roles/', views_role.role_list, name='role_list'),
    path('roles/create/', views_role.role_create, name='role_create'),
    path('roles/edit/<int:pk>/', views_role.role_edit, name='role_edit'),
    path('roles/delete/<int:pk>/', views_role.role_delete, name='role_delete'),

    # User management
    path('users/', views_role.user_list, name='user_list'),
    path('users/create/', views_role.user_create, name='user_create'),
    path('users/edit/<int:pk>/', views_role.user_edit, name='user_edit'),
    path('users/delete/<int:pk>/', views_role.user_delete, name='user_delete'),

    #API
    path('api/generate_certificate/', generate_certificate_api), # generate cert api
    path('api/generate_hash/', generate_hash_api),  # generate hash api
    path('api/generate_kkux/', generate_kkux_api),  # generate kkux api
    path('api/block-listed/', block_listed_api),

    path('sysdashboard/', views_role.superadmin_dashboard, name='superadmin_dashboard'),

    # Advanced Templates (KKUx)
    path('advanced/templates/', views_advanced_template.template_list, name='advanced_template_list'),
    path('advanced/templates/create/', views_advanced_template.template_create, name='advanced_template_create'),
    path('advanced/templates/edit/<int:template_id>/', views_advanced_template.template_edit, name='advanced_template_edit'),
    path('advanced/templates/delete/<int:template_id>/', views_advanced_template.template_delete, name='advanced_template_delete'),
    path('advanced/templates/preview/', views_advanced_template.template_preview, name='advanced_template_preview'),
    path('advanced/templates/preview_pdf/', views_advanced_template.preview_pdf, name='advanced_preview_pdf'),
    
    # Advanced Certificates (KKUx)
    path('advanced/certificates/create/', views_advanced.create_certificate, name='advanced_create_certificate'),
    path('advanced/certificates/manage/', views_advanced.manage_certificates, name='advanced_manage_certificates'),
    path('advanced/certificates/download/<str:certificate_hash>/', views_advanced.download_certificate, name='advanced_download_certificate'),
    path('advanced/certificates/success_redirect/', views_advanced.success_redirect, name='advanced_success_redirect'),

    # Transcript Templates (سجل المقررات)
    path('transcript/templates/', views_transcript_template.template_list, name='transcript_template_list'),
    path('transcript/templates/create/', views_transcript_template.template_create, name='transcript_template_create'),
    path('transcript/templates/edit/<int:template_id>/', views_transcript_template.template_edit, name='transcript_template_edit'),
    path('transcript/templates/delete/<int:template_id>/', views_transcript_template.template_delete, name='transcript_template_delete'),
    path('transcript/templates/preview/', views_transcript_template.template_preview, name='transcript_template_preview'),
    path('transcript/templates/preview_pdf/', views_transcript_template.preview_pdf, name='transcript_preview_pdf'),
    
    # Transcripts (سجل المقررات)
    path('transcript/create/', views_transcript.create_transcript, name='transcript_create'),
    path('transcript/manage/', views_transcript.manage_transcripts, name='transcript_manage'),
    path('transcript/download/<str:certificate_hash>/', views_transcript.download_transcript, name='transcript_download'),
    path('transcript/success/', views_transcript.success_redirect, name='transcript_success'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]






# from django.urls import path, re_path
# from . import views
# from blockchain_certificates import views as admin_view
# from django.conf import settings
# from django.conf.urls.static import static
# from .api import generate_certificate_api, generate_hash_api
# from django.views.static import serve

# urlpatterns = [

#     path('login/', admin_view.cas_login, {'page_type': 'default'}, name='default_login'),
#     path('logout/', admin_view.cas_logout, name='logout'),
#     path('welcome/', views.welcome, name='welcome'),
#     path('', views.index, name='index'),
#     path('create/', views.create_certificate, name='create_certificate'),
#     path('manage/', views.manage_certificates, name='manage_certificates'),
#     path('verify/', views.verify_certificate, name='verify_certificate'),
#     path('validate/', views.validate, name='validate'),
#     path('success_redirect/', views.success_redirect, name='success_redirect'),
#     path('download-certificate/<str:certificate_hash>/', views.download_certificate, name='download_certificate'),
#     path('api/generate_certificate/', generate_certificate_api),
#     path('api/generate_hash/', generate_hash_api),  # New API endpoint,
#     path('home/', views.home, name='home')
# ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# if not settings.DEBUG:
#     urlpatterns += [
#         re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
#         re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
#     ]




# from django.urls import path, re_path
# from . import views
# from . import views_template
# from . import views_role
# from django.conf import settings
# from django.conf.urls.static import static
# from .api import generate_certificate_api, generate_hash_api, block_listed_api
# from django.views.static import serve

# urlpatterns = [
#     path('', views.welcome, name='welcome'),  # Set welcome page as root URL
#     path('index/', views.index, name='index'),
#     path('create/', views.create_certificate, name='create_certificate'),
#     path('manage/', views.manage_certificates, name='manage_certificates'),
#     path('verify/', views.verify_certificate, name='verify_certificate'),
#     path('validate/', views.validate, name='validate'),
#     path('success_redirect/', views.success_redirect, name='success_redirect'),
#     path('download-certificate/<str:certificate_hash>/', views.download_certificate, name='download_certificate'),
#     path('api/generate_certificate/', generate_certificate_api), # generate cert api
#     path('api/generate_hash/', generate_hash_api),  # generate hash api
#     path('api/block-listed/', block_listed_api),
#     path('home/', views.home, name='home'),
    
#     # Template management
#     path('template/', views_template.template_list, name='template_list'),
#     path('template/create/', views_template.template_create, name='template_create'),
#     path('template/edit/<int:template_id>/', views_template.template_edit, name='template_edit'),
#     path('template/delete/<int:template_id>/', views_template.template_delete, name='template_delete'),
#     path('template/preview/', views_template.template_preview, name='template_preview'),
#     path('template/preview_pdf/', views_template.preview_pdf, name='preview_pdf'),

#     # Role management
#     path('roles/', views_role.role_list, name='role_list'),
#     path('roles/create/', views_role.role_create, name='role_create'),
#     path('roles/edit/<int:pk>/', views_role.role_edit, name='role_edit'),
#     path('roles/delete/<int:pk>/', views_role.role_delete, name='role_delete'),

#     # User management
#     path('users/', views_role.user_list, name='user_list'),
#     path('users/create/', views_role.user_create, name='user_create'),
#     path('users/edit/<int:pk>/', views_role.user_edit, name='user_edit'),
#     path('users/delete/<int:pk>/', views_role.user_delete, name='user_delete'),
# ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# if not settings.DEBUG:
#     urlpatterns += [
#         re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
#         re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
#     ]