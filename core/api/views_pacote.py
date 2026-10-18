from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction

from core.models import Pacote, SessaoPacote, HistoricoSessao, Agendamento, Auditoria
from .base import ClinicaContextMixin
from .permissions import IsAdminOrSecretario
from .serializers_core import PacoteSerializer

class PacoteViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = PacoteSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_queryset(self):
        return Pacote.objects.filter(
            clinica=self.get_clinica()
        ).select_related('cliente__usuario', 'servico').prefetch_related('sessoes')

    @transaction.atomic
    def perform_create(self, serializer):
        clinica = self.get_clinica()
        pacote = serializer.save(clinica=clinica, ativo=True)
        sessoes_a_criar = [
            SessaoPacote(pacote=pacote, estado=SessaoPacote.DISPONIVEL)
            for _ in range(pacote.quantidade_contratada)
        ]
        SessaoPacote.objects.bulk_create(sessoes_a_criar)
        sessoes_criadas = SessaoPacote.objects.filter(pacote=pacote)
        historicos = [
            HistoricoSessao(
                sessao=s,
                pacote=pacote,
                usuario_executor=self.request.user,
                estado_posterior=SessaoPacote.DISPONIVEL,
                motivo="Criação inicial de pacote"
            ) for s in sessoes_criadas
        ]
        HistoricoSessao.objects.bulk_create(historicos)
        Auditoria.objects.create(
            usuario=self.request.user,
            clinica=clinica,
            acao=Auditoria.CREATE,
            entidade="Pacote",
            objeto_id=str(pacote.id),
            dados_novos={"quantidade": pacote.quantidade_contratada},
            ip=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancelar(self, request, pk=None):
        """
        Serviço de domínio equivalente a cancelar_pacote() - Regra 10.7
        """
        pacote = self.get_object()
        clinica = self.get_clinica()
        motivo = request.data.get('motivo', 'Cancelamento padrão')

        if not pacote.ativo:
            return Response({"detail": "Pacote já inativo."}, status=status.HTTP_400_BAD_REQUEST)
        pacote = Pacote.objects.select_for_update().get(pk=pacote.pk)
        sessoes_elegiveis = list(SessaoPacote.objects.select_for_update().filter(
            pacote=pacote,
            estado__in=[SessaoPacote.DISPONIVEL, SessaoPacote.AGENDADA]
        ))

        agendamentos_afetados = []
        historicos = []

        for sessao in sessoes_elegiveis:
            estado_anterior = sessao.estado
            sessao.estado = SessaoPacote.CANCELADA
            
            if sessao.agendamento_id:
                agendamento = Agendamento.objects.select_for_update().get(pk=sessao.agendamento_id)
                if agendamento.status in [Agendamento.PENDENTE, Agendamento.CONFIRMADO]:
                    agendamento.status = Agendamento.CANCELADO
                    agendamento.motivo_cancelamento = "PACOTE_CANCELADO"
                    agendamento.save(update_fields=['status', 'motivo_cancelamento', 'updated_at'])
                    agendamentos_afetados.append(agendamento.id)
            

            sessao.save(update_fields=['estado', 'updated_at'])
            historicos.append(HistoricoSessao(
                sessao=sessao,
                pacote=pacote,
                agendamento_relacionado_id=sessao.agendamento_id,
                usuario_executor=request.user,
                estado_anterior=estado_anterior,
                estado_posterior=SessaoPacote.CANCELADA,
                motivo="Cancelamento de Pacote (Regra 10.7)",
                justificativa=motivo
            ))

        HistoricoSessao.objects.bulk_create(historicos)
        pacote.ativo = False
        pacote.save(update_fields=['ativo', 'updated_at'])

        # 9. Registrar Auditoria do evento crítico
        Auditoria.objects.create(
            usuario=request.user,
            clinica=clinica,
            acao=Auditoria.DEACTIVATE,
            entidade="Pacote",
            objeto_id=str(pacote.id),
            dados_novos={
                "motivo": motivo, 
                "sessoes_canceladas": len(sessoes_elegiveis), 
                "agendamentos_cancelados": len(agendamentos_afetados)
            },
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response({
            "detail": "Pacote cancelado com sucesso.",
            "sessoes_canceladas": len(sessoes_elegiveis),
            "agendamentos_cancelados": len(agendamentos_afetados)
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Utilize o endpoint de /cancelar/ informando o motivo, conforme a auditoria obrigatória."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )