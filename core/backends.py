from django.contrib.auth.backends import ModelBackend

from .models import Usuario


class CPFBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        cpf = username or kwargs.get("cpf")

        if not cpf or not password:
            return None

        cpf = "".join(filter(str.isdigit, str(cpf)))

        try:
            user = Usuario.objects.get(cpf=cpf)
        except Usuario.DoesNotExist:
            return None

        if not self.user_can_authenticate(user):
            return None

        if not user.check_password(password):
            return None

        return user

    def get_user(self, user_id):
        try:
            user = Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None

        if not self.user_can_authenticate(user):
            return None

        return user