from django.db import transaction
from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.models import (
    Agendamento,
    Auditoria,
    HistoricoSessao,
    Pacote,
    SessaoPacote,
)
from .base import ClinicaContextMixin
from .permissions import IsAdminOrSecretario
from .serializers_core import PacoteSerializer


class PacoteViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = PacoteSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_queryset(self):
        return (
            Pacote.objects.filter(clinica=self.get_clinica())
            .select_related("cliente__usuario", "servico", "clinica")
            .prefetch_related("sessoes")
        )

    
    def _snapshot(self, pacote):
        return {
            "modelo_id": str(pacote.modelo_id) if pacote.modelo_id else None,
            "status": pacote.status,
            "quantidade_sessoes": pacote.quantidade_sessoes,
            "cliente_id": str(pacote.cliente_id),
            "servico_id": str(pacote.servico_id),
            "valor_total": str(pacote.valor_total),
        }

    def _registrar_auditoria(
        self,
        pacote,
        acao,
        dados_anteriores=None,
        dados_novos=None,
    ):
        ip = self.request.META.get("REMOTE_ADDR")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        Auditoria.objects.create(
            usuario=self.request.user,
            clinica=pacote.clinica,
            acao=acao,
            entidade="Pacote",
            objeto_id=str(pacote.pk),
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            origem="USUARIO",
            ip=ip or None,
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    
    @transaction.atomic
    def perform_create(self, serializer):
        modelo = serializer.validated_data.get("modelo")

        if modelo is None:
            raise ValidationError({
                "modelo": "Selecione um modelo ativo do catálogo."
            })

        if modelo.clinica_id != self.get_clinica().pk:
            raise ValidationError({
                "modelo": "O modelo não pertence à clínica ativa."
            })

        if not modelo.ativo:
            raise ValidationError({
                "modelo": "Não é possível vender um modelo inativo."
            })

        pacote = serializer.save(
            clinica=self.get_clinica(),
            status=Pacote.ATIVO,
            servico=modelo.servico,
            quantidade_sessoes=modelo.quantidade_sessoes,
            valor_total=modelo.valor_total,
        )

        sessoes = [
            SessaoPacote(
                pacote=pacote,
                status=SessaoPacote.DISPONIVEL,
            )
            for _ in range(pacote.quantidade_sessoes)
        ]

        SessaoPacote.objects.bulk_create(sessoes)

        sessoes_criadas = SessaoPacote.objects.filter(
            pacote=pacote
        ).only("id", "status")

        HistoricoSessao.objects.bulk_create([
            HistoricoSessao(
                sessao=sessao,
                estado_anterior="",
                estado_novo=SessaoPacote.DISPONIVEL,
                usuario_executor=self.request.user,
                motivo="CRIACAO_PACOTE",
                justificativa="Registro inicial da sessão do pacote.",
            )
            for sessao in sessoes_criadas
        ])

        self._registrar_auditoria(
            pacote,
            Auditoria.CREATE,
            dados_novos={
                **self._snapshot(pacote),
                "modelo_id": str(modelo.pk),
                "sessoes_criadas": len(sessoes),
            },
        )

    @transaction.atomic
    def perform_update(self, serializer):
        pacote = self.get_object()
        anteriores = self._snapshot(pacote)

        if pacote.status != Pacote.ATIVO:
            raise ValidationError(
                "Somente pacotes ativos podem ser editados."
            )

        dados = serializer.validated_data

        if "quantidade_sessoes" in dados:
            raise ValidationError({
                "quantidade_sessoes": (
                    "A quantidade de sessões não pode ser alterada "
                    "após a criação do pacote."
                )
            })

        pacote = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            pacote,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(pacote),
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancelar(self, request, pk=None):
        clinica = self.get_clinica()
        pacote = (
            Pacote.objects.select_for_update()
            .filter(clinica=clinica)
            .get(pk=self.get_object().pk)
        )

        motivo = request.data.get("motivo")

        if not isinstance(motivo, str) or not motivo.strip():
            raise ValidationError({
                "motivo": "Informe o motivo do cancelamento do pacote."
            })

        motivo = motivo.strip()

        if pacote.status != Pacote.ATIVO:
            return Response(
                {
                    "detail": (
                        "Somente pacotes ativos podem ser cancelados. "
                        f"Status atual: {pacote.status}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        dados_anteriores = self._snapshot(pacote)

        sessoes = list(
            SessaoPacote.objects.select_for_update()
            .filter(
                pacote=pacote,
                status__in=[
                    SessaoPacote.DISPONIVEL,
                    SessaoPacote.AGENDADA,
                ],
            )
            .order_by("pk")
        )

        ids_agendamentos_sessoes = [
            sessao.agendamento_id
            for sessao in sessoes
            if sessao.agendamento_id
        ]

        
        agendamentos = list(
            Agendamento.objects.select_for_update().filter(
                clinica=clinica,
                status__in=[
                    Agendamento.PENDENTE,
                    Agendamento.CONFIRMADO,
                ],
            ).exclude(
                resultado__in=[
                    Agendamento.REALIZADO,
                    Agendamento.FALTA,
                ]
            ).filter(
                Q(pacote_origem=pacote)
                | Q(pk__in=ids_agendamentos_sessoes)
            ).order_by("pk")
        )

        agendamentos_cancelados = []

        for agendamento in agendamentos:
            agendamento.status = Agendamento.CANCELADO
            agendamento.motivo_cancelamento = "PACOTE_CANCELADO"
            agendamento.save(
                update_fields=[
                    "status",
                    "motivo_cancelamento",
                    "updated_at",
                ]
            )
            agendamentos_cancelados.append(str(agendamento.pk))

        historicos = []

        for sessao in sessoes:
            estado_anterior = sessao.status
            agendamento_id = sessao.agendamento_id

            sessao.status = SessaoPacote.CANCELADA
            sessao.agendamento = None
            sessao.save(
                update_fields=[
                    "status",
                    "agendamento",
                    "updated_at",
                ]
            )

            historicos.append(
                HistoricoSessao(
                    sessao=sessao,
                    estado_anterior=estado_anterior,
                    estado_novo=SessaoPacote.CANCELADA,
                    usuario_executor=request.user,
                    agendamento_relacionado_id=agendamento_id,
                    motivo="CANCELAMENTO_PACOTE",
                    justificativa=motivo,
                )
            )

        if historicos:
            HistoricoSessao.objects.bulk_create(historicos)

        pacote.status = Pacote.CANCELADO
        pacote.save(update_fields=["status", "updated_at"])

        self._registrar_auditoria(
            pacote,
            Auditoria.DEACTIVATE,
            dados_anteriores=dados_anteriores,
            dados_novos={
                **self._snapshot(pacote),
                "motivo": motivo,
                "sessoes_canceladas": len(sessoes),
                "agendamentos_cancelados": len(agendamentos_cancelados),
                "agendamentos_cancelados_ids": agendamentos_cancelados,
            },
        )

        return Response(
            {
                "detail": "Pacote cancelado com sucesso.",
                "pacote_id": str(pacote.pk),
                "status": pacote.status,
                "sessoes_canceladas": len(sessoes),
                "agendamentos_cancelados": len(agendamentos_cancelados),
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "A exclusão física de pacotes não é permitida. "
                    "Utilize o endpoint de cancelamento e informe o motivo."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
