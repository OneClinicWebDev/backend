
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache

from core.models import (
    Usuario,
    Clinica,
    Colaborador,
    Role,
    Auditoria,
)


class CadastroClinicaTestCase(APITestCase):
    url = "/api/auth/criar-clinica/"
    senha = "Senha!Fortissima2026Azul"

    def setUp(self):
        cache.clear()
        Role.objects.get_or_create(nome=Role.ADMIN)

    def payload(self, **overrides):
        data = {
            "cpf": "52998224725",
            "nome_completo": "Administrador Teste",
            "data_nascimento": "1990-01-15",
            "password": self.senha,
            "cnpj": "11222333000181",
            "razao_social": "Clinica Teste LTDA",
            "nome_fantasia": "Clinica Teste",
            "telefone": "47999999999",
            "profissionais_podem_editar_agenda": False,
        }
        data.update(overrides)
        return data

    def test_cadastro_cria_clinica_e_primeiro_admin(self):
        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        clinica = Clinica.objects.get(
            id=response.data["clinica_id"]
        )
        usuario = Usuario.objects.get(
            id=response.data["usuario_id"]
        )

        colaborador = Colaborador.objects.get(
            usuario=usuario,
            clinica=clinica,
        )

        self.assertEqual(colaborador.role.nome, Role.ADMIN)
        self.assertTrue(colaborador.ativo)
        self.assertTrue(colaborador.pode_editar_agenda)

        self.assertTrue(
            Auditoria.objects.filter(
                clinica=clinica,
                acao="CREATE",
                entidade="Clinica",
            ).exists()
        )

        self.assertEqual(Clinica.objects.count(), 1)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(Colaborador.objects.count(), 1)

    def test_rejeita_cpf_invalido(self):
        response = self.client.post(
            self.url,
            self.payload(cpf="11111111111"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Clinica.objects.count(), 0)
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Colaborador.objects.count(), 0)

    def test_rejeita_cnpj_invalido(self):
        response = self.client.post(
            self.url,
            self.payload(cnpj="00000000000000"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Clinica.objects.count(), 0)
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Colaborador.objects.count(), 0)

    def test_rejeita_cnpj_ja_cadastrado(self):
        Clinica.objects.create(
            cnpj="11222333000181",
            razao_social="Outra Clinica LTDA",
            nome_fantasia="Outra Clinica",
            telefone="47988887777",
        )

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Clinica.objects.count(), 1)
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Colaborador.objects.count(), 0)

    def test_usuario_existente_pode_criar_outra_clinica(self):
        usuario = Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Administrador Existente",
            data_nascimento="1990-01-15",
            password=self.senha,
        )

        response = self.client.post(
            self.url,
            self.payload(
                cnpj="11444777000161",
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(Clinica.objects.count(), 1)
        self.assertEqual(Colaborador.objects.count(), 1)

        colaborador = Colaborador.objects.get(
            usuario=usuario,
        )
        self.assertEqual(colaborador.role.nome, Role.ADMIN)

    def test_senha_incorreta_nao_cria_clinica(self):
        Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Administrador Existente",
            data_nascimento="1990-01-15",
            password=self.senha,
        )

        response = self.client.post(
            self.url,
            self.payload(password="OutraSenha!2026Azul"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(Clinica.objects.count(), 0)
        self.assertEqual(Colaborador.objects.count(), 0)
