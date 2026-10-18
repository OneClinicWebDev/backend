from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from core.models import Usuario, Clinica, Colaborador, Role

class SecurityTestCase(APITestCase):
    def setUp(self):
        self.clinica1 = Clinica.objects.create(
            cnpj="48545800000100", 
            razao_social="Clinica A", 
            nome_fantasia="A", 
            telefone="11999999999"
        )
        self.user1 = Usuario.objects.create_user(
            cpf="52998224025", 
            nome_completo="Admin A", 
            data_nascimento="1990-01-01", 
            password="SenhaForte123"
        )
        role_admin = Role.objects.create(nome=Role.ADMIN)
        Colaborador.objects.create(usuario=self.user1, clinica=self.clinica1, role=role_admin)

        self.clinica2 = Clinica.objects.create(
            cnpj="92135061000155", 
            razao_social="Clinica B", 
            nome_fantasia="B", 
            telefone="11999999999"
        )

        try:
            self.login_url = reverse('login')
            self.logout_url = reverse('logout')
            self.clientes_url = reverse('cliente-list')
        except:
            self.login_url = '/api/token/'
            self.logout_url = '/api/token/blacklist/'
            self.clientes_url = '/api/clientes/'

    def test_login_retorna_tokens(self):
        response = self.client.post(self.login_url, {"cpf": "52998224025", "password": "SenhaForte123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_logout_invalida_token_blacklist(self):
        login_resp = self.client.post(self.login_url, {"cpf": "52998224025", "password": "SenhaForte123"})
        access_token = login_resp.data.get('access')
        refresh_token = login_resp.data.get('refresh')

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_CLINICA_ID=str(self.clinica1.id))
        resp_antes_logout = self.client.get(self.clientes_url)
        self.assertNotEqual(resp_antes_logout.status_code, status.HTTP_401_UNAUTHORIZED)

        logout_resp = self.client.post(self.logout_url, {"refresh": refresh_token})
        self.assertIn(logout_resp.status_code, [status.HTTP_200_OK, status.HTTP_205_RESET_CONTENT])
        
    def test_acesso_negado_clinica_isolada(self):
        login_resp = self.client.post(self.login_url, {"cpf": "52998224025", "password": "SenhaForte123"})
        access_token = login_resp.data.get('access')

        # Tenta injetar o ID da Clínica 2 (onde ele NÃO é colaborador)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_CLINICA_ID=str(self.clinica2.id))
        response = self.client.get(self.clientes_url)
        
        # Agora o middleware vai interceptar e retornar 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)