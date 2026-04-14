"""
Django settings for virtual_reviewer project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file (e.g. OPENROUTER_API_KEY)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DEBUG = True

# Comma-separated list of allowed hostnames, e.g.:
# ALLOWED_HOSTS=virtualreviewer.digi-teach.com,localhost
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# Django checks the Origin header on POST requests against this list.
# Must include every domain the site is served from (with scheme).
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:8000"
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reviewer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "virtual_reviewer.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
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

WSGI_APPLICATION = "virtual_reviewer.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Sessions are stored server-side; only a cookie with the session ID is sent to the browser.
SESSION_ENGINE = "django.contrib.sessions.backends.db"

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Destination directory for `collectstatic` (used in the Docker build)
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Maximum size for an uploaded file: 20 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
