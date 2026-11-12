from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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
    destroy=extend_schema(
        summary="Delete User",
        description="Admin only: soft delete. The user is kept in the database but can no longer log in",
    ),
    me=extend_schema(
        summary="Current User",
        description="Retrieve the logged-in user",
    ),
)
class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(self.get_serializer(request.user).data)
