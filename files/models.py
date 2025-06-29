from django.db import models


class Photo(models.Model):
    """Stores uploaded images."""
    image = models.ImageField(upload_to="photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return f"Photo {self.id}"


class File(models.Model):
    """Stores general uploaded files."""
    file = models.FileField(upload_to="files/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return f"File {self.id}"

