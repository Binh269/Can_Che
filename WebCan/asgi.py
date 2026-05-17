import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from can import consumers

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WebCan.settings')

application = ProtocolTypeRouter({
    # Xu ly HTTP binh thuong
    'http': get_asgi_application(),
    # Xu ly WebSocket cho WebRTC signaling
    'websocket': AuthMiddlewareStack(
        URLRouter([
            path('ws/tin-hieu/<str:camera_id>/', consumers.SignalingConsumer.as_asgi()),
        ])
    ),
})
