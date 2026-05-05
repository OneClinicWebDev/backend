from django.contrib.auth.backends import BaseBackend
from .models import Usuario


class CPFBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        cpf = username or kwargs.get("cpf")

        if cpf is None or password is None:
            return None

        try:
            user = Usuario.objects.get(cpf=cpf)
        except Usuario.DoesNotExist:
            return None

        if user.check_password(password) and user.is_active:
            return user

        return None

    def get_user(self, user_id):
        try:
            user = Usuario.objects.get(pk=user_id)
            return user if user.is_active else None
        except Usuario.DoesNotExist:
            return None