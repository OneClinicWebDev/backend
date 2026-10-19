
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Usuario,
    Clinica,
    Role,
    Colaborador,
    Cliente,
    Servico,
    Pacote,
    Agendamento,
    SessaoPacote,
    HistoricoSessao,
)


class SessoesPacoteTestCase(TestCase):
    def setUp(self):
        self.usuario_profissional = Usuario.objects.create_user(
            cpf="11144477735",
            nome_completo="Profissional Teste",
            data_nascimento="1990-01-01",
            password="Teste!Senha2026",
        )
        self.usuario_cliente = Usuario.objects.create_user(
            cpf="22255588846",
            nome_completo="Cliente Teste",
            data_nascimento="1995-01-01",
            password="Teste!Senha2026",
        )

        self.clinica = Clinica.objects.create(
            cnpj="11444777000161",
            razao_social="Clínica Teste LTDA",
            nome_fantasia="Clínica Teste",
            telefone="47999999999",
        )

        role = Role.objects.create(nome=Role.PROFISSIONAL)
        self.profissional = Colaborador.objects.create(
            usuario=self.usuario_profissional,
            clinica=self.clinica,
            role=role,
        )

        self.cliente = Cliente.objects.create(
            usuario=self.usuario_cliente,
            clinica=self.clinica,
            telefone="47999999999",
        )

        self.servico = Servico.objects.create(
            clinica=self.clinica,
            nome="Serviço Teste",
            duracao_padrao_minutos=30,
        )

        self.pacote = Pacote.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            servico=self.servico,
            quantidade_sessoes=3,
            valor_total="300.00",
        )

    def criar_agendamento_vencido(self, resultado=None):
        inicio = timezone.now() - timedelta(hours=2)
        agendamento = Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            pacote_origem=self.pacote,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=Agendamento.CONFIRMADO,
            resultado=(
                resultado
                or Agendamento.AGUARDANDO_RESULTADO
            ),
        )
        return agendamento

    def test_saldo_calculado_pelas_sessoes_disponiveis(self):
        for _ in range(3):
            SessaoPacote.objects.create(
                pacote=self.pacote,
                status=SessaoPacote.DISPONIVEL,
            )

        self.assertEqual(self.pacote.saldo_sessoes, 3)

        sessao = self.pacote.sessoes.first()
        sessao.status = SessaoPacote.UTILIZADA
        sessao.save(update_fields=["status", "updated_at"])

        self.assertEqual(self.pacote.saldo_sessoes, 2)

    def test_rotina_consume_sessao_agendada_e_registra_historico(self):
        agendamento = self.criar_agendamento_vencido()

        sessao = SessaoPacote.objects.create(
            pacote=self.pacote,
            agendamento=agendamento,
            status=SessaoPacote.AGENDADA,
        )

        call_command(
            "concluir_agendamentos",
            stdout=StringIO(),
        )

        agendamento.refresh_from_db()
        sessao.refresh_from_db()

        self.assertEqual(agendamento.status, Agendamento.CONCLUIDO)
        self.assertEqual(agendamento.resultado, Agendamento.REALIZADO)
        self.assertEqual(sessao.status, SessaoPacote.UTILIZADA)

        historico = HistoricoSessao.objects.get(sessao=sessao)
        self.assertEqual(
            historico.estado_anterior,
            SessaoPacote.AGENDADA,
        )
        self.assertEqual(
            historico.estado_novo,
            SessaoPacote.UTILIZADA,
        )
        self.assertEqual(
            historico.agendamento_relacionado_id,
            agendamento.id,
        )

    def test_falta_previamente_registrada_nao_consumira_sessao(self):
        agendamento = self.criar_agendamento_vencido(
            resultado=Agendamento.FALTA,
        )

        sessao = SessaoPacote.objects.create(
            pacote=self.pacote,
            agendamento=agendamento,
            status=SessaoPacote.AGENDADA,
        )

        call_command(
            "concluir_agendamentos",
            stdout=StringIO(),
        )

        agendamento.refresh_from_db()
        sessao.refresh_from_db()

        self.assertEqual(agendamento.status, Agendamento.CONFIRMADO)
        self.assertEqual(agendamento.resultado, Agendamento.FALTA)
        self.assertEqual(sessao.status, SessaoPacote.AGENDADA)
        self.assertFalse(
            HistoricoSessao.objects.filter(sessao=sessao).exists()
        )

    def test_rotina_nao_consume_sessao_mais_de_uma_vez(self):
        agendamento = self.criar_agendamento_vencido()
        sessao = SessaoPacote.objects.create(
            pacote=self.pacote,
            agendamento=agendamento,
            status=SessaoPacote.AGENDADA,
        )

        call_command("concluir_agendamentos", stdout=StringIO())
        call_command("concluir_agendamentos", stdout=StringIO())

        sessao.refresh_from_db()

        self.assertEqual(sessao.status, SessaoPacote.UTILIZADA)
        self.assertEqual(
            HistoricoSessao.objects.filter(sessao=sessao).count(),
            1,
        )
