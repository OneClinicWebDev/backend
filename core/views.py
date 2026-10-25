from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .models import Cliente, Colaborador, Servico, Agendamento
from .serializers import ClienteSerializer, ColaboradorSerializer, ServicoSerializer, AgendamentoSerializer

class BaseTenantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        clinica_id = request.headers.get("X-Clinica-ID")
        if clinica_id and not request.clinica:
            raise PermissionDenied("Você não tem permissão para acessar esta clínica.")

    def get_queryset(self):
        return self.queryset.filter(clinica=self.request.clinica)

    def perform_create(self, serializer):
        serializer.save(clinica=self.request.clinica)

class ClienteViewSet(BaseTenantViewSet):
    serializer_class = ClienteSerializer
    queryset = Cliente.objects.all()

class ColaboradorViewSet(BaseTenantViewSet):
    serializer_class = ColaboradorSerializer
    queryset = Colaborador.objects.all()

class ServicoViewSet(BaseTenantViewSet):
    serializer_class = ServicoSerializer
    queryset = Servico.objects.all()

class AgendamentoViewSet(BaseTenantViewSet):
    serializer_class = AgendamentoSerializer
    queryset = Agendamento.objects.all()