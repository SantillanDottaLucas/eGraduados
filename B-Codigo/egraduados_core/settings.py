"""
Django settings for egraduados_core project.

La configuración sensible se toma de variables de entorno. En
desarrollo se mantienen valores por defecto seguros para poder
levantar el proyecto sin configuración adicional; en producción
(DJANGO_DEBUG=0) el secreto y los hosts son obligatorios.

Si existe un archivo .env junto a manage.py se carga con
python-dotenv. Las variables definidas en el entorno del proceso
(systemd, Docker, consola) tienen prioridad sobre el archivo.
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ==================================================
# VARIABLES DE ENTORNO
# ==================================================

# Los tests no deben leer un .env de producción que pudiera
# redirigir la suite a otra base de datos. DJANGO_READ_DOTENV=0
# permite desactivar la carga explícitamente.
if (
    os.environ.get("DJANGO_READ_DOTENV", "1") != "0"
    and "test" not in sys.argv
):
    ruta_env = BASE_DIR / ".env"

    if ruta_env.is_file():
        load_dotenv(ruta_env, override=False)

def env_bool(nombre, por_defecto=False):
    valor = os.environ.get(nombre)

    if valor is None:
        return por_defecto

    return valor.strip().lower() in ("1", "true", "yes", "si", "sí", "on")


def env_list(nombre, por_defecto=""):
    valor = os.environ.get(nombre, por_defecto)

    return [item.strip() for item in valor.split(",") if item.strip()]


def env_int(nombre, por_defecto):
    valor = os.environ.get(nombre)

    if valor is None or not str(valor).strip():
        return por_defecto

    try:
        return int(valor)
    except (TypeError, ValueError) as error:
        raise ImproperlyConfigured(
            f"La variable {nombre} debe ser un número entero."
        ) from error


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DJANGO_DEBUG", True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = (
            "django-insecure-solo-desarrollo-"
            "8k&j#d%7r9d!($d))rcv)4u$rpxf"
        )
    else:
        raise ImproperlyConfigured(
            "Definí DJANGO_SECRET_KEY antes de ejecutar en producción."
        )

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost,[::1]",
)

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# El admin de Django queda deshabilitado salvo que se habilite
# explícitamente (o estemos en desarrollo).
HABILITAR_ADMIN = env_bool("DJANGO_HABILITAR_ADMIN", DEBUG)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'academico',
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

ROOT_URLCONF = 'egraduados_core.urls'

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
                'academico.contextos.usuario_actual',
            ],
        },
    },
]

WSGI_APPLICATION = 'egraduados_core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.environ.get(
            "DJANGO_DB_ENGINE",
            "django.db.backends.mysql",
        ),
        'NAME': os.environ.get("DJANGO_DB_NAME", "egraduados"),
        'USER': os.environ.get("DJANGO_DB_USER", "root"),
        'PASSWORD': os.environ.get("DJANGO_DB_PASSWORD", ""),
        'HOST': os.environ.get("DJANGO_DB_HOST", "127.0.0.1"),
        'PORT': os.environ.get("DJANGO_DB_PORT", "3306"),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# SQLite no acepta el parámetro «charset» de MySQL.
if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    DATABASES['default']['OPTIONS'] = {}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'es-ar'

TIME_ZONE = 'America/Argentina/Rio_Gallegos'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

# En desarrollo los correos se imprimen en consola; en producción
# se usa SMTP. Django 6.1 configura los mailers desde MAILERS (los
# settings EMAIL_* quedaron deprecados y no pueden convivir con él).
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
CONSOLA_BACKEND = "django.core.mail.backends.console.EmailBackend"

_backend = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    CONSOLA_BACKEND if DEBUG else SMTP_BACKEND,
)

_opciones_smtp = {
    "host": os.environ.get("DJANGO_EMAIL_HOST", "localhost"),
    "port": env_int("DJANGO_EMAIL_PORT", 25),
    "username": os.environ.get("DJANGO_EMAIL_HOST_USER", ""),
    "password": os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", ""),
    "use_tls": env_bool("DJANGO_EMAIL_USE_TLS", False),
    "use_ssl": env_bool("DJANGO_EMAIL_USE_SSL", False),
}

MAILERS = {
    'default': {
        'BACKEND': _backend,
    },
}

if _backend == SMTP_BACKEND:
    MAILERS['default']['OPTIONS'] = _opciones_smtp

DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL",
    "egraduados@unpa.edu.ar",
)


# ==================================================
# SESIONES Y SEGURIDAD
# ==================================================

# La sesión se renueva al iniciar y expira por inactividad.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int(
    "DJANGO_SESSION_COOKIE_AGE",
    60 * 60 * 8,
)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Límites de ingreso y de archivos.
LOGIN_MAX_INTENTOS = env_int("DJANGO_LOGIN_MAX_INTENTOS", 5)
LOGIN_BLOQUEO_SEGUNDOS = env_int("DJANGO_LOGIN_BLOQUEO_SEGUNDOS", 300)
MAX_UPLOAD_SIZE = env_int(
    "DJANGO_MAX_UPLOAD_SIZE",
    10 * 1024 * 1024,
)

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int(
        "DJANGO_SECURE_HSTS_SECONDS",
        60 * 60 * 24 * 365,
    )
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ==================================================
# LOGGING
# ==================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "academico": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
