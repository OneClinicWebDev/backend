from rest_framework.exceptions import PermissionDenied

class ClinicaContextMixin:
    """
    Garante que as Views consigam recuperar a clínica injetada pelo TenantMiddleware.
    """
    def get_clinica(self):
        clinica = getattr(self.request, 'clinica', None)
        if not clinica:
            raise PermissionDenied("Contexto da clínica ausente ou inválido. Informe o X-Clinica-ID corretamente.")
        return clinica