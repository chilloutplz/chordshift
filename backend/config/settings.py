"""
Django settings for config project.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = 'django-insecure-chordshift-dev-key-change-in-production'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    # Local
    'scores',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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

# --- Cloudflare R2 (정식 저장) / 로컬 (tmp) ---
# .env 에 R2_* 가 있으면 ImageField 기본 저장소를 R2 로 사용
# media/tmp 는 계속 로컬 MEDIA_ROOT 사용 (temp_store.py)
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
                'default_acl': None,  # R2 ACL 미사용
                'querystring_auth': True,  # 비공개 버킷이면 서명 URL
                'file_overwrite': False,
                'object_parameters': {
                    'CacheControl': 'max-age=86400',
                },
            },
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    # 브라우저에서 바로 열 공개 URL이 있으면 사용
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

# CORS (Vue frontend)
CORS_ALLOW_ALL_ORIGINS = True  # 개발용. 운영시 제한 필요

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# Image processing settings
MOBILE_IMAGE_MAX_WIDTH = 1080
MOBILE_IMAGE_MAX_HEIGHT = 1920
MOBILE_IMAGE_QUALITY = 85
