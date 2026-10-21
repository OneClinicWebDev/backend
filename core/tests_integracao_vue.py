from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
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


class IntegracaoFrontendTestCase(TestCase):
    """
    Contrato usado pelo frontend: login, vínculos, clínica ativa por
    X-Clinica-ID e listagem da agenda.
    """

    SENHA = "SenhaForte123"
    URL_AGENDA = "/api/agendamentos/"

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.role_admin = Role.objects.get_or_create(nome=Role.ADMIN)[0]

        self.clinica = Clinica.objects.create(
            cnpj="11222333000181",
            razao_social="Clinica Integracao",
            nome_fantasia="Clinica Integracao",
            telefone="47999990000",
        )
        self.usuario_admin = Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Admin Integracao",
            data_nascimento="1990-01-01",
            password=self.SENHA,
        )
        self.admin = Colaborador.objects.create(
            usuario=self.usuario_admin,
            clinica=self.clinica,
            role=self.role_admin,
            ativo=True,
        )
        self.usuario_cliente = Usuario.objects.create_user(
            cpf="11144477735",
            nome_completo="Cliente Integracao",
            data_nascimento="1995-05-20",
            password=self.SENHA,
        )
        self.cliente = Cliente.objects.create(
            usuario=self.usuario_cliente,
            clinica=self.clinica,
            telefone="47988880000",
        )
        self.servico = Servico.objects.create(
            clinica=self.clinica,
            nome="Servico Integracao",
            duracao_padrao_minutos=30,
        )

    def login(self):
        response = self.client.post(
            "/api/auth/login/",
            {"cpf": self.usuario_admin.cpf, "password": self.SENHA},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )
        return response.data

    def autenticar(self, clinica_id=None):
        dados = self.login()
        credenciais = {"HTTP_AUTHORIZATION": f"Bearer {dados['access']}"}

        if clinica_id is not None:
            credenciais["HTTP_X_CLINICA_ID"] = str(clinica_id)

        self.client.credentials(**credenciais)
        return dados

    def agendar(self, dia, hora, status_agendamento=Agendamento.CONFIRMADO):
        inicio = timezone.make_aware(datetime.combine(dia, time(hora, 0)))

        return Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.admin,
            servico=self.servico,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=status_agendamento,
        )

    def ids_da_agenda(self, **parametros):
        response = self.client.get(self.URL_AGENDA, parametros)
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )
        return [item["id"] for item in response.data]

    # Login e vínculos

    def test_login_devolve_vinculo_da_clinica_ativa(self):
        dados = self.login()

        self.assertEqual(dados["usuario"]["cpf"], self.usuario_admin.cpf)
        self.assertEqual(len(dados["vinculos"]), 1)
        self.assertEqual(
            dados["vinculos"][0]["clinica_id"],
            str(self.clinica.pk),
        )
        self.assertEqual(dados["vinculos"][0]["role"], Role.ADMIN)

    def test_login_ignora_token_invalido_no_cabecalho(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer token-vencido")

        response = self.client.post(
            "/api/auth/login/",
            {"cpf": self.usuario_admin.cpf, "password": self.SENHA},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_nao_lista_clinica_inativa(self):
        self.clinica.ativo = False
        self.clinica.save(update_fields=["ativo"])

        dados = self.login()

        self.assertEqual(dados["vinculos"], [])

    def test_me_exige_autenticacao(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_devolve_usuario_e_vinculos_sem_clinica_ativa(self):
        self.autenticar()

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["usuario"]["cpf"],
            self.usuario_admin.cpf,
        )
        self.assertEqual(
            [v["clinica_id"] for v in response.data["vinculos"]],
            [str(self.clinica.pk)],
        )

    # Clínica ativa e isolamento

    def test_agenda_exige_token(self):
        response = self.client.get(self.URL_AGENDA)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_agenda_sem_cabecalho_de_clinica_retorna_403(self):
        self.autenticar()

        response = self.client.get(self.URL_AGENDA)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cabecalho_de_clinica_malformado_retorna_403(self):
        self.autenticar(clinica_id="isto-nao-e-um-uuid")

        response = self.client.get(self.URL_AGENDA)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_clinica_sem_vinculo_retorna_403(self):
        outra = Clinica.objects.create(
            cnpj="45997418000153",
            razao_social="Outra Clinica",
            nome_fantasia="Outra Clinica",
            telefone="47977770000",
        )
        self.autenticar(clinica_id=outra.pk)

        response = self.client.get(self.URL_AGENDA)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_agenda_lista_somente_dados_da_clinica_ativa(self):
        dia = timezone.localdate() + timedelta(days=10)
        propria = self.agendar(dia, 10)

        outra = Clinica.objects.create(
            cnpj="45997418000153",
            razao_social="Outra Clinica",
            nome_fantasia="Outra Clinica",
            telefone="47977770000",
        )
        usuario_outro = Usuario.objects.create_user(
            cpf="39053344705",
            nome_completo="Admin Outra Clinica",
            data_nascimento="1985-03-10",
            password=self.SENHA,
        )
        admin_outro = Colaborador.objects.create(
            usuario=usuario_outro,
            clinica=outra,
            role=self.role_admin,
            ativo=True,
        )
        cliente_outro = Cliente.objects.create(
            usuario=usuario_outro,
            clinica=outra,
            telefone="47966660000",
        )
        servico_outro = Servico.objects.create(
            clinica=outra,
            nome="Servico Outra Clinica",
            duracao_padrao_minutos=30,
        )
        inicio = timezone.make_aware(datetime.combine(dia, time(10, 0)))
        alheia = Agendamento.objects.create(
            clinica=outra,
            cliente=cliente_outro,
            profissional=admin_outro,
            servico=servico_outro,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=Agendamento.CONFIRMADO,
        )

        self.autenticar(clinica_id=self.clinica.pk)

        ids = self.ids_da_agenda()

        self.assertEqual(ids, [propria.pk])
        self.assertNotIn(alheia.pk, ids)

    # Filtros da listagem

    def test_listagem_ordenada_por_inicio(self):
        dia = timezone.localdate() + timedelta(days=10)
        depois = self.agendar(dia + timedelta(days=2), 10)
        antes = self.agendar(dia, 10)
        self.autenticar(clinica_id=self.clinica.pk)

        self.assertEqual(self.ids_da_agenda(), [antes.pk, depois.pk])

    def test_filtro_por_periodo_inclui_o_dia_final(self):
        dia = timezone.localdate() + timedelta(days=10)
        primeiro = self.agendar(dia, 10)
        segundo = self.agendar(dia + timedelta(days=2), 10)
        self.autenticar(clinica_id=self.clinica.pk)

        self.assertEqual(
            self.ids_da_agenda(
                data_inicio=dia.isoformat(),
                data_fim=dia.isoformat(),
            ),
            [primeiro.pk],
        )
        self.assertEqual(
            self.ids_da_agenda(
                data_inicio=(dia + timedelta(days=1)).isoformat(),
            ),
            [segundo.pk],
        )

    def test_filtro_por_status_e_profissional(self):
        dia = timezone.localdate() + timedelta(days=10)
        confirmado = self.agendar(dia, 10)
        cancelado = self.agendar(dia, 12, Agendamento.CANCELADO)
        self.autenticar(clinica_id=self.clinica.pk)

        self.assertEqual(
            self.ids_da_agenda(status=Agendamento.CONFIRMADO),
            [confirmado.pk],
        )
        self.assertEqual(
            self.ids_da_agenda(profissional=str(self.admin.pk)),
            [confirmado.pk, cancelado.pk],
        )

    def test_filtros_invalidos_retornam_400(self):
        self.autenticar(clinica_id=self.clinica.pk)

        for parametros in (
            {"data_inicio": "ontem"},
            {"data_fim": "2026-13-45"},
            {"profissional": "abc"},
            {"cliente": "abc"},
            {"status": "FALTA"},
        ):
            with self.subTest(parametros=parametros):
                response = self.client.get(self.URL_AGENDA, parametros)

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    getattr(response, "data", None),
                )

    # Cadastros duplicados na mesma clínica

    def test_cliente_duplicado_na_mesma_clinica_retorna_400(self):
        self.autenticar(clinica_id=self.clinica.pk)

        response = self.client.post(
            "/api/clientes/",
            {
                "usuario": str(self.usuario_cliente.pk),
                "telefone": "(47) 99999-0000",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )
        self.assertEqual(
            Cliente.objects.filter(
                usuario=self.usuario_cliente,
                clinica=self.clinica,
            ).count(),
            1,
        )

    def test_colaborador_duplicado_na_mesma_clinica_retorna_400(self):
        self.autenticar(clinica_id=self.clinica.pk)

        response = self.client.post(
            "/api/colaboradores/",
            {
                "usuario": str(self.usuario_admin.pk),
                "role": self.role_admin.pk,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            getattr(response, "data", None),
        )
        self.assertEqual(
            Colaborador.objects.filter(
                usuario=self.usuario_admin,
                clinica=self.clinica,
            ).count(),
            1,
        )