from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Agendamento, ProcedimentoRealizado
from core.servicos_atendimento import RegraAtendimentoError, concluir_atendimento


class Command(BaseCommand):
    help = "Conclui agendamentos vencidos, consome a sessão e registra o procedimento realizado."

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
        try:
            concluir_atendimento(
                agendamento_id,
                usuario=None,
                origem=ProcedimentoRealizado.ORIGEM_AUTOMATICA,
                exigir_inicio=True,
            )
        except RegraAtendimentoError as exc:
            self.stderr.write(
                f"Agendamento {agendamento_id} não concluído: {exc}"
            )
            return False

        return True