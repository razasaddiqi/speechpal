import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "speechpal.settings")

from django.core.asgi import get_asgi_application
django_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from chat.consumers import ChatConsumer
from therapy import consumers as therapy_consumers

application = ProtocolTypeRouter({
    "http": django_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter([
          path("ws/chat/<uuid:session_id>/", ChatConsumer.as_asgi()),
          path("ws/speech-analysis/", therapy_consumers.SpeechAnalysisConsumer.as_asgi()),
          path('ws/xp-updates/', therapy_consumers.XPUpdateConsumer.as_asgi()),
        ]))
    ),
})
