from rest_framework import permissions
from core.models import Role, Colaborador


class HasClinicaContext(permissions.BasePermission):
    """
    Valida se o contexto da clínica foi explicitamente informado e se o
    usuário autenticado possui um vínculo ativo com este estabelecimento.
    Atende à Seção 7 da especificação v1.1 (Contexto da Clínica e Isolamento).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        clinica_id = request.headers.get('X-Clinica-ID')
        if not clinica_id:
            return False

        return Colaborador.objects.filter(
            usuario=request.user,
            clinica_id=clinica_id,
            ativo=True
        ).exists()


class IsAdmin(HasClinicaContext):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
            
        clinica_id = request.headers.get('X-Clinica-ID')
        return Colaborador.objects.filter(
            usuario=request.user,
            clinica_id=clinica_id,
            ativo=True,
            role__nome=Role.ADMIN
        ).exists()


class IsSecretario(HasClinicaContext):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
            
        clinica_id = request.headers.get('X-Clinica-ID')
        return Colaborador.objects.filter(
            usuario=request.user,
            clinica_id=clinica_id,
            ativo=True,
            role__nome=Role.SECRETARIO
        ).exists()


class IsAdminOrSecretario(HasClinicaContext):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
            
        clinica_id = request.headers.get('X-Clinica-ID')
        return Colaborador.objects.filter(
            usuario=request.user,
            clinica_id=clinica_id,
            ativo=True,
            role__nome__in=[Role.ADMIN, Role.SECRETARIO]
        ).exists()


class IsProfissional(HasClinicaContext):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
            
        clinica_id = request.headers.get('X-Clinica-ID')
        return Colaborador.objects.filter(
            usuario=request.user,
            clinica_id=clinica_id,
            ativo=True,
            role__nome=Role.PROFISSIONAL
        ).exists()