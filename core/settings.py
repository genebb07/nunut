"""
Configuración de Django para el proyecto core.

Generado por 'django-admin startproject' usando Django 5.2.7.
"""

from pathlib import Path

# Construye rutas dentro del proyecto como esta: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Configuraciones de inicio rápido - no aptas para producción
# Ver https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# ADVERTENCIA DE SEGURIDAD: ¡mantén secreta la clave secreta usada en producción!
SECRET_KEY = 'django-insecure-7+efgjx_)0xn@@=owj-oks_obhrw#@trtux!f%cns86fc&he5='

# ADVERTENCIA DE SEGURIDAD: ¡no ejecutes con debug activado en producción!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Definición de la aplicación

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'base',

    # Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.apple',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ROOT_URLCONF = 'core.urls'

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
                'base.context_processors.racha_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Base de datos
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Validación de contraseñas
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


# Internacionalización
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'es-es'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Archivos estáticos (CSS, JavaScript, Imágenes)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Tipo de campo de clave primaria por defecto
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuración de Login
LOGIN_URL = 'base:iniciar_sesion'
LOGIN_REDIRECT_URL = 'base:index'
ACCOUNT_LOGOUT_REDIRECT_URL = 'base:bienvenida'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_ADAPTER = 'allauth.socialaccount.adapter.DefaultSocialAccountAdapter'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'FIELDS': ['id', 'email', 'name', 'first_name', 'last_name', 'verified', 'locale', 'timezone', 'link', 'gender', 'updated_time'],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': False,
        'VERSION': 'v13.0',
    }
}

# Configuración de Correo
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'ppyop.dope@gmail.com'  # <--- TU CORREO REAL
EMAIL_HOST_PASSWORD = 'tnoh hdyw stbh pjwo'  # <--- TU CONTRASEÑA DE APLICACIÓN
DEFAULT_FROM_EMAIL = 'Nunut <ppyop.dope@gmail.com>'

# Configuración de Cache (Memoria local para desarrollo)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

GEMINI_API_KEY = 'AIzaSyAHhg0VVxgIbGeOQmQO8zbNrUycYK6gAeY'
