from django.contrib import admin
from django.test import RequestFactory
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError


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

class AuditoriaImutabilidadeTestCase(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Usuario Teste",
            data_nascimento="1990-01-15",
            password="Senha!Fortissima2026Azul",
)

        self.clinica = Clinica.objects.create(
            razao_social="Clinica Auditoria LTDA",
            nome_fantasia="Clinica Auditoria",
            cnpj="11222333000181",
            telefone="47999999999",
        )

        self.auditoria = Auditoria.objects.create(
            clinica=self.clinica,
            usuario=self.usuario,
            acao=Auditoria.CREATE,
            entidade="Clinica",
            objeto_id=str(self.clinica.pk),
            dados_novos={"nome_fantasia": "Clinica Auditoria"},
        )

    def test_impede_alteracao_de_registro_existente(self):
        self.auditoria.entidade = "Alterada"

        with self.assertRaises(ValidationError):
            self.auditoria.save()

        self.auditoria.refresh_from_db()
        self.assertEqual(self.auditoria.entidade, "Clinica")

    def test_impede_exclusao_individual(self):
        with self.assertRaises(ValidationError):
            self.auditoria.delete()

        self.assertTrue(
            Auditoria.objects.filter(pk=self.auditoria.pk).exists()
        )

    def test_impede_atualizacao_em_lote(self):
        with self.assertRaises(ValidationError):
            Auditoria.objects.filter(
                pk=self.auditoria.pk
            ).update(entidade="Alterada")

        self.auditoria.refresh_from_db()
        self.assertEqual(self.auditoria.entidade, "Clinica")

    def test_impede_exclusao_em_lote(self):
        with self.assertRaises(ValidationError):
            Auditoria.objects.filter(
                pk=self.auditoria.pk
            ).delete()

        self.assertTrue(
            Auditoria.objects.filter(pk=self.auditoria.pk).exists()
        )

    def test_impede_exclusao_de_clinica_com_auditoria(self):
        with self.assertRaises(ProtectedError):
            self.clinica.delete()

        self.assertTrue(
            Auditoria.objects.filter(pk=self.auditoria.pk).exists()
        )    
class AdminExclusaoProtegidaTestCase(TestCase):
    def test_modelos_core_bloqueiam_exclusao_no_admin(self):
        request = RequestFactory().get("/admin/")

        modelos_core = [
            model
            for model in admin.site._registry
            if model.__module__.startswith("core.models")
        ]

        self.assertTrue(
            modelos_core,
            "Nenhum modelo de core foi encontrado no Django Admin.",
        )

        for model in modelos_core:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]

                self.assertFalse(
                    model_admin.has_delete_permission(request),
                    f"{model.__name__} permite exclusão pelo Django Admin.",
                )        