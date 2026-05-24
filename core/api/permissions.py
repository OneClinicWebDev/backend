from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.role == "ADMIN"


class IsSecretario(BasePermission):
    def has_permission(self, request, view):
        return request.role == "SECRETARIO"


class IsProfissional(BasePermission):
    def has_permission(self, request, view):
        return request.role == "PROFISSIONAL"