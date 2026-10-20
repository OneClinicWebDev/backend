from datetime import timedelta
from io import StringIO
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
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
        return Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            pacote_origem=self.pacote,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=Agendamento.CONFIRMADO,
            resultado=(
                resultado or Agendamento.AGUARDANDO_RESULTADO
            ),
        )

    def test_pacote_com_sessoes_nao_pode_ser_excluido(self):
        SessaoPacote.objects.create(
            pacote=self.pacote,
            status=SessaoPacote.DISPONIVEL,
        )

        with self.assertRaises(ProtectedError):
            self.pacote.delete()