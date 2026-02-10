# =============================
# Django Settings for Certs Project
# =============================

from pathlib import Path
import os
import dotenv

dotenv.load_dotenv()

# =============================
# Base Directory
# =============================
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================
# Security Settings
# =============================
# SECRET_KEY: Keep this secret in production!
SECRET_KEY = 'django-insecure-p@0*g3z@)&u_*5a33#a-h)fjl41dl#m1874kftd1qz3zqiue2u'

# DEBUG: Never set to True in production
DEBUG = False

# Allowed hosts for this server
ALLOWED_HOSTS = [
    'certs.kku.edu.sa',
    'https://certs.kku.edu.sa/',
    'localhost:8000',
    '127.0.0.1:8000',
    'localhost'
]

# Trusted origins for CSRF protection
CSRF_TRUSTED_ORIGINS = [
    'https://certs.kku.edu.sa',
    'https://www.iam.gov.sa',
    'https://www.kku.edu.sa',
    'https://mysso.kku.edu.sa/cas/logout?service=https%3A//certs.kku.edu.sa/',
    'https://mysso.kku.edu.sa'
]

# =============================
# HTTPS & Cookie Security
# =============================
# Ensure cookies are only sent over HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
# Make session cookies inaccessible to JavaScript
SESSION_COOKIE_HTTPONLY = True
# Redirect all HTTP requests to HTTPS
# SECURE_SSL_REDIRECT = not DEBUG
# If behind a proxy/load balancer
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# =============================
# Session Management
# =============================
# Session expires after 30 minutes of inactivity
SESSION_COOKIE_AGE = 1800  # 30 minutes
# Session expires when browser closes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Reset session timer on every request
SESSION_SAVE_EVERY_REQUEST = True

# =============================
# Data Upload Limits
# =============================
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000  # Max form fields
DATA_UPLOAD_MAX_MEMORY_SIZE = 26214400  # 25 MB limit

# =============================
# Application Definition
# =============================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'certificates.apps.CertificatesConfig',  # Main app
    'widget_tweaks',
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'blockchain_certificates.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'blockchain_certificates.wsgi.application'

# =============================
# Database Configuration
# =============================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# =============================
# External Service URLs & Credentials
# =============================
URL_CAS_LOGIN = os.getenv('URL_CAS_LOGIN')
CAS_HOST = os.getenv('CAS_HOST')
CAS_PROTOCOL = os.getenv('CAS_PROTOCOL')
CAS_CONTEXT = os.getenv('CAS_CONTEXT')
MAIN_URL = os.getenv('MAIN_URL')

KKU_IAM_WS_URL = os.getenv('KKU_IAM_WS_URL')
KKU_SERVICES_USER= os.getenv('KKU_SERVICES_USER')
KKU_SERVICES_PASS= os.getenv('KKU_SERVICES_PASS')
KKU_SERVICES_USER_INFO_URL= os.getenv('KKU_SERVICES_USER_INFO_URL')
KKU_SERVICES_EMAIL_SEND_URL= os.getenv('KKU_SERVICES_EMAIL_SEND_URL')
KKU_SERVICES_EMAIL_SEND_URL_NO_ATTACHMENT= os.getenv('KKU_SERVICES_EMAIL_SEND_URL_NO_ATTACHMENT')
KKU_SERVICES_EMAIL_FROM= os.getenv('KKU_SERVICES_EMAIL_FROM')
BLOCK_LISTED_EXCEL_PATH = os.getenv('BLOCK_LISTED_EXCEL_PATH')

# =============================
# Password Validation
# =============================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================
# Localization
# =============================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Riyadh'
USE_I18N = True
USE_TZ = True
USE_L10N = True

# =============================
# Static & Media Files
# =============================
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / 'static']
else:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# =============================
# Django Model Defaults
# =============================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================
# Authentication Backends
# =============================
# Modes: 'cas', 'nafath', 'both', or 'local' (for development)
AUTH_MODE = os.getenv('AUTH_MODE', 'both')  # Default to both if not set

if AUTH_MODE == 'cas':
    AUTHENTICATION_BACKENDS = [
        'blockchain_certificates.auth_backends.api_backend.APIUserBackend',
        'blockchain_certificates.auth_backends.cas_backend.CASBackend',
    ]
elif AUTH_MODE == 'nafath':
    AUTHENTICATION_BACKENDS = [
        'blockchain_certificates.auth_backends.api_backend.APIUserBackend',
        'blockchain_certificates.auth_backends.nafath_backend.NafathBackend',
    ]
elif AUTH_MODE == 'both':
    AUTHENTICATION_BACKENDS = [
        'blockchain_certificates.auth_backends.api_backend.APIUserBackend',
        'blockchain_certificates.auth_backends.cas_backend.CASBackend',
        'blockchain_certificates.auth_backends.nafath_backend.NafathBackend',
    ]
else:  # local (for development)
    AUTHENTICATION_BACKENDS = [
        'blockchain_certificates.auth_backends.local_backend.LocalBackend',
    ]