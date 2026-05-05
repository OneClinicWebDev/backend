from django.contrib.auth.backends import ModelBackend
from .models import Usuario


class CPFBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        cpf = username or kwargs.get("cpf")

        if cpf is None or password is None:
            return None

        try:
            user = Usuario.objects.get(cpf=cpf)
        except Usuario.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

    def get_user(self, user_id):
        try:
            user = Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None

        return user if self.user_can_authenticate(user) else None