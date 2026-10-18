from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

Usuario = get_user_model()

class CPFBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        cpf = username or kwargs.get('cpf')
        
        if not cpf:
            return None
            
        try:
            user = Usuario.objects.get(cpf=cpf)
        except Usuario.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
            
        return None