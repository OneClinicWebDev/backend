class ClinicaQuerySetMixin:
    def for_request(self, request):
        if not request.clinica:
            return self.none()

        return self.filter(clinica=request.clinica)