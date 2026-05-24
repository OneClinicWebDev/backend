class ClinicaMixin:
    def get_queryset(self):
        qs = super().get_queryset()

        if hasattr(self.request, "clinica") and self.request.clinica:
            return qs.filter(clinica=self.request.clinica)

        return qs.none()