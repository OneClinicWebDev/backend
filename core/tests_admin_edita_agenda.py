from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Agendamento,
    Cliente,
    Clinica,
    Colaborador,
    Role,
    Servico,
    Usuario,
)


class AdminEditaAgendaTestCase(TestCase):
    def criar_usuario(self, cpf, nome):
        return Usuario.objects.create_user(
            cpf=cpf,
            nome_completo=nome,
            data_nascimento="1990-01-01",
            password="Teste!Senha2026",
        )

    def setUp(self):
        self.clinica = Clinica.objects.create(
            cnpj="11444777000161",
            razao_social="Clínica Teste LTDA",
            nome_fantasia="Clínica Teste",
            telefone="47999999999",
        )
        self.usuario_admin = self.criar_usuario("11144477735", "Admin Teste")
        self.usuario_sec = self.criar_usuario("22255588846", "Secretaria Teste")
        self.usuario_prof = self.criar_usuario("33366699957", "Profissional Teste")
        self.usuario_cli = self.criar_usuario("44477700068", "Cliente Teste")
        self.admin = Colaborador.objects.create(
            usuario=self.usuario_admin,
            clinica=self.clinica,
            role=Role.objects.get_or_create(nome=Role.ADMIN)[0],
        )
        self.secretario = Colaborador.objects.create(
            usuario=self.usuario_sec,
            clinica=self.clinica,
            role=Role.objects.get_or_create(nome=Role.SECRETARIO)[0],
        )
        self.profissional = Colaborador.objects.create(
            usuario=self.usuario_prof,
            clinica=self.clinica,
            role=Role.objects.get_or_create(nome=Role.PROFISSIONAL)[0],
        )
        self.cliente = Cliente.objects.create(
            usuario=self.usuario_cli,
            clinica=self.clinica,
            telefone="47999999999",
        )
        self.servico = Servico.objects.create(
            clinica=self.clinica,
            nome="Limpeza de pele",
            preco="100.00",
            duracao_padrao_minutos=30,
        )

    def agendamento(self, status):
        inicio = timezone.now() + timedelta(days=1)
        return Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=status,
        )

    def cliente_api(self, usuario):
        api = APIClient()
        api.force_authenticate(usuario)
        return api

    def patch(self, usuario, agendamento, dados):
        return self.cliente_api(usuario).patch(
            f"/api/agendamentos/{agendamento.pk}/",
            dados,
            format="json",
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )

    def test_admin_edita_agenda_de_outro_profissional(self):
        agendamento = self.agendamento(Agendamento.CONFIRMADO)
        resposta = self.patch(
            self.usuario_admin, agendamento, {"observacoes": "Ajuste do admin"}
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        agendamento.refresh_from_db()
        self.assertEqual(agendamento.observacoes, "Ajuste do admin")

    def test_admin_edita_observacoes_de_concluido_e_cancelado(self):
        for situacao in (Agendamento.CONCLUIDO, Agendamento.CANCELADO):
            agendamento = self.agendamento(situacao)
            resposta = self.patch(
                self.usuario_admin, agendamento, {"observacoes": "Nota do admin"}
            )
            self.assertEqual(resposta.status_code, 200, resposta.content)
            agendamento.refresh_from_db()
            self.assertEqual(agendamento.observacoes, "Nota do admin")

    def test_admin_nao_altera_campos_travados_de_encerrado(self):
        agendamento = self.agendamento(Agendamento.CONCLUIDO)
        novo_inicio = agendamento.data_hora_inicio + timedelta(hours=2)
        resposta = self.patch(
            self.usuario_admin,
            agendamento,
            {
                "data_hora_inicio": novo_inicio.isoformat(),
                "data_hora_fim": (novo_inicio + timedelta(minutes=30)).isoformat(),
            },
        )
        self.assertEqual(resposta.status_code, 400)
        agendamento.refresh_from_db()
        self.assertNotEqual(agendamento.data_hora_inicio, novo_inicio)

    def test_secretario_nao_edita_encerrado(self):
        agendamento = self.agendamento(Agendamento.CONCLUIDO)
        resposta = self.patch(
            self.usuario_sec, agendamento, {"observacoes": "Tentativa"}
        )
        self.assertEqual(resposta.status_code, 400)

    def test_edicao_de_agendamento_ativo_com_cliente_inativado_depois(self):
        agendamento = self.agendamento(Agendamento.CONFIRMADO)
        Cliente.objects.filter(pk=self.cliente.pk).update(
            status_cadastro=Cliente.INATIVO
        )
        resposta = self.patch(
            self.usuario_admin, agendamento, {"observacoes": "Cliente inativado"}
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)