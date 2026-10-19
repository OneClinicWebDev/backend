
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    Agendamento,
    SessaoPacote,
    HistoricoSessao,
    Auditoria,
)


class Command(BaseCommand):
    help = "Conclui agendamentos vencidos e registra o consumo de sessões."

    def handle(self, *args, **kwargs):
        agora = timezone.now()

        ids = list(
            Agendamento.objects.filter(
                status=Agendamento.CONFIRMADO,
                data_hora_fim__lte=agora,
            )
            .exclude(resultado=Agendamento.FALTA)
            .order_by("data_hora_fim")
            .values_list("id", flat=True)
        )

        processados = 0

        for agendamento_id in ids:
            if self.processar_agendamento(agendamento_id):
                processados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Rotina concluída. Agendamentos processados: {processados}."
            )
        )

    def processar_agendamento(self, agendamento_id):
        with transaction.atomic():
            agendamento = (
                Agendamento.objects.select_for_update()
                .filter(pk=agendamento_id)
                .first()
            )

            if agendamento is None:
                return False

            if agendamento.status != Agendamento.CONFIRMADO:
                return False

            if agendamento.data_hora_fim > timezone.now():
                return False

            if agendamento.resultado == Agendamento.FALTA:
                return False

            resultado_anterior = agendamento.resultado
            agendamento.status = Agendamento.CONCLUIDO

            if agendamento.resultado == Agendamento.AGUARDANDO_RESULTADO:
                agendamento.resultado = Agendamento.REALIZADO

            agendamento.save(update_fields=[
                "status",
                "resultado",
                "updated_at",
            ])

            sessao = (
                SessaoPacote.objects.select_for_update()
                .filter(agendamento=agendamento)
                .first()
            )

            sessoes_consumidas = 0

            if sessao and sessao.status == SessaoPacote.AGENDADA:
                estado_anterior = sessao.status
                sessao.status = SessaoPacote.UTILIZADA
                sessao.save(update_fields=["status", "updated_at"])

                HistoricoSessao.objects.create(
                    sessao=sessao,
                    estado_anterior=estado_anterior,
                    estado_novo=SessaoPacote.UTILIZADA,
                    usuario_executor=None,
                    agendamento_relacionado=agendamento,
                    motivo="Conclusão automática do agendamento",
                    justificativa="Processamento pela rotina automática.",
                )

                sessoes_consumidas = 1

            Auditoria.objects.create(
                clinica=agendamento.clinica,
                usuario=None,
                acao=Auditoria.UPDATE,
                entidade="Agendamento",
                objeto_id=str(agendamento.id),
                dados_anteriores={
                    "status": Agendamento.CONFIRMADO,
                    "resultado": resultado_anterior,
                },
                dados_novos={
                    "status": Agendamento.CONCLUIDO,
                    "resultado": agendamento.resultado,
                    "sessoes_consumidas": sessoes_consumidas,
                },
                origem="SISTEMA",
            )

            return True
