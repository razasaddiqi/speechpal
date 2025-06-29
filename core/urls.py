"""URL configuration for the core app."""

from django.urls import path

from .views import LoginView, RegisterView, SsoView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("sso/", SsoView.as_view(), name="sso"),
]

