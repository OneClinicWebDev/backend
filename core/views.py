from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Cliente, Colaborador, Servico, Agendamento
from .serializers import ClienteSerializer, ColaboradorSerializer, ServicoSerializer, AgendamentoSerializer

class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Magia do Multi-Tenant: O usuário SÓ vê clientes da clínica atual dele
        return Cliente.objects.filter(clinica=self.request.clinica)

    def perform_create(self, serializer):
        # Injeta a clínica automaticamente na hora de salvar
        serializer.save(clinica=self.request.clinica)

class ColaboradorViewSet(viewsets.ModelViewSet):
    serializer_class = ColaboradorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Colaborador.objects.filter(clinica=self.request.clinica)

class ServicoViewSet(viewsets.ModelViewSet):
    serializer_class = ServicoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Servico.objects.filter(clinica=self.request.clinica)

    def perform_create(self, serializer):
        serializer.save(clinica=self.request.clinica)

class AgendamentoViewSet(viewsets.ModelViewSet):
    serializer_class = AgendamentoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Agendamento.objects.filter(clinica=self.request.clinica)

    def perform_create(self, serializer):
        serializer.save(clinica=self.request.clinica)