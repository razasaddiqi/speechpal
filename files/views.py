"""API views for the files app."""

from rest_framework import viewsets

from .models import File, Photo
from .serializers import FileSerializer, PhotoSerializer


class PhotoViewSet(viewsets.ModelViewSet):
    """CRUD operations for :class:`Photo`."""

    queryset = Photo.objects.all()
    serializer_class = PhotoSerializer


class FileViewSet(viewsets.ModelViewSet):
    """CRUD operations for :class:`File`."""

    queryset = File.objects.all()
    serializer_class = FileSerializer

