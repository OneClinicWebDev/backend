
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Agendamento,
    Auditoria,
    Cliente,
    Clinica,
    Colaborador,
    HistoricoSessao,
    Pacote,
    Role,
    Servico,
    SessaoPacote,
    Usuario,
)


class AgendamentoEncerramentoAPITestCase(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.clinica = Clinica.objects.create(
            cnpj="48545800000100",
            razao_social="Clinica Teste",
            nome_fantasia="Clinica Teste",
            telefone="11999999999",
        )

        self.usuario_admin = Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Admin Teste",
            data_nascimento="1990-01-01",
            password="SenhaForte123",
        )

        self.role_admin = Role.objects.create(nome=Role.ADMIN)

        self.admin = Colaborador.objects.create(
            usuario=self.usuario_admin,
            clinica=self.clinica,
            role=self.role_admin,
            ativo=True,
        )

        self.usuario_profissional = Usuario.objects.create_user(
            cpf="11144477735",
            nome_completo="Profissional Teste",
            data_nascimento="1992-02-02",
            password="SenhaForte123",
        )

        self.role_profissional = Role.objects.create(
            nome=Role.PROFISSIONAL,
        )

        self.profissional = Colaborador.objects.create(
            usuario=self.usuario_profissional,
            clinica=self.clinica,
            role=self.role_profissional,
            ativo=True,
        )

        self.usuario_cliente = Usuario.objects.create_user(
            cpf="22233344405",
            nome_completo="Cliente Teste",
            data_nascimento="1995-03-03",
            password="SenhaForte123",
        )

        self.cliente = Cliente.objects.create(
            usuario=self.usuario_cliente,
            clinica=self.clinica,
            telefone="11988888888",
        )

        self.servico = Servico.objects.create(
            clinica=self.clinica,
            nome="Servico Teste",
            duracao_padrao_minutos=30,
        )

        self.inicio = (
            timezone.now() + timedelta(days=10)
        ).replace(second=0, microsecond=0)
        self.fim = self.inicio + timedelta(minutes=30)

        response = self.client.post(
            "/api/token/",
            {
                "cpf": self.usuario_admin.cpf,
                "password": "SenhaForte123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}",
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )

        self.url = "/api/agendamentos/"

    def criar_agendamento(self, estado=Agendamento.CONFIRMADO):
        return Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            data_hora_inicio=self.inicio,
            data_hora_fim=self.fim,
            status=estado,
            resultado=Agendamento.AGUARDANDO_RESULTADO,
        )

    def criar_sessao_agendada(self, agendamento):
        pacote = Pacote.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            servico=self.servico,
            quantidade_sessoes=1,
            valor_total=Decimal("150.00"),
            status=Pacote.ATIVO,
        )

        sessao = SessaoPacote.objects.create(
            pacote=pacote,
            agendamento=agendamento,
            status=SessaoPacote.AGENDADA,
        )

        return pacote, sessao

    def url_action(self, agendamento, action):
        return f"{self.url}{agendamento.pk}/{action}/"

    def test_cancelamento_sem_motivo_retorna_400_sem_alteracoes(self):
        agendamento = self.criar_agendamento()

        response = self.client.post(
            self.url_action(agendamento, "cancelar"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()

        self.assertEqual(
            agendamento.status,
            Agendamento.CONFIRMADO,
        )
        self.assertFalse(
            Auditoria.objects.filter(
                entidade="Agendamento",
                objeto_id=str(agendamento.pk),
            ).exists()
        )

    def test_cancelamento_manual_atualiza_status_motivo_e_auditoria(self):
        agendamento = self.criar_agendamento()

        response = self.client.post(
            self.url_action(agendamento, "cancelar"),
            {"motivo": "Solicitação do cliente"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()

        self.assertEqual(
            agendamento.status,
            Agendamento.CANCELADO,
        )
        self.assertEqual(
            agendamento.motivo_cancelamento,
            "Solicitação do cliente",
        )

        self.assertTrue(
            Auditoria.objects.filter(
                entidade="Agendamento",
                objeto_id=str(agendamento.pk),
                dados_anteriores__status=Agendamento.CONFIRMADO,
                dados_novos__status=Agendamento.CANCELADO,
            ).exists()
        )

    def test_cancelamento_libera_sessao_e_registra_historico(self):
        agendamento = self.criar_agendamento()
        _, sessao = self.criar_sessao_agendada(agendamento)

        response = self.client.post(
            self.url_action(agendamento, "cancelar"),
            {"motivo": "Cliente solicitou cancelamento"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        sessao.refresh_from_db()

        self.assertEqual(
            agendamento.status,
            Agendamento.CANCELADO,
        )
        self.assertEqual(
            sessao.status,
            SessaoPacote.DISPONIVEL,
        )
        self.assertIsNone(sessao.agendamento_id)

        historico = HistoricoSessao.objects.filter(
            sessao=sessao,
            agendamento_relacionado=agendamento,
            estado_anterior=SessaoPacote.AGENDADA,
            estado_novo=SessaoPacote.DISPONIVEL,
        )

        self.assertTrue(historico.exists())
        self.assertEqual(
            historico.latest("data_alteracao").justificativa,
            "Cliente solicitou cancelamento",
        )

    def test_nao_permite_cancelar_agendamento_ja_cancelado(self):
        agendamento = self.criar_agendamento(
            estado=Agendamento.CANCELADO,
        )

        response = self.client.post(
            self.url_action(agendamento, "cancelar"),
            {"motivo": "Novo motivo"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        self.assertEqual(
            agendamento.status,
            Agendamento.CANCELADO,
        )

    def test_nao_permite_cancelar_agendamento_concluido(self):
        agendamento = self.criar_agendamento(
            estado=Agendamento.CONCLUIDO,
        )

        response = self.client.post(
            self.url_action(agendamento, "cancelar"),
            {"motivo": "Tentativa de cancelamento"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        self.assertEqual(
            agendamento.status,
            Agendamento.CONCLUIDO,
        )

    def test_registro_de_falta_sem_sessao_de_pacote(self):
        agendamento = self.criar_agendamento()

        response = self.client.post(
            self.url_action(agendamento, "registrar_falta"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()

        self.assertEqual(
            agendamento.status,
            Agendamento.CONCLUIDO,
        )
        self.assertEqual(
            agendamento.resultado,
            Agendamento.FALTA,
        )

        self.assertTrue(
            Auditoria.objects.filter(
                entidade="Agendamento",
                objeto_id=str(agendamento.pk),
                dados_anteriores__status=Agendamento.CONFIRMADO,
                dados_novos__resultado=Agendamento.FALTA,
            ).exists()
        )

    def test_falta_com_sessao_exige_decisao_explicita(self):
        agendamento = self.criar_agendamento()
        _, sessao = self.criar_sessao_agendada(agendamento)

        response = self.client.post(
            self.url_action(agendamento, "registrar_falta"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        sessao.refresh_from_db()

        self.assertEqual(
            agendamento.status,
            Agendamento.CONFIRMADO,
        )
        self.assertEqual(
            agendamento.resultado,
            Agendamento.AGUARDANDO_RESULTADO,
        )
        self.assertEqual(
            sessao.status,
            SessaoPacote.AGENDADA,
        )
        self.assertEqual(
            sessao.agendamento_id,
            agendamento.pk,
        )
        self.assertFalse(
            HistoricoSessao.objects.filter(sessao=sessao).exists()
        )

    def test_falta_preservando_sessao_libera_para_disponivel(self):
        agendamento = self.criar_agendamento()
        _, sessao = self.criar_sessao_agendada(agendamento)

        response = self.client.post(
            self.url_action(agendamento, "registrar_falta"),
            {
                "decisao_sessao": "PRESERVAR",
                "justificativa": "Cliente avisou que não compareceria",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        sessao.refresh_from_db()

        self.assertEqual(
            agendamento.status,
            Agendamento.CONCLUIDO,
        )
        self.assertEqual(
            agendamento.resultado,
            Agendamento.FALTA,
        )
        self.assertEqual(
            sessao.status,
            SessaoPacote.DISPONIVEL,
        )
        self.assertIsNone(sessao.agendamento_id)

        self.assertTrue(
            HistoricoSessao.objects.filter(
                sessao=sessao,
                agendamento_relacionado=agendamento,
                estado_anterior=SessaoPacote.AGENDADA,
                estado_novo=SessaoPacote.DISPONIVEL,
                justificativa="Cliente avisou que não compareceria",
            ).exists()
        )

    def test_falta_perdendo_sessao_registra_historico(self):
        agendamento = self.criar_agendamento()
        _, sessao = self.criar_sessao_agendada(agendamento)

        response = self.client.post(
            self.url_action(agendamento, "registrar_falta"),
            {
                "decisao_sessao": "PERDER",
                "justificativa": "Falta sem aviso",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        sessao.refresh_from_db()

        self.assertEqual(
            agendamento.resultado,
            Agendamento.FALTA,
        )
        self.assertEqual(
            sessao.status,
            SessaoPacote.PERDIDA,
        )
        self.assertIsNone(sessao.agendamento_id)

        self.assertTrue(
            HistoricoSessao.objects.filter(
                sessao=sessao,
                agendamento_relacionado=agendamento,
                estado_anterior=SessaoPacote.AGENDADA,
                estado_novo=SessaoPacote.PERDIDA,
                justificativa="Falta sem aviso",
            ).exists()
        )

    def test_nao_permite_registrar_falta_duas_vezes(self):
        agendamento = self.criar_agendamento(
            estado=Agendamento.CONCLUIDO,
        )
        agendamento.resultado = Agendamento.FALTA
        agendamento.save(update_fields=["resultado"])

        response = self.client.post(
            self.url_action(agendamento, "registrar_falta"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        self.assertEqual(
            agendamento.resultado,
            Agendamento.FALTA,
        )

    def test_profissional_nao_pode_cancelar_agendamento(self):
        agendamento = self.criar_agendamento()

        self.client.force_authenticate(
            user=self.usuario_profissional,
        )
        self.client.credentials(
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )

        response = self.client.post(
            self.url_action(agendamento, "cancelar"),
            {"motivo": "Tentativa pelo profissional"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        self.assertEqual(
            agendamento.status,
            Agendamento.CONFIRMADO,
        )

    def test_profissional_nao_pode_registrar_falta(self):
        agendamento = self.criar_agendamento()

        self.client.force_authenticate(
            user=self.usuario_profissional,
        )
        self.client.credentials(
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )

        response = self.client.post(
            self.url_action(agendamento, "registrar_falta"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            getattr(response, "data", None),
        )

        agendamento.refresh_from_db()
        self.assertEqual(
            agendamento.status,
            Agendamento.CONFIRMADO,
        )
