"""
Django settings for config project - Cleaned for ChordShift
"""
from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-chordshift-dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'true').lower() in ('1', 'true', 'yes')

def split_env(key, default=""):
    return [h.strip() for h in os.getenv(key, default).split(",") if h.strip()]

ALLOWED_HOSTS = split_env('ALLOWED_HOSTS', '*')

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = split_env('CORS_ALLOWED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = split_env('CSRF_TRUSTED_ORIGINS', '')

if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    if not DEBUG:
        CORS_ALLOWED_ORIGINS.append("https://web-frontend-ms9q4iuj754ec266.sel3.cloudtype.app")

if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:5173",
        "https://web-frontend-ms9q4iuj754ec266.sel3.cloudtype.app",
        "https://port-0-backend-docker-ms9q4iuj754ec266.sel3.cloudtype.app",
    ]

CORS_ALLOW_CREDENTIALS = True

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'scores',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

_db_host = os.getenv('DB_HOST', '').strip()
_db_user = os.getenv('DB_USER', '').strip()
_db_password = os.getenv('DB_PASSWORD', '')
_db_name = os.getenv('DB_NAME', '').strip() or 'chordshift'
_db_port = os.getenv('DB_PORT', '').strip() or '5432'

if _db_host == 'dummy':
    _db_host = 'localhost'
    _db_user = 'dummy'
    _db_password = 'dummy'
    _db_name = 'dummy'
    _db_port = '5432'
elif not _db_host or not _db_user:
    raise ImproperlyConfigured(
        'PostgreSQL 설정이 필요합니다. .env 에 DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT 를 넣으세요. (CloudType 환경변수 확인)'
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _db_name,
        'USER': _db_user,
        'PASSWORD': _db_password,
        'HOST': _db_host,
        'PORT': _db_port,
        'CONN_MAX_AGE': 600,
        'OPTIONS': {},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY') or os.getenv('AWS_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.getenv('R2_BUCKET_NAME') or os.getenv('AWS_STORAGE_BUCKET_NAME') or 'chordshift'
R2_ENDPOINT_URL = os.getenv('R2_ENDPOINT_URL') or os.getenv('AWS_S3_ENDPOINT_URL')
R2_REGION = os.getenv('R2_REGION') or os.getenv('AWS_S3_REGION_NAME') or 'auto'
R2_CUSTOM_DOMAIN = os.getenv('R2_CUSTOM_DOMAIN', '').rstrip('/')

USE_R2 = bool(R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT_URL)

if USE_R2:
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
            'OPTIONS': {
                'access_key': R2_ACCESS_KEY_ID,
                'secret_key': R2_SECRET_ACCESS_KEY,
                'bucket_name': R2_BUCKET_NAME,
                'endpoint_url': R2_ENDPOINT_URL,
                'region_name': R2_REGION,
                'default_acl': None,
                'querystring_auth': True,
                'file_overwrite': True,
                'object_parameters': {
                    'CacheControl': 'max-age=86400',
                },
            },
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    if R2_CUSTOM_DOMAIN:
        STORAGES['default']['OPTIONS']['custom_domain'] = R2_CUSTOM_DOMAIN.replace('https://', '').replace('http://', '')
        STORAGES['default']['OPTIONS']['querystring_auth'] = False
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

MOBILE_IMAGE_MAX_WIDTH = 1080
MOBILE_IMAGE_MAX_HEIGHT = 1920
MOBILE_IMAGE_QUALITY = 85
