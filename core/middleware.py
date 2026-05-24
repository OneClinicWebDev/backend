from core.models import Colaborador


class ClinicaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.clinica = None
        request.role = None

        if request.user.is_authenticated:
            colab = Colaborador.objects.filter(
                usuario=request.user,
                ativo=True
            ).select_related("role", "clinica").first()

            if colab:
                request.clinica = colab.clinica
                request.role = colab.role.nome

        return self.get_response(request)