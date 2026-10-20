from rest_framework.test import APITestCase
from rest_framework import status

from core.models import Usuario, Clinica, Colaborador, Role


class SecurityTestCase(APITestCase):
    def setUp(self):
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

        role_admin = Role.objects.create(nome=Role.ADMIN)

        Colaborador.objects.create(
            usuario=self.user1,
            clinica=self.clinica1,
            role=role_admin,
            ativo=True,
        )

        self.clinica2 = Clinica.objects.create(
            cnpj="92135061000155",
            razao_social="Clinica B",
            nome_fantasia="B",
            telefone="11999999999",
        )

        self.login_url = "/api/token/"
        self.logout_url = "/api/token/blacklist/"
        self.refresh_url = "/api/token/refresh/"
        self.clientes_url = "/api/clientes/"

    def obter_tokens(self):
        response = self.client.post(
            self.login_url,
            {
                "cpf": "52998224725",
                "password": "SenhaForte123",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        return response.data

    def autenticar_na_clinica(self, access_token, clinica_id):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
            HTTP_X_CLINICA_ID=str(clinica_id),
        )

    def test_login_retorna_tokens(self):
        tokens = self.obter_tokens()

        self.assertTrue(tokens["access"])
        self.assertTrue(tokens["refresh"])

    def test_acesso_propria_clinica_com_jwt(self):
        tokens = self.obter_tokens()

        self.autenticar_na_clinica(
            tokens["access"],
            self.clinica1.id,
        )

        response = self.client.get(self.clientes_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            getattr(response, "data", None),
        )

    def test_acesso_negado_clinica_isolada(self):
        tokens = self.obter_tokens()

        self.autenticar_na_clinica(
            tokens["access"],
            self.clinica2.id,
        )

        response = self.client.get(self.clientes_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_acesso_sem_clinica_selecionada_e_negado(self):
        tokens = self.obter_tokens()

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )

        response = self.client.get(self.clientes_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_logout_invalida_refresh_token(self):
        tokens = self.obter_tokens()

        self.autenticar_na_clinica(
            tokens["access"],
            self.clinica1.id,
        )

        response_antes = self.client.get(self.clientes_url)

        self.assertEqual(
            response_antes.status_code,
            status.HTTP_200_OK,
            getattr(response_antes, "data", None),
        )

        logout_response = self.client.post(
            self.logout_url,
            {"refresh": tokens["refresh"]},
        )

        self.assertEqual(
            logout_response.status_code,
            status.HTTP_200_OK,
        )

        self.client.credentials()

        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
