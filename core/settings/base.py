import logging.config
import os
from datetime import timedelta
from pathlib import Path

import environ

from core.jazzmin_conf import *  # noqa

# Base settings
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
env.read_env(str(BASE_DIR / ".env"))

# Core settings
SECRET_KEY = env.str("SECRET_KEY")
DEBUG = env.bool("DEBUG")
ALLOWED_HOSTS = ["*"]
STAGE = env.str("STAGE", default="development")

# Application definition
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django_elasticsearch_dsl',
    'django_celery_beat',
    'django_celery_results',
    'debug_toolbar',
    "rest_framework",
    "drf_yasg",
    "corsheaders",
    "rosetta",
    # local
    "apps.bot",
    "apps.multiparser",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 10,
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True, # debug_toolbar ogohlantirishini tuzatadi
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"

# Database
DATABASES = {
    'default': {
        'ENGINE': env.str('DB_ENGINE'),
        'NAME': env.str('POSTGRES_DB'),
        'USER': env.str('POSTGRES_USER'),
        'PASSWORD': env.str('POSTGRES_PASSWORD'),
        'HOST': env.str('POSTGRES_HOST'),
        'PORT': env.str('POSTGRES_PORT'),
        'CONN_MAX_AGE': 0,  # Important for PgBouncer
        'OPTIONS': {
            'connect_timeout': 10,
            'client_encoding': 'UTF8',
        },
    }
}

# Internationalization
LANGUAGE_CODE = env.str("LANGUAGE_CODE", default="uz")
TIME_ZONE = env.str("TIME_ZONE", default="Asia/Tashkent")
USE_I18N = True
USE_TZ = True
USE_L10N = True

LANGUAGES = [
    ("uz", "Uzbek"),
    ("ru", "Russian"),
    ("en", "English"),
]

# Static and Media files
STATIC_URL = env.str("STATIC_URL", default="static/")
STATIC_ROOT = BASE_DIR / "static"
STATICFILES_DIRS = (BASE_DIR / "staticfiles",)

MEDIA_URL = env.str("MEDIA_URL", default="media/")
MEDIA_ROOT = BASE_DIR / "media"

# Cache configuration
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env.str("REDIS_URL"),
        "KEY_PREFIX": env.str("CACHE_KEY_PREFIX", default="kuku_bot"),
    }
}

# Redis settings
REDIS_HOST = env.str("REDIS_HOST")
REDIS_PORT = env.int("REDIS_PORT")
REDIS_DB = env.int("REDIS_DB")

# Celery settings
CELERY_BROKER_URL = env.str("REDIS_URL")
CELERY_RESULT_BACKEND = env.str("REDIS_URL")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = env.int("CELERY_MAX_TASKS_PER_CHILD", default=50)
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=600)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=540)
CELERY_TASK_DEFAULT_RETRY_DELAY = env.int("CELERY_RETRY_DELAY", default=30)
CELERY_BROKER_POOL_LIMIT = env.int("CELERY_BROKER_POOL_LIMIT", default=5)
CELERYD_PREFETCH_MULTIPLIER = env.int("CELERYD_PREFETCH_MULTIPLIER", default=1)
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = env.int("CELERY_RESULT_EXPIRES", default=604800)

# Logging configuration
LOGGING_CONFIG = None
LOGLEVEL = env.str("DJANGO_LOGLEVEL", default="info").upper()

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s [%(name)s:%(lineno)s] %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "loggers": {
        "": {
            "level": LOGLEVEL,
            "handlers": ["console"],
        },
    },
})

# Bot configuration
WEBHOOK_URL = env.str("WEBHOOK_URL")
CELERY_WEBHOOK = env.str("CELERY_WEBHOOK", default="False")
BOT_TOKEN = env.str("BOT_TOKEN")
FORCE_CHANNEL_USERNAME = env.str("FORCE_CHANNEL_USERNAME")

# Elasticsearch configuration
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": env.str("ES_URL"),
    },
}

ES_URL = env.str("ES_URL")
ES_INDEX = env.str("ES_INDEX")

# Tika configuration
TIKA_URL = env.str("TIKA_URL")
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True, # debug_toolbar ogohlantirishini tuzatadi
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]