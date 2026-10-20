from rest_framework import permissions

from core.models import Role, Colaborador


class HasClinicaContext(permissions.BasePermission):
    """
    Valida a autenticação, a clínica selecionada e o vínculo ativo.
    Disponibiliza a clínica e o colaborador autenticados para as views.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not user.is_active:
            return False

        clinica_id = request.headers.get("X-Clinica-ID")

        if not clinica_id:
            return False

        try:
            colaborador = (
                Colaborador.objects.select_related(
                    "role",
                    "clinica",
                    "usuario",
                )
                .get(
                    usuario=user,
                    usuario__is_active=True,
                    clinica_id=clinica_id,
                    clinica__ativo=True,
                    ativo=True,
                )
            )
        except (
            Colaborador.DoesNotExist,
            TypeError,
            ValueError,
        ):
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
