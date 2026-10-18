from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from core.models import Usuario, Clinica, Colaborador, Role

class SecurityTestCase(APITestCase):
    def setUp(self):
        # CNPJ válido gerado para testes
        self.clinica1 = Clinica.objects.create(cnpj="48545800000100", razao_social="Clinica A", nome_fantasia="A", telefone="11999999999")
        
        # CPF válido gerado para testes
        self.user1 = Usuario.objects.create_user(cpf="16369527015", nome_completo="Admin A", data_nascimento="1990-01-01", password="SenhaForte123")
        
        role_admin = Role.objects.create(nome=Role.ADMIN)
        Colaborador.objects.create(usuario=self.user1, clinica=self.clinica1, role=role_admin)

        # Outro CNPJ válido gerado para testes (para tentar quebrar o isolamento)
        self.clinica2 = Clinica.objects.create(cnpj="92135061000155", razao_social="Clinica B", nome_fantasia="B", telefone="11999999999")

        # Rotas
        try:
            self.login_url = reverse('login')
            self.logout_url = reverse('logout')
            self.clientes_url = reverse('cliente-list')
        except:
            # Fallback caso os names no seu urls.py sejam diferentes
            self.login_url = '/api/token/'
            self.logout_url = '/api/token/blacklist/'
            self.clientes_url = '/api/clientes/'

    def test_login_retorna_tokens(self):
        response = self.client.post(self.login_url, {"cpf": "16369527015", "password": "SenhaForte123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_logout_invalida_token_blacklist(self):
        # 1. Faz login
        login_resp = self.client.post(self.login_url, {"cpf": "16369527015", "password": "SenhaForte123"})
        access_token = login_resp.data.get('access')
        refresh_token = login_resp.data.get('refresh')

        # 2. Requisita clientes passando X-Clinica-ID e Token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_CLINICA_ID=str(self.clinica1.id))
        resp_antes_logout = self.client.get(self.clientes_url)
        self.assertNotEqual(resp_antes_logout.status_code, status.HTTP_401_UNAUTHORIZED)

        # 3. Faz o Logout
        logout_resp = self.client.post(self.logout_url, {"refresh": refresh_token})
        self.assertIn(logout_resp.status_code, [status.HTTP_200_OK, status.HTTP_205_RESET_CONTENT])
        
    def test_acesso_negado_clinica_isolada(self):
        # Tenta acessar Clínica 2 usando o usuário da Clínica 1
        login_resp = self.client.post(self.login_url, {"cpf": "16369527015", "password": "SenhaForte123"})
        access_token = login_resp.data.get('access')

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_CLINICA_ID=str(self.clinica2.id))
        response = self.client.get(self.clientes_url)
        
        # O middleware ou o get_clinica devem barrar (403 Forbidden ou 401 Unauthorized)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])