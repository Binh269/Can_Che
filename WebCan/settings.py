import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-web-can-quan-ly-can-2024-secret-key-change-in-production'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'can',
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

ROOT_URLCONF = 'WebCan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'WebCan.wsgi.application'
ASGI_APPLICATION = 'WebCan.asgi.application'

# Kenh WebSocket (dung InMemoryChannelLayer cho dev)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

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

LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (anh ban ghi can)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Thu muc anh lich su theo ngay: data/img/<ngay>/...
DATA_IMG_URL = '/data-img/'
DATA_IMG_ROOT = BASE_DIR / 'data' / 'img'

# Cau hinh MQTT cho luong nhan du lieu can
MQTT_BROKER_URL = os.environ.get('MQTT_BROKER_URL', 'mqtt://10.6.5.232:1883')
MQTT_TOPIC_PATTERN = os.environ.get('MQTT_TOPIC_PATTERN', 'can/camera/image')
MQTT_ACK_TOPIC = os.environ.get('MQTT_ACK_TOPIC', f'{MQTT_TOPIC_PATTERN}/ack')
MQTT_CLIENT_ID = os.environ.get('MQTT_CLIENT_ID', 'web_can_server')
MQTT_USERNAME = os.environ.get('MQTT_USERNAME', '')
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', '')
MQTT_KEEPALIVE = int(os.environ.get('MQTT_KEEPALIVE', '60'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session: luu dang nhap 1 ngay
SESSION_COOKIE_AGE = 86400
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Redirect ve trang dang nhap neu chua xac thuc
LOGIN_URL = '/dang-nhap/'
