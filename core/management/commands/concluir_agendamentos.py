from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from core.models import Agendamento, SessaoPacote, HistoricoSessao, Auditoria

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        agora = timezone.now()
        
        agendamentos_elegiveis = Agendamento.objects.filter(
            status=Agendamento.CONFIRMADO,
            data_hora_fim__lte=agora,
        ).exclude(
            resultado=Agendamento.FALTA
        )

        for agendamento in agendamentos_elegiveis:
            self.processar_agendamento(agendamento.id)

    def processar_agendamento(self, agendamento_id):
        with transaction.atomic():
            agendamento = Agendamento.objects.select_for_update().get(id=agendamento_id)

            if agendamento.status != Agendamento.CONFIRMADO:
                return

            if agendamento.resultado == Agendamento.FALTA:
                return

            agendamento.status = Agendamento.CONCLUIDO
            
            if agendamento.resultado == Agendamento.AGUARDANDO_RESULTADO:
                agendamento.resultado = Agendamento.REALIZADO

            agendamento.save(update_fields=['status', 'resultado', 'updated_at'])

            sessoes = SessaoPacote.objects.select_for_update().filter(
                agendamento=agendamento,
                estado=SessaoPacote.AGENDADA
            )

            historicos = []
            for sessao in sessoes:
                estado_anterior = sessao.estado
                sessao.estado = SessaoPacote.UTILIZADA
                sessao.save(update_fields=['estado', 'updated_at'])

                historicos.append(
                    HistoricoSessao(
                        sessao=sessao,
                        pacote=sessao.pacote,
                        agendamento_relacionado=agendamento,
                        estado_anterior=estado_anterior,
                        estado_posterior=SessaoPacote.UTILIZADA,
                        motivo="Conclusão automática"
                    )
                )

            if historicos:
                HistoricoSessao.objects.bulk_create(historicos)

            Auditoria.objects.create(
                clinica=agendamento.clinica,
                acao=Auditoria.UPDATE,
                entidade="Agendamento",
                objeto_id=str(agendamento.id),
                dados_novos={
                    "status": Agendamento.CONCLUIDO,
                    "resultado": agendamento.resultado,
                    "sessoes_consumidas": len(historicos)
                },
                origem="SISTEMA"
            )