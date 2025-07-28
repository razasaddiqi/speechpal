from django.urls import re_path
from chat import consumers as chat_consumers
from therapy import consumers as therapy_consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>\w+)/$', chat_consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/speech-analysis/$', therapy_consumers.SpeechAnalysisConsumer.as_asgi()),
] 