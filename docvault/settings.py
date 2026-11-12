from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(BASE_DIR / "app.env")

env = environ.Env()

SECRET_KEY = env("SECRET_KEY", cast=str)
DEBUG = env("DEBUG", cast=bool)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps
    "user",
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

ROOT_URLCONF = 'docvault.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'docvault.wsgi.application'
ASGI_APPLICATION = "docvault.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", cast=str),
        "USER": env("POSTGRES_USER", cast=str),
        "PASSWORD": env("POSTGRES_PASSWORD", cast=str),
        "HOST": env("POSTGRES_HOST", cast=str),
        "PORT": env("POSTGRES_PORT", cast=str),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_ROOT = BASE_DIR / "static"
STATIC_URL = "/static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = "user.User"


AUTHENTICATION_CLASSES = [
    "rest_framework_simplejwt.authentication.JWTAuthentication",
    # "rest_framework.authentication.TokenAuthentication",  # Token auth (old)
    "rest_framework.authentication.SessionAuthentication",
]

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": AUTHENTICATION_CLASSES,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.PageNumberPagination",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Sanaap DMS API",
    "DESCRIPTION": "Document Management System",
    "VERSION": "1.0.0",
}

# JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Redis cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_REDIS_URL", cast=str),
    }
}

# Celery (Redis is the broker)
CELERY_BROKER_URL = env("CELERY_BROKER_URL", cast=str)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Django Channels (Redis is the channel layer)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("CHANNELS_REDIS_URL", cast=str)]},
    }
}

# MinIO
MINIO_ENDPOINT = env("MINIO_ENDPOINT", cast=str)
MINIO_EXTERNAL_ENDPOINT = env("MINIO_EXTERNAL_ENDPOINT", cast=str)
MINIO_EXTERNAL_ENDPOINT_USE_HTTPS = env("MINIO_EXTERNAL_ENDPOINT_USE_HTTPS", cast=bool)
MINIO_ACCESS_KEY = env("MINIO_ACCESS_KEY", cast=str)
MINIO_SECRET_KEY = env("MINIO_SECRET_KEY", cast=str)
MINIO_USE_HTTPS = env("MINIO_USE_HTTPS", cast=bool)
MINIO_URL_EXPIRY_HOURS = timedelta(hours=1)
MINIO_CONSISTENCY_CHECK_ON_START = env("MINIO_CONSISTENCY_CHECK_ON_START", cast=bool)
MINIO_APP_PRIVATE_BUCKET = env("MINIO_APP_PRIVATE_BUCKET", cast=str)
MINIO_PRIVATE_BUCKETS = [
    MINIO_APP_PRIVATE_BUCKET,
]
MINIO_PUBLIC_BUCKETS = []
MINIO_POLICY_HOOKS = []
# Creates bucket if missing, then save
MINIO_BUCKET_CHECK_ON_SAVE = env("MINIO_BUCKET_CHECK_ON_SAVE", cast=bool)

# Uploads stay in memory (never written to disk) until they are sent to MinIO.
# The same 10 MB limit is set in nginx (client_max_body_size).
FILE_UPLOAD_HANDLERS = ["django.core.files.uploadhandler.MemoryFileUploadHandler"]
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024