class ClinicaQuerySet(models.QuerySet):
    def for_request(self, request):
        if not request.clinica:
            return self.none()

        return self.filter(clinica=request.clinica)


class ClinicaManager(models.Manager):
    def get_queryset(self):
        return ClinicaQuerySet(self.model, using=self._db)

    def for_request(self, request):
        return self.get_queryset().for_request(request)