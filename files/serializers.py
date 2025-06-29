"""Serializers for the files app."""

from rest_framework import serializers

from .models import File, Photo


class PhotoSerializer(serializers.ModelSerializer):
    """Serializer for the ``Photo`` model."""

    class Meta:
        model = Photo
        fields = ["id", "image", "uploaded_at"]


class FileSerializer(serializers.ModelSerializer):
    """Serializer for the ``File`` model."""

    class Meta:
        model = File
        fields = ["id", "file", "uploaded_at"]

