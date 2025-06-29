"""URL configuration for the files app."""

from rest_framework.routers import DefaultRouter

from .views import FileViewSet, PhotoViewSet

router = DefaultRouter()
router.register(r"photos", PhotoViewSet)
router.register(r"files", FileViewSet)

urlpatterns = router.urls

