"""API views for the core app."""

from django.contrib.auth import login
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import User
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    SsoSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """API endpoint for registering a user."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(generics.GenericAPIView):
    """API endpoint for logging in a user."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


class SsoView(generics.GenericAPIView):
    """Very small stub for social sign-on."""

    serializer_class = SsoSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key}, status=status.HTTP_200_OK)

