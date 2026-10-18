from rest_framework import viewsets


class ClinicaContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        if hasattr(self.request, "clinica") and self.request.clinica:
            context["clinica"] = self.request.clinica
        return context


class TenantModelViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(queryset, "for_request"):
            return queryset.for_request(self.request)
        
        if hasattr(self.request, "clinica") and self.request.clinica:
            if hasattr(queryset.model, "clinica"):
                return queryset.filter(clinica=self.request.clinica)
        
        return queryset.none()

    def perform_create(self, serializer):
        if hasattr(self.request, "clinica") and self.request.clinica:
            if "clinica" in serializer.fields:
                serializer.save(clinica=self.request.clinica)
            else:
                serializer.save()
        else:
            serializer.save()