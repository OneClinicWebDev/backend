from datetime import timedelta

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
    Role,
    Servico,
    Usuario,
)


class AgendamentoAPITestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cache.clear()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cache.clear()
        super().tearDownClass()

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

    def criar_agendamento(
        self,
        inicio=None,
        fim=None,
        cliente=None,
        profissional=None,
        estado=Agendamento.PENDENTE,
    ):
        return Agendamento.objects.create(
            clinica=self.clinica,
            cliente=cliente or self.cliente,
            profissional=profissional or self.profissional,
            servico=self.servico,
            data_hora_inicio=inicio or self.inicio,
            data_hora_fim=fim or self.fim,
            status=estado,
        )

    def payload(self, inicio=None, fim=None):
        return {
            "cliente": self.cliente.pk,
            "profissional": self.profissional.pk,
            "servico": self.servico.pk,
            "data_hora_inicio": (
                inicio or self.inicio
            ).isoformat(),
            "data_hora_fim": (
                fim or self.fim
            ).isoformat(),
        }

    def test_criacao_sem_conflito_confirma_agendamento(self):
        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            getattr(response, "data", None),
        )

        agendamento = Agendamento.objects.get(pk=response.data["id"])

        self.assertEqual(
            agendamento.status,
            Agendamento.CONFIRMADO,
        )
        self.assertEqual(
            agendamento.resultado,
            Agendamento.AGUARDANDO_RESULTADO,
        )
        self.assertTrue(
            Auditoria.objects.filter(
                entidade="Agendamento",
                objeto_id=str(agendamento.pk),
            ).exists()
        )

    def test_admin_pode_ser_selecionado_para_atender(self):
        payload = self.payload()
        payload["profissional"] = self.admin.pk

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            getattr(response, "data", None),
        )

        agendamento = Agendamento.objects.get(
            pk=response.data["id"],
        )

        self.assertEqual(
            agendamento.profissional_id,
            self.admin.pk,
        )
        self.assertEqual(
            agendamento.status,
            Agendamento.CONFIRMADO,
        )

    def test_conflito_confirmado_retorna_409_sem_alterar_agendamento(self):
        existente = self.criar_agendamento(
            estado=Agendamento.CONFIRMADO,
        )

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            getattr(response, "data", None),
        )

        existente.refresh_from_db()

        self.assertEqual(
            existente.status,
            Agendamento.CONFIRMADO,
        )
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_conflito_pendente_sem_decisao_retorna_409(self):
        existente = self.criar_agendamento()

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            getattr(response, "data", None),
        )

        existente.refresh_from_db()

        self.assertEqual(
            existente.status,
            Agendamento.PENDENTE,
        )
        self.assertEqual(
            existente.data_hora_inicio,
            self.inicio,
        )
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_varios_pendentes_nao_sao_alterados_automaticamente(self):
        outro_cliente_usuario = Usuario.objects.create_user(
            cpf="93541134780",
            nome_completo="Outro Cliente",
            data_nascimento="1996-04-04",
            password="SenhaForte123",
        )

        outro_cliente = Cliente.objects.create(
            usuario=outro_cliente_usuario,
            clinica=self.clinica,
            telefone="11977777777",
        )

        primeiro = self.criar_agendamento(
            estado=Agendamento.PENDENTE,
        )

        segundo = self.criar_agendamento(
            inicio=self.inicio + timedelta(minutes=10),
            fim=self.fim + timedelta(minutes=10),
            cliente=outro_cliente,
            estado=Agendamento.PENDENTE,
        )

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            getattr(response, "data", None),
        )

        primeiro.refresh_from_db()
        segundo.refresh_from_db()

        self.assertEqual(primeiro.status, Agendamento.PENDENTE)
        self.assertEqual(segundo.status, Agendamento.PENDENTE)
        self.assertEqual(
            primeiro.data_hora_inicio,
            self.inicio,
        )
        self.assertEqual(
            segundo.data_hora_inicio,
            self.inicio + timedelta(minutes=10),
        )
        self.assertEqual(Agendamento.objects.count(), 2)

    def test_cancelar_pendente_e_confirmar_novo_agendamento(self):
        existente = self.criar_agendamento(
            estado=Agendamento.PENDENTE,
        )

        dados = self.payload()
        dados.update({
            "resolucao_conflito": "CANCELAR_E_CONFIRMAR",
            "agendamento_conflitante_id": existente.pk,
        })

        response = self.client.post(
            self.url,
            dados,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            getattr(response, "data", None),
        )

        existente.refresh_from_db()

        self.assertEqual(
            existente.status,
            Agendamento.CANCELADO,
        )
        self.assertEqual(
            existente.motivo_cancelamento,
            "SOBREPOSICAO",
        )

        novo = Agendamento.objects.get(pk=response.data["id"])

        self.assertEqual(novo.status, Agendamento.CONFIRMADO)

        self.assertTrue(
            Auditoria.objects.filter(
                entidade="Agendamento",
                objeto_id=str(existente.pk),
            ).exists()
        )

    def test_remanejar_pendente_e_confirmar_novo_agendamento(self):
        existente = self.criar_agendamento(
            estado=Agendamento.PENDENTE,
        )

        novo_inicio = self.inicio + timedelta(hours=2)
        novo_fim = novo_inicio + timedelta(minutes=30)

        dados = self.payload()
        dados.update({
            "resolucao_conflito": "REMANEJAR",
            "agendamento_conflitante_id": existente.pk,
            "conflito_novo_inicio": novo_inicio.isoformat(),
            "conflito_novo_fim": novo_fim.isoformat(),
        })

        response = self.client.post(
            self.url,
            dados,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            getattr(response, "data", None),
        )

        existente.refresh_from_db()

        self.assertEqual(
            existente.status,
            Agendamento.PENDENTE,
        )
        self.assertEqual(
            existente.data_hora_inicio,
            novo_inicio,
        )
        self.assertEqual(
            existente.data_hora_fim,
            novo_fim,
        )

        novo = Agendamento.objects.get(pk=response.data["id"])
        self.assertEqual(novo.status, Agendamento.CONFIRMADO)

    def test_remanejamento_com_conflito_preserva_dados_originais(self):
        existente = self.criar_agendamento(
            estado=Agendamento.PENDENTE,
        )

        bloqueio_inicio = self.inicio + timedelta(hours=2)
        bloqueio_fim = bloqueio_inicio + timedelta(minutes=30)

        bloqueio = self.criar_agendamento(
            inicio=bloqueio_inicio,
            fim=bloqueio_fim,
            cliente=self.cliente,
            estado=Agendamento.PENDENTE,
        )

        dados = self.payload()
        dados.update({
            "resolucao_conflito": "REMANEJAR",
            "agendamento_conflitante_id": existente.pk,
            "conflito_novo_inicio": bloqueio_inicio.isoformat(),
            "conflito_novo_fim": bloqueio_fim.isoformat(),
        })

        response = self.client.post(
            self.url,
            dados,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            getattr(response, "data", None),
        )

        existente.refresh_from_db()
        bloqueio.refresh_from_db()

        self.assertEqual(
            existente.data_hora_inicio,
            self.inicio,
        )
        self.assertEqual(
            existente.data_hora_fim,
            self.fim,
        )
        self.assertEqual(
            existente.status,
            Agendamento.PENDENTE,
        )
        self.assertEqual(
            bloqueio.status,
            Agendamento.PENDENTE,
        )
        self.assertEqual(Agendamento.objects.count(), 2)
