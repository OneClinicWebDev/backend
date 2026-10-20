from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Clinica, Usuario, Role, Colaborador


class SecurityTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.clinica1 = Clinica.objects.create(
            cnpj="48545800000100",
            razao_social="Clinica A",
            nome_fantasia="A",
            telefone="11999999999",
        )

        self.user1 = Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Admin A",
            data_nascimento="1990-01-01",
            password="SenhaForte123",
        )

        self.role_admin = Role.objects.create(nome=Role.ADMIN)

        self.colaborador1 = Colaborador.objects.create(
            usuario=self.user1,
            clinica=self.clinica1,
            role=self.role_admin,
            ativo=True,
        )

        self.clinica2 = Clinica.objects.create(
            cnpj="92135061000155",
            razao_social="Clinica B",
            nome_fantasia="B",
            telefone="11999999999",
        )

        self.login_url = "/api/token/"
        self.logout_url = "/api/auth/logout/"
        self.refresh_url = "/api/token/refresh/"
        self.clientes_url = "/api/clientes/"

    def obter_tokens(self, cpf=None, password="SenhaForte123"):
        response = self.client.post(
            self.login_url,
            {
                "cpf": cpf or self.user1.cpf,
                "password": password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        return response.data["access"], response.data["refresh"]

    def autenticar_na_clinica(self, access_token, clinica_id):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
            HTTP_X_CLINICA_ID=str(clinica_id),
        )

    def test_login_retorna_tokens(self):
        access, refresh = self.obter_tokens()

        self.assertTrue(access)
        self.assertTrue(refresh)

    def test_login_usuario_inativo_e_negado(self):
        self.user1.is_active = False
        self.user1.save(update_fields=["is_active"])

        response = self.client.post(
            self.login_url,
            {
                "cpf": self.user1.cpf,
                "password": "SenhaForte123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            response.data,
        )

    def test_acesso_propria_clinica_com_jwt(self):
        access, _ = self.obter_tokens()

        self.autenticar_na_clinica(access, self.clinica1.id)

        response = self.client.get(self.clientes_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

    def test_acesso_negado_clinica_isolada(self):
        access, _ = self.obter_tokens()

        self.autenticar_na_clinica(access, self.clinica2.id)

        response = self.client.get(self.clientes_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            getattr(response, "data", None),
        )

    def test_acesso_sem_clinica_selecionada_e_negado(self):
        access, _ = self.obter_tokens()

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

        response = self.client.get(self.clientes_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            getattr(response, "data", None),
        )

    def test_logout_invalida_refresh_token(self):
        access, refresh = self.obter_tokens()

        self.autenticar_na_clinica(access, self.clinica1.id)

        response_antes = self.client.get(self.clientes_url)

        self.assertEqual(
            response_antes.status_code,
            status.HTTP_200_OK,
            getattr(response_antes, "data", None),
        )

        logout_response = self.client.post(
            self.logout_url,
            {"refresh": refresh},
            format="json",
        )

        self.assertEqual(
            logout_response.status_code,
            status.HTTP_205_RESET_CONTENT,
            logout_response.data,
        )

        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": refresh},
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            refresh_response.data,
        )

    def test_logout_nao_invalida_refresh_de_outro_usuario(self):
        _, refresh = self.obter_tokens()

        outro_usuario = Usuario.objects.create_user(
            cpf="11144477735",
            nome_completo="Outro Usuario",
            data_nascimento="1992-02-02",
            password="OutraSenha123",
        )

        self.client.force_authenticate(user=outro_usuario)

        response = self.client.post(
            self.logout_url,
            {"refresh": refresh},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
        )

        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": refresh},
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_200_OK,
            refresh_response.data,
        )
