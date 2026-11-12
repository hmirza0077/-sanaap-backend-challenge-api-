from django.contrib.auth import models as auth_models
from common.models import SoftDeleteManager, SoftDeleteModel


class UserManager(SoftDeleteManager, auth_models.UserManager):
    """Django's UserManager (create_user, ...) without deleted users, so they cannot log in."""