from __future__ import annotations

from pathlib import Path

from apps.core.config.env import get_runtime_settings

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME = get_runtime_settings()

SECRET_KEY = RUNTIME.secret_key
DEBUG = RUNTIME.debug
ALLOWED_HOSTS = list(RUNTIME.allowed_hosts)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "apps.core",
    "apps.identity",
    "apps.admin_portal",
    "apps.vendors",
    "apps.offerings",
    "apps.projects",
    "apps.imports",
    "apps.workflows",
    "apps.reports",
    "apps.help_center",
    "apps.contracts",
    "apps.demos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "apps.core.middleware.StructuredRequestLogMiddleware",
    "apps.core.error_handlers.UnifiedErrorMiddleware",
]

ROOT_URLCONF = "vendorcatalog_rebuild.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context.navigation_context",
            ],
        },
    }
]

WSGI_APPLICATION = "vendorcatalog_rebuild.wsgi.application"
ASGI_APPLICATION = "vendorcatalog_rebuild.asgi.application"

# Django requires a default DB setting, but runtime SQL adapters are managed separately.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "_django_control.db",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "loggers": {
        "vendorcatalog.rebuild": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        }
    },
}
