from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.response import Response

from core.models import Cliente, Auditoria
from .base import ClinicaContextMixin
from .permissions import IsAdminOrSecretario
from .serializers_core import ClienteSerializer


class ClienteViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_queryset(self):
        return (
            Cliente.objects.filter(clinica=self.get_clinica())
            .select_related("usuario", "clinica")
        )

    def _snapshot(self, cliente):
        return {
            "usuario_id": str(cliente.usuario_id),
            "telefone": cliente.telefone,
            "cep": cliente.cep,
            "numero_endereco": cliente.numero_endereco,
            "status_cadastro": cliente.status_cadastro,
        }

    def _registrar_auditoria(
        self,
        cliente,
        acao,
        dados_anteriores=None,
        dados_novos=None,
    ):
        ip = self.request.META.get("REMOTE_ADDR")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        Auditoria.objects.create(
            usuario=self.request.user,
            clinica=cliente.clinica,
            acao=acao,
            entidade="Cliente",
            objeto_id=str(cliente.id),
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            origem="USUARIO",
            ip=ip or None,
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @transaction.atomic
    def perform_create(self, serializer):
        cliente = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            cliente,
            Auditoria.CREATE,
            dados_novos=self._snapshot(cliente),
        )

    @transaction.atomic
    def perform_update(self, serializer):
        cliente = self.get_object()
        anteriores = self._snapshot(cliente)

        cliente = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            cliente,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(cliente),
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        cliente = self.get_object()

        if cliente.status_cadastro == Cliente.INATIVO:
            return Response(
                {"detail": "O cliente já está inativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        anteriores = self._snapshot(cliente)

        cliente.status_cadastro = Cliente.INATIVO
        cliente.save(update_fields=["status_cadastro", "updated_at"])

        self._registrar_auditoria(
            cliente,
            Auditoria.DEACTIVATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(cliente),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
