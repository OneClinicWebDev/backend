from core.models import Colaborador


class ClinicaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.clinica = None
        request.role = None
        request.colaborador = None

        clinica_id = (
            request.headers.get("X-Clinica-ID")
            or request.GET.get("clinica_id")
            or (request.POST.get("clinica_id") if hasattr(request, "POST") else None)
        )

        if clinica_id and request.user and request.user.is_authenticated:
            try:
                colaborador = Colaborador.objects.select_related("role", "clinica").get(
                    usuario=request.user,
                    clinica_id=clinica_id,
                    ativo=True,
                    clinica__ativo=True
                )
                request.clinica = colaborador.clinica
                request.colaborador = colaborador
                request.role = colaborador.role.nome
            except Colaborador.DoesNotExist:
                pass

        response = self.get_response(request)
        return response