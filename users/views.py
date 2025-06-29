from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from core.serializers import UserSerializer


class UserDetailView(generics.RetrieveAPIView):
    """Return details for the authenticated user."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
