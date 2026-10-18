from rest_framework import viewsets
from core.models import Servico
from .base import ClinicaContextMixin
from .permissions import IsAdminOrSecretario
from .serializers_core import ServicoSerializer

class ServicoViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ServicoSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_queryset(self):
        return Servico.objects.filter(
            clinica=self.get_clinica()
        )

    def perform_create(self, serializer):
        serializer.save(clinica=self.get_clinica())