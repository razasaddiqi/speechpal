from django.contrib.auth.models import AbstractUser
from django.db import models

from files.models import Photo


class User(AbstractUser):
    """Custom user model with optional profile photo."""

    photo = models.ForeignKey(
        Photo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

