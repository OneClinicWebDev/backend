from django.core.exceptions import ValidationError
from django.http import JsonResponse

from core.models import Colaborador


class ClinicaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.clinica = None
        request.role = None
        request.colaborador = None

        clinica_id = request.headers.get("X-Clinica-ID")

        if clinica_id and request.user.is_authenticated:
            try:
                colaborador = (
                    Colaborador.objects.select_related(
                        "role",
                        "clinica",
                        "usuario",
                    )
                    .get(
                        usuario=request.user,
                        usuario__is_active=True,
                        clinica_id=clinica_id,
                        clinica__ativo=True,
                        ativo=True,
                    )
                )
            except (
                Colaborador.DoesNotExist,
                ValidationError,
                ValueError,
                TypeError,
            ):
                return JsonResponse(
                    {
                        "detail": (
                            "Você não tem permissão para acessar "
                            "esta clínica ou o contexto é inválido."
                        )
                    },
                    status=403,
                )

            request.clinica = colaborador.clinica
            request.colaborador = colaborador
            request.role = colaborador.role.nome

        return self.get_response(request)
