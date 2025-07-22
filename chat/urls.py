from django.urls import path
from .views import ChatSessionCreateView, ChatSessionListView, ChatMessageListView

urlpatterns = [
    path('sessions/', ChatSessionListView.as_view(), name='chat-session-list'),
    path('sessions/create/', ChatSessionCreateView.as_view(), name='chat-session-create'),
    path('sessions/<uuid:session_id>/messages/', ChatMessageListView.as_view(), name='chat-messages'),
]
