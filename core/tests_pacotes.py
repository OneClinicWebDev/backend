from datetime import timedelta

from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone

from core.models import (
    Usuario,
    Clinica,
    Role,
    Colaborador,
    Cliente,
    Servico,
    ModeloPacote,
    Pacote,
    Agendamento,
    SessaoPacote,
    HistoricoSessao,
    Auditoria,
)


class PacotesAPITestCase(APITestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Administrador Teste",
            data_nascimento="1990-01-01",
            password="SenhaForte123",
        )

        self.usuario_cliente = Usuario.objects.create_user(
            cpf="11144477735",
            nome_completo="Cliente Teste",
            data_nascimento="1995-01-01",
            password="SenhaForte123",
        )

        self.clinica = Clinica.objects.create(
            cnpj="48545800000100",
            razao_social="Clínica Teste LTDA",
            nome_fantasia="Clínica Teste",
            telefone="47999999999",
        )

        self.clinica_externa = Clinica.objects.create(
            cnpj="92135061000155",
            razao_social="Clínica Externa LTDA",
            nome_fantasia="Clínica Externa",
            telefone="47988888888",
        )

        self.role_admin = Role.objects.get_or_create(nome=Role.ADMIN)[0]

        Colaborador.objects.create(
            usuario=self.admin,
            clinica=self.clinica,
            role=self.role_admin,
            ativo=True,
        )

        self.cliente = Cliente.objects.create(
            usuario=self.usuario_cliente,
            clinica=self.clinica,
            telefone="47999999999",
        )

        self.cliente_externo = Cliente.objects.create(
            usuario=self.usuario_cliente,
            clinica=self.clinica_externa,
            telefone="47999999999",
        )

        self.servico = Servico.objects.create(
            clinica=self.clinica,
            nome="Limpeza de Pele",
            duracao_padrao_minutos=60,
            ativo=True,
        )

        self.servico_externo = Servico.objects.create(
            clinica=self.clinica_externa,
            nome="Serviço Externo",
            duracao_padrao_minutos=30,
            ativo=True,
        )

        response = self.client.post(
            "/api/token/",
            {
                "cpf": "52998224725",
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
            HTTP_X_CLINICA_ID=str(self.clinica.id),
        )

        self.url = "/api/pacotes/"

    def criar_pacote(self, quantidade=3):
        return Pacote.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            servico=self.servico,
            quantidade_sessoes=quantidade,
            valor_total="300.00",
        )

    def payload_pacote(self, **overrides):
        payload = {
            "cliente": str(self.cliente.id),
            "servico": self.servico.id,
            "quantidade_sessoes": 3,
            "valor_total": "300.00",
            "observacoes": "Pacote de teste",
        }
        payload.update(overrides)
        return payload

    def test_criar_pacote_gera_sessoes_e_historico(self):
        modelo = ModeloPacote.objects.create(
            clinica=self.clinica,
            nome="Pacote Limpeza de Pele",
            servico=self.servico,
            quantidade_sessoes=3,
            valor_total="300.00",
            ativo=True,
        )

        payload = self.payload_pacote(modelo=modelo.id)

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

        pacote = Pacote.objects.get(id=response.data["id"])

        self.assertEqual(pacote.modelo_id, modelo.id)
        self.assertEqual(pacote.servico_id, self.servico.id)
        self.assertEqual(pacote.quantidade_sessoes, 3)
        self.assertEqual(str(pacote.valor_total), "300.00")
        self.assertEqual(pacote.sessoes.count(), 3)

        self.assertEqual(
            HistoricoSessao.objects.filter(
                sessao__pacote=pacote,
                motivo="CRIACAO_PACOTE",
            ).count(),
            3,
        )

        self.assertTrue(
            Auditoria.objects.filter(
                entidade="Pacote",
                objeto_id=str(pacote.id),
                acao=Auditoria.CREATE,
            ).exists()
        )
    def test_criar_pacote_rejeita_cliente_de_outra_clinica(self):
        response = self.client.post(
            self.url,
            self.payload_pacote(
                cliente=str(self.cliente_externo.id)
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )
        self.assertFalse(
            Pacote.objects.filter(
                clinica=self.clinica
            ).exists()
        )

    def test_criar_pacote_rejeita_servico_de_outra_clinica(self):
        response = self.client.post(
            self.url,
            self.payload_pacote(
                servico=self.servico_externo.id
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )
        self.assertFalse(
            Pacote.objects.filter(
                clinica=self.clinica
            ).exists()
        )

    def test_criar_pacote_rejeita_quantidade_zero(self):
        response = self.client.post(
            self.url,
            self.payload_pacote(quantidade_sessoes=0),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            Pacote.objects.filter(clinica=self.clinica).exists()
        )

    def test_listagem_nao_exibe_pacotes_de_outra_clinica(self):
        pacote_local = self.criar_pacote()

        Pacote.objects.create(
            clinica=self.clinica_externa,
            cliente=self.cliente_externo,
            servico=self.servico_externo,
            quantidade_sessoes=2,
            valor_total="150.00",
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ids = {str(item["id"]) for item in response.data}

        self.assertIn(str(pacote_local.id), ids)
        self.assertEqual(len(ids), 1)

    def test_detalhe_de_pacote_de_outra_clinica_nao_e_acessivel(self):
        pacote_externo = Pacote.objects.create(
            clinica=self.clinica_externa,
            cliente=self.cliente_externo,
            servico=self.servico_externo,
            quantidade_sessoes=2,
            valor_total="150.00",
        )

        response = self.client.get(
            f"{self.url}{pacote_externo.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cancelamento_exige_motivo(self):
        pacote = self.criar_pacote()
        SessaoPacote.objects.create(
            pacote=pacote,
            status=SessaoPacote.DISPONIVEL,
        )

        response = self.client.post(
            f"{self.url}{pacote.id}/cancelar/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        pacote.refresh_from_db()

        self.assertEqual(pacote.status, Pacote.ATIVO)

    def test_cancelamento_preserva_sessoes_utilizadas_e_perdidas(self):
        pacote = self.criar_pacote()

        sessao_disponivel = SessaoPacote.objects.create(
            pacote=pacote,
            status=SessaoPacote.DISPONIVEL,
        )
        sessao_agendada = SessaoPacote.objects.create(
            pacote=pacote,
            status=SessaoPacote.AGENDADA,
        )
        sessao_utilizada = SessaoPacote.objects.create(
            pacote=pacote,
            status=SessaoPacote.UTILIZADA,
        )
        sessao_perdida = SessaoPacote.objects.create(
            pacote=pacote,
            status=SessaoPacote.PERDIDA,
        )

        response = self.client.post(
            f"{self.url}{pacote.id}/cancelar/",
            {"motivo": "Solicitação do cliente"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        pacote.refresh_from_db()
        sessao_disponivel.refresh_from_db()
        sessao_agendada.refresh_from_db()
        sessao_utilizada.refresh_from_db()
        sessao_perdida.refresh_from_db()

        self.assertEqual(pacote.status, Pacote.CANCELADO)
        self.assertEqual(
            sessao_disponivel.status,
            SessaoPacote.CANCELADA,
        )
        self.assertEqual(
            sessao_agendada.status,
            SessaoPacote.CANCELADA,
        )
        self.assertEqual(
            sessao_utilizada.status,
            SessaoPacote.UTILIZADA,
        )
        self.assertEqual(
            sessao_perdida.status,
            SessaoPacote.PERDIDA,
        )

        self.assertEqual(
            HistoricoSessao.objects.filter(
                sessao__in=[sessao_disponivel, sessao_agendada],
                estado_novo=SessaoPacote.CANCELADA,
            ).count(),
            2,
        )

        auditoria = Auditoria.objects.get(
            clinica=self.clinica,
            entidade="Pacote",
            objeto_id=str(pacote.id),
            acao=Auditoria.DEACTIVATE,
        )

        self.assertEqual(
            auditoria.dados_novos["motivo"],
            "Solicitação do cliente",
        )
        self.assertEqual(
            auditoria.dados_anteriores["status"],
            Pacote.ATIVO,
        )

    def test_cancelamento_cancela_agendamentos_pendentes_e_confirmados(self):
        pacote = self.criar_pacote()
        inicio = timezone.now() + timedelta(days=2)

        agendamento_pendente = Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=Colaborador.objects.get(
                usuario=self.admin,
                clinica=self.clinica,
            ),
            servico=self.servico,
            pacote_origem=pacote,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=Agendamento.PENDENTE,
        )

        agendamento_confirmado = Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=Colaborador.objects.get(
                usuario=self.admin,
                clinica=self.clinica,
            ),
            servico=self.servico,
            pacote_origem=pacote,
            data_hora_inicio=inicio + timedelta(hours=1),
            data_hora_fim=inicio + timedelta(hours=1, minutes=30),
            status=Agendamento.CONFIRMADO,
        )

        response = self.client.post(
            f"{self.url}{pacote.id}/cancelar/",
            {"motivo": "Cancelamento solicitado"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        agendamento_pendente.refresh_from_db()
        agendamento_confirmado.refresh_from_db()

        self.assertEqual(
            agendamento_pendente.status,
            Agendamento.CANCELADO,
        )
        self.assertEqual(
            agendamento_confirmado.status,
            Agendamento.CANCELADO,
        )
        self.assertEqual(
            agendamento_pendente.motivo_cancelamento,
            "PACOTE_CANCELADO",
        )

    def test_cancelamento_nao_altera_agendamento_concluido_ou_com_falta(self):
        pacote = self.criar_pacote()
        inicio = timezone.now() + timedelta(days=3)

        agendamento_concluido = Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=Colaborador.objects.get(
                usuario=self.admin,
                clinica=self.clinica,
            ),
            servico=self.servico,
            pacote_origem=pacote,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=Agendamento.CONCLUIDO,
            resultado=Agendamento.REALIZADO,
        )

        agendamento_falta = Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=Colaborador.objects.get(
                usuario=self.admin,
                clinica=self.clinica,
            ),
            servico=self.servico,
            pacote_origem=pacote,
            data_hora_inicio=inicio + timedelta(hours=1),
            data_hora_fim=inicio + timedelta(hours=1, minutes=30),
            status=Agendamento.CONFIRMADO,
            resultado=Agendamento.FALTA,
        )

        response = self.client.post(
            f"{self.url}{pacote.id}/cancelar/",
            {"motivo": "Cancelamento solicitado"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

        agendamento_concluido.refresh_from_db()
        agendamento_falta.refresh_from_db()

        self.assertEqual(
            agendamento_concluido.status,
            Agendamento.CONCLUIDO,
        )
        self.assertEqual(
            agendamento_concluido.resultado,
            Agendamento.REALIZADO,
        )
        self.assertEqual(
            agendamento_falta.status,
            Agendamento.CONFIRMADO,
        )
        self.assertEqual(
            agendamento_falta.resultado,
            Agendamento.FALTA,
        )

    def test_cancelamento_nao_pode_ser_repetido(self):
        pacote = self.criar_pacote()

        primeira_resposta = self.client.post(
            f"{self.url}{pacote.id}/cancelar/",
            {"motivo": "Cancelamento inicial"},
            format="json",
        )

        segunda_resposta = self.client.post(
            f"{self.url}{pacote.id}/cancelar/",
            {"motivo": "Tentativa repetida"},
            format="json",
        )

        self.assertEqual(
            primeira_resposta.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            segunda_resposta.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Auditoria.objects.filter(
                clinica=self.clinica,
                entidade="Pacote",
                objeto_id=str(pacote.id),
                acao=Auditoria.DEACTIVATE,
            ).count(),
            1,
        )

    def test_exclusao_fisica_de_pacote_e_bloqueada(self):
        pacote = self.criar_pacote()

        response = self.client.delete(
            f"{self.url}{pacote.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertTrue(
            Pacote.objects.filter(pk=pacote.pk).exists()
        )

    def test_usuario_sem_vinculo_na_clinica_nao_acessa_pacotes(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=self.client._credentials.get(
                "HTTP_AUTHORIZATION", ""
            )
        )

        self.client.credentials(
            HTTP_AUTHORIZATION="",
            HTTP_X_CLINICA_ID=str(self.clinica_externa.id),
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
