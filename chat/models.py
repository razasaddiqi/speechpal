from django.db import models
from django.conf import settings
import uuid


class ChatSession(models.Model):
    """Session for grouping chat messages."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    created_at = models.DateTimeField(auto_now_add=True)


class ChatMessage(models.Model):
    """Single chat message belonging to a session."""

    ROLE_CHOICES = (
        ("user", "User"),
        ("assistant", "Assistant"),
    )

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

