from core.models import Colaborador


class ClinicaMiddleware:
    """
    Injeta a clínica ativa no request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request.clinica = None

        if request.user.is_authenticated:
            colaborador = Colaborador.objects.filter(
                usuario=request.user,
                ativo=True
            ).first()

            if colaborador:
                request.clinica = colaborador.clinica

        response = self.get_response(request)
        return response