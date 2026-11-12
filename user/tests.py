from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from user.models import User


# --- JWT auth tests (current) ---
class LoginTests(APITestCase):
    def setUp(self):
        User.objects.create_user(username="ali", password="pass12345")

    def login(self, password="pass12345"):
        return self.client.post(reverse("login"), {"username": "ali", "password": password})

    def test_login_returns_access_and_refresh(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_fails(self):
        response = self.login(password="wrong")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_works_in_header(self):
        access = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "ali")

    def test_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access(self):
        refresh = self.login().data["refresh"]
        response = self.client.post(reverse("token-refresh"), {"refresh": refresh})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)


class UserManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass12345", role=User.Role.ADMIN)
        self.editor = User.objects.create_user(username="editor", password="pass12345", role=User.Role.EDITOR)
        self.url = reverse("user-list")

    def test_admin_can_create_user_with_role(self):
        self.client.force_authenticate(self.admin)
        data = {"username": "new", "password": "pass12345", "role": "editor"}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="new")
        self.assertEqual(user.role, User.Role.EDITOR)
        self.assertTrue(user.check_password("pass12345"))

    def test_admin_can_change_role(self):
        self.client.force_authenticate(self.admin)
        url = reverse("user-detail", args=[self.editor.id])
        response = self.client.patch(url, {"role": "viewer"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.editor.refresh_from_db()
        self.assertEqual(self.editor.role, User.Role.VIEWER)

    def test_non_admin_cannot_manage_users(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_manage_users(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get(reverse("me"))
        self.assertEqual(response.data["username"], "editor")
        self.assertEqual(response.data["role"], "editor")
