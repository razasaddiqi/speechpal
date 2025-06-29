"""Serializers for the core app."""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the ``User`` model."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "photo"]


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer used for user registration."""

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "photo"]

    def validate_password(self, value: str) -> str:
        validate_password(value, self.instance)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        Token.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs.get("username"), password=attrs.get("password")
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        attrs["user"] = user
        return attrs


class SsoSerializer(serializers.Serializer):
    """Minimal serializer for SSO endpoints."""

    provider = serializers.ChoiceField(choices=["google", "apple"])
    email = serializers.EmailField()

