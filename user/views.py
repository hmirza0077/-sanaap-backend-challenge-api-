from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework.generics import RetrieveAPIView
from rest_framework.viewsets import ModelViewSet

from user.models import User
from user.permissions import IsAdminRole
from user.serializers import UserSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List Users",
        description="Admin only: retrieve a list of users",
    ),
    create=extend_schema(
        summary="Create User",
        description="Admin only: create a user and assign a role",
    ),
    partial_update=extend_schema(
        summary="Update User",
        description="Admin only: change the role or password of a user",
    ),
)
class UserViewSet(ModelViewSet):
    queryset = User.objects.order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]


@extend_schema(
    summary="Current User",
    description="Retrieve the logged-in user",
)
class MeView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
