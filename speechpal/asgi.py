"""
ASGI config for speechpal project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from chat.consumers import ChatConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'speechpal.settings')

django_app = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_app,
    'websocket': URLRouter([
        path('ws/chat/<uuid:session_id>/', ChatConsumer.as_asgi()),
    ]),
})
