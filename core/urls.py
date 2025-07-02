"""URL configuration for the core app."""

from django.urls import path, include

from .views import LoginView, RegisterView, SsoView, GoogleLogin, AppleLogin


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path('auth/', include('social_django.urls', namespace='social')),
    path('google/<str:backend>/', GoogleLogin.as_view(), name='google_login'),
    path('apple/<str:backend>/',  AppleLogin.as_view(), name='apple_login'),
]

