from rest_framework import permissions
from core.models import Role, Colaborador


class HasClinicaContext(permissions.BasePermission):
    """
    Valida a autenticação, o cabeçalho X-Clinica-ID e o vínculo ativo.
    Disponibiliza a clínica e o colaborador autenticados para as views.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        clinica_id = request.headers.get("X-Clinica-ID")
        if not clinica_id:
            return False

        try:
            colaborador = Colaborador.objects.select_related(
                "role",
                "clinica",
            ).get(
                usuario=request.user,
                clinica_id=clinica_id,
                ativo=True,
            )

        except Colaborador.DoesNotExist:
            return False
        except (TypeError, ValueError):
            return False

        request.clinica = colaborador.clinica
        request.colaborador = colaborador
        request.role = colaborador.role.nome

        return True


class IsAdmin(HasClinicaContext):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.colaborador.role.nome == Role.ADMIN
        )


class IsSecretario(HasClinicaContext):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.colaborador.role.nome == Role.SECRETARIO
        )


class IsAdminOrSecretario(HasClinicaContext):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.colaborador.role.nome
            in [Role.ADMIN, Role.SECRETARIO]
        )


class IsProfissional(HasClinicaContext):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.colaborador.role.nome == Role.PROFISSIONAL
        )
