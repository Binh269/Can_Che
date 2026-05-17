import os
from django.apps import AppConfig


class CanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'can'
    verbose_name = 'Quan ly can'

    def ready(self):
        # Chi khoi dong luong khi server chay that (tranh chay 2 lan luc debug)
        # RUN_MAIN=true duoc set boi Django dev server o process chinh
        if os.environ.get('RUN_MAIN') == 'true':
            from .luong_api import khoi_dong_luong_mqtt
            khoi_dong_luong_mqtt()
