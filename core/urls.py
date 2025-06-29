"""URL configuration for the core app."""

from django.urls import path

from .views import LoginView, RegisterView, SsoView, GoogleLogin, AppleLogin


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path('google/', GoogleLogin.as_view(), name='google_login'),
    path('apple/',  AppleLogin.as_view(), name='apple_login'),
]

