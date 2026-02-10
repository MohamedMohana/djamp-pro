from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

handler404 = 'certificates.views.custom_404'

urlpatterns = [
    # Admin login/logout (CAS)
    path('admin/login/', views.cas_login, {'page_type': 'admin'}, name='admin_login'),
    path('admin/logout/', views.cas_logout, name='admin_logout'),
    path('admin/', admin.site.urls),

    # Default login/logout (CAS or local)
    path('login/', views.cas_login, {'page_type': 'default'}, name='default_login'),
    path('logout/', views.cas_logout, name='logout'),

    # Django's built-in login/logout (for local mode)
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Nafath/IAM login
    path('nafath_login/', views.create_iam_req, name='nafath_login'),
    path('iam_callback/', views.iam_callback, name='iam_callback'),

    # Main app URLs
    path('', include('certificates.urls')),
]
