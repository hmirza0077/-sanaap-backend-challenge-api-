from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminRole(BasePermission):

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_role)


class DocumentPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return user.is_admin_role
        return user.is_admin_role or user.is_editor_role

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin_role or obj.uploaded_by_id == request.user.id
