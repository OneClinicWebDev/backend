from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.response import Response

from core.models import Servico, Auditoria
from .base import ClinicaContextMixin
from .permissions import (
    IsAdminOrSecretario,
    IsAdminOrSecretarioOuProfissionalAgenda,
)
from .serializers_core import ServicoSerializer


class ServicoViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ServicoSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAdminOrSecretarioOuProfissionalAgenda()]
        return [IsAdminOrSecretario()]

    def get_queryset(self):
        return Servico.objects.filter(
            clinica=self.get_clinica()
        ).select_related("clinica")

    def _snapshot(self, servico):
        return {
            "nome": servico.nome,
            "duracao_padrao_minutos": servico.duracao_padrao_minutos,
            "ativo": servico.ativo,
        }

    def _registrar_auditoria(
        self,
        servico,
        acao,
        dados_anteriores=None,
        dados_novos=None,
    ):
        ip = self.request.META.get("REMOTE_ADDR")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        Auditoria.objects.create(
            usuario=self.request.user,
            clinica=servico.clinica,
            acao=acao,
            entidade="Servico",
            objeto_id=str(servico.id),
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            origem="USUARIO",
            ip=ip or None,
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @transaction.atomic
    def perform_create(self, serializer):
        servico = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            servico,
            Auditoria.CREATE,
            dados_novos=self._snapshot(servico),
        )

    @transaction.atomic
    def perform_update(self, serializer):
        servico = self.get_object()
        anteriores = self._snapshot(servico)

        servico = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            servico,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(servico),
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        servico = self.get_object()

        if not servico.ativo:
            return Response(
                {"detail": "O serviço já está inativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        anteriores = self._snapshot(servico)

        servico.ativo = False
        servico.save(update_fields=["ativo", "updated_at"])

        self._registrar_auditoria(
            servico,
            Auditoria.DEACTIVATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(servico),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)