
from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.response import Response

from core.models import ModeloPacote, Auditoria
from .base import ClinicaContextMixin
from .permissions import IsAdminOrSecretario
from .serializers_core import ModeloPacoteSerializer


class ModeloPacoteViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ModeloPacoteSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_queryset(self):
        return ModeloPacote.objects.filter(
            clinica=self.get_clinica()
        ).select_related("clinica", "servico")

    def _snapshot(self, modelo):
        return {
            "nome": modelo.nome,
            "servico_id": str(modelo.servico_id),
            "quantidade_sessoes": modelo.quantidade_sessoes,
            "valor_total": str(modelo.valor_total),
            "categoria": modelo.categoria,
            "descricao": modelo.descricao,
            "ativo": modelo.ativo,
        }

    def _registrar_auditoria(
        self,
        modelo,
        acao,
        dados_anteriores=None,
        dados_novos=None,
    ):
        ip = self.request.META.get("REMOTE_ADDR")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        Auditoria.objects.create(
            usuario=self.request.user,
            clinica=modelo.clinica,
            acao=acao,
            entidade="ModeloPacote",
            objeto_id=str(modelo.pk),
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            origem="USUARIO",
            ip=ip or None,
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @transaction.atomic
    def perform_create(self, serializer):
        modelo = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            modelo,
            Auditoria.CREATE,
            dados_novos=self._snapshot(modelo),
        )

    @transaction.atomic
    def perform_update(self, serializer):
        modelo = self.get_object()
        anteriores = self._snapshot(modelo)

        modelo = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            modelo,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(modelo),
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        modelo = self.get_object()

        if not modelo.ativo:
            return Response(
                {"detail": "O modelo de pacote já está inativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        anteriores = self._snapshot(modelo)
        modelo.ativo = False
        modelo.save(update_fields=["ativo", "updated_at"])

        self._registrar_auditoria(
            modelo,
            Auditoria.DEACTIVATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(modelo),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
