from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")  # also /users/me/

urlpatterns = [
    path("login/", TokenObtainPairView.as_view(), name="login"),  # username + password -> access + refresh
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),  # refresh -> new access
] + router.urls
