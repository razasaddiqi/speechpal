from django.contrib import admin

from .models import File, Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "image", "uploaded_at")


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("id", "file", "uploaded_at")
