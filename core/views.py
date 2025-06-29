"""API views for the core app."""

from django.contrib.auth import login
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from social_django.utils import psa


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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        headers = self.get_success_headers(serializer.data)
        token, _ = Token.objects.get_or_create(user=user)
        data = {
            "token": token.key,
            "user": UserSerializer(user).data,
        }
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)


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
        data = {
            "token": token.key,
            "user": UserSerializer(user).data,
        }
        return Response(data)


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



class GoogleLogin(APIView):
    permission_classes = []                  # allow unauthenticated
    authentication_classes = []
    @method_decorator(psa('social:complete'))
    def post(self, request, backend):
        """
        Expects JSON: { "access_token": "<GOOGLE_OAUTH2_TOKEN>" }
        """
        token = request.data.get('access_token')
        if not token:
            return Response({'detail':'access_token required'}, status=status.HTTP_400_BAD_REQUEST)

        # do_auth will run your pipeline (including save_profile_photo)
        user = request.backend.do_auth(token)
        if not user or not user.is_active:
            return Response({'detail':'Authentication failed'}, status=status.HTTP_400_BAD_REQUEST)

        # get or create DRF token
        drf_token, _ = Token.objects.get_or_create(user=user)
        data = {
            'token': drf_token.key,
            'user': UserSerializer(user).data
        }
        return Response(data, status=status.HTTP_200_OK)


class AppleLogin(APIView):
    permission_classes = []
    authentication_classes = []
    @method_decorator(psa('social:complete'))
    def post(self, request, backend):
        """
        Expects JSON: { "id_token": "<APPLE_ID_TOKEN>" }
        """
        id_token = request.data.get('id_token')
        if not id_token:
            return Response({'detail':'id_token required'}, status=status.HTTP_400_BAD_REQUEST)

        # pass id_token into do_auth
        user = request.backend.do_auth(access_token=None, id_token=id_token)
        if not user or not user.is_active:
            return Response({'detail':'Authentication failed'}, status=status.HTTP_400_BAD_REQUEST)

        drf_token, _ = Token.objects.get_or_create(user=user)
        data = {
            'token': drf_token.key,
            'user': UserSerializer(user).data
        }
        return Response(data, status=status.HTTP_200_OK)