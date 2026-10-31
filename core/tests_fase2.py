from datetime import timedelta
from decimal import Decimal

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
    HistoricoSessao,
    Pacote,
    Role,
    Servico,
    SessaoPacote,
    Usuario,
)


SENHA = "SenhaForte123"


class BaseFase2(TestCase):
    def setUp(self):
        cache.clear()

        self.clinica = Clinica.objects.create(
            cnpj="48545800000100",
            razao_social="Clinica Teste",
            nome_fantasia="Clinica Teste",
            telefone="11999999999",
            profissionais_podem_editar_agenda=True,
        )

        self.role_admin = Role.objects.get_or_create(nome=Role.ADMIN)[0]
        self.role_prof = Role.objects.get_or_create(nome=Role.PROFISSIONAL)[0]

        self.usuario_admin = Usuario.objects.create_user(
            cpf="52998224725",
            nome_completo="Admin Teste",
            data_nascimento="1990-01-01",
            password=SENHA,
        )
        self.admin = Colaborador.objects.create(
            usuario=self.usuario_admin,
            clinica=self.clinica,
            role=self.role_admin,
            ativo=True,
        )

        self.usuario_prof = Usuario.objects.create_user(
            cpf="11144477735",
            nome_completo="Profissional Teste",
            data_nascimento="1992-02-02",
            password=SENHA,
        )
        self.profissional = Colaborador.objects.create(
            usuario=self.usuario_prof,
            clinica=self.clinica,
            role=self.role_prof,
            ativo=True,
            pode_editar_agenda=True,
        )

        self.usuario_cliente = Usuario.objects.create_user(
            cpf="22233344405",
            nome_completo="Cliente Teste",
            data_nascimento="1995-03-03",
            password=SENHA,
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
            preco=Decimal("100.00"),
        )

        self.inicio = (
            timezone.now() + timedelta(days=10)
        ).replace(second=0, microsecond=0)
        self.fim = self.inicio + timedelta(minutes=30)

    def autenticar(self, usuario):
        client = APIClient()
        resposta = client.post(
            "/api/token/",
            {"cpf": usuario.cpf, "password": SENHA},
            format="json",
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {resposta.data['access']}",
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )
        return client

    def criar_pacote(self, quantidade=2):
        pacote = Pacote.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            servico=self.servico,
            quantidade_sessoes=quantidade,
            valor_total=Decimal("150.00"),
            status=Pacote.ATIVO,
        )

        for _ in range(quantidade):
            SessaoPacote.objects.create(
                pacote=pacote,
                status=SessaoPacote.DISPONIVEL,
            )

        return pacote

    def payload(self, **extra):
        dados = {
            "cliente": str(self.cliente.pk),
            "profissional": str(self.profissional.pk),
            "servico": self.servico.pk,
            "data_hora_inicio": self.inicio.isoformat(),
            "data_hora_fim": self.fim.isoformat(),
        }
        dados.update(extra)
        return dados


class PrecoAcordadoTests(BaseFase2):
    def test_cria_com_preco_acordado_sem_alterar_servico(self):
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            "/api/agendamentos/",
            self.payload(preco_acordado="80.50"),
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(resposta.data["preco_acordado"], "80.50")
        self.assertEqual(resposta.data["servico_preco"], "100.00")

        self.servico.refresh_from_db()
        self.assertEqual(self.servico.preco, Decimal("100.00"))

    def test_preco_negativo_retorna_400(self):
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            "/api/agendamentos/",
            self.payload(preco_acordado="-1"),
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("preco_acordado", resposta.data)

    def test_preco_pode_ser_nulo_e_editado(self):
        client = self.autenticar(self.usuario_admin)

        criado = client.post(
            "/api/agendamentos/",
            self.payload(),
            format="json",
        )
        self.assertEqual(criado.status_code, status.HTTP_201_CREATED, criado.data)
        self.assertIsNone(criado.data["preco_acordado"])

        editado = client.patch(
            f"/api/agendamentos/{criado.data['id']}/",
            {"preco_acordado": "55.00"},
            format="json",
        )
        self.assertEqual(editado.status_code, status.HTTP_200_OK, editado.data)
        self.assertEqual(editado.data["preco_acordado"], "55.00")


class PermissoesProfissionalTests(BaseFase2):
    def test_profissional_com_autonomia_le_cadastros(self):
        client = self.autenticar(self.usuario_prof)

        for rota in (
            "/api/clientes/",
            "/api/colaboradores/",
            "/api/servicos/",
            "/api/pacotes/",
        ):
            resposta = client.get(rota)
            self.assertEqual(resposta.status_code, status.HTTP_200_OK, rota)

    def test_profissional_sem_permissao_individual_recebe_403(self):
        self.profissional.pode_editar_agenda = False
        self.profissional.save(update_fields=["pode_editar_agenda"])

        client = self.autenticar(self.usuario_prof)

        self.assertEqual(
            client.get("/api/clientes/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_profissional_sem_autonomia_da_clinica_recebe_403(self):
        self.clinica.profissionais_podem_editar_agenda = False
        self.clinica.save(update_fields=["profissionais_podem_editar_agenda"])

        client = self.autenticar(self.usuario_prof)

        self.assertEqual(
            client.get("/api/servicos/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_profissional_nao_escreve_em_cadastros(self):
        client = self.autenticar(self.usuario_prof)

        resposta = client.post(
            "/api/servicos/",
            {"nome": "Novo", "duracao_padrao_minutos": 20, "preco": "10.00"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_expoe_colaborador_id_e_autonomia(self):
        client = self.autenticar(self.usuario_prof)

        resposta = client.get("/api/auth/me/")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        vinculo = resposta.data["vinculos"][0]
        self.assertEqual(vinculo["colaborador_id"], str(self.profissional.pk))
        self.assertTrue(vinculo["profissionais_podem_editar_agenda"])
        self.assertTrue(vinculo["pode_editar_agenda"])


class ReservaSessaoTests(BaseFase2):
    def test_criar_com_pacote_reserva_sessao(self):
        pacote = self.criar_pacote()
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            "/api/agendamentos/",
            self.payload(pacote_origem=pacote.pk),
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(
            SessaoPacote.objects.filter(
                pacote=pacote,
                status=SessaoPacote.AGENDADA,
                agendamento_id=resposta.data["id"],
            ).count(),
            1,
        )
        self.assertEqual(resposta.data["sessao_pacote_status"], SessaoPacote.AGENDADA)
        self.assertTrue(
            HistoricoSessao.objects.filter(
                estado_novo=SessaoPacote.AGENDADA,
                agendamento_relacionado_id=resposta.data["id"],
            ).exists()
        )

    def test_pacote_sem_sessao_disponivel_retorna_400_sem_criar(self):
        pacote = self.criar_pacote(quantidade=1)
        SessaoPacote.objects.filter(pacote=pacote).update(
            status=SessaoPacote.UTILIZADA
        )
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            "/api/agendamentos/",
            self.payload(pacote_origem=pacote.pk),
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Agendamento.objects.exists())

    def test_cancelar_libera_sessao_reservada(self):
        pacote = self.criar_pacote()
        client = self.autenticar(self.usuario_admin)

        criado = client.post(
            "/api/agendamentos/",
            self.payload(pacote_origem=pacote.pk),
            format="json",
        )

        resposta = client.post(
            f"/api/agendamentos/{criado.data['id']}/cancelar/",
            {"motivo": "Cliente desistiu"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertEqual(
            SessaoPacote.objects.filter(
                pacote=pacote,
                status=SessaoPacote.DISPONIVEL,
            ).count(),
            2,
        )

    def test_falta_com_sessao_reservada_exige_decisao(self):
        pacote = self.criar_pacote()
        client = self.autenticar(self.usuario_admin)

        criado = client.post(
            "/api/agendamentos/",
            self.payload(pacote_origem=pacote.pk),
            format="json",
        )
        url = f"/api/agendamentos/{criado.data['id']}/registrar_falta/"

        sem_decisao = client.post(url, {}, format="json")
        self.assertEqual(sem_decisao.status_code, status.HTTP_400_BAD_REQUEST)

        com_decisao = client.post(
            url,
            {"decisao_sessao": "PRESERVAR"},
            format="json",
        )
        self.assertEqual(com_decisao.status_code, status.HTTP_200_OK, com_decisao.data)
        self.assertEqual(
            SessaoPacote.objects.filter(
                pacote=pacote,
                status=SessaoPacote.DISPONIVEL,
            ).count(),
            2,
        )


class FaltaAposConclusaoTests(BaseFase2):
    def criar_concluido(self, com_pacote=False):
        pacote = self.criar_pacote() if com_pacote else None
        agendamento = Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            pacote_origem=pacote,
            data_hora_inicio=self.inicio,
            data_hora_fim=self.fim,
            status=Agendamento.CONCLUIDO,
            resultado=Agendamento.REALIZADO,
        )
        sessao = None

        if pacote is not None:
            sessao = SessaoPacote.objects.filter(pacote=pacote).first()
            sessao.status = SessaoPacote.UTILIZADA
            sessao.agendamento = agendamento
            sessao.save()

        return agendamento, sessao

    def test_corrige_para_falta_exige_justificativa(self):
        agendamento, _ = self.criar_concluido()
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            f"/api/agendamentos/{agendamento.pk}/registrar_falta/",
            {},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("justificativa", resposta.data)

    def test_corrige_para_falta_sem_pacote(self):
        agendamento, _ = self.criar_concluido()
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            f"/api/agendamentos/{agendamento.pk}/registrar_falta/",
            {"justificativa": "Cliente não compareceu"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        agendamento.refresh_from_db()
        self.assertEqual(agendamento.status, Agendamento.CONCLUIDO)
        self.assertEqual(agendamento.resultado, Agendamento.FALTA)

    def test_corrige_para_falta_com_sessao_utilizada_exige_decisao(self):
        agendamento, sessao = self.criar_concluido(com_pacote=True)
        client = self.autenticar(self.usuario_admin)
        url = f"/api/agendamentos/{agendamento.pk}/registrar_falta/"

        sem_decisao = client.post(
            url,
            {"justificativa": "Cliente não compareceu"},
            format="json",
        )
        self.assertEqual(sem_decisao.status_code, status.HTTP_400_BAD_REQUEST)

        resposta = client.post(
            url,
            {
                "justificativa": "Cliente não compareceu",
                "decisao_sessao": "PERDER",
            },
            format="json",
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)

        sessao.refresh_from_db()
        self.assertEqual(sessao.status, SessaoPacote.PERDIDA)
        self.assertTrue(
            HistoricoSessao.objects.filter(
                sessao=sessao,
                estado_anterior=SessaoPacote.UTILIZADA,
                estado_novo=SessaoPacote.PERDIDA,
            ).exists()
        )

    def test_cancelado_nao_aceita_falta(self):
        agendamento, _ = self.criar_concluido()
        agendamento.status = Agendamento.CANCELADO
        agendamento.save(update_fields=["status"])
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            f"/api/agendamentos/{agendamento.pk}/registrar_falta/",
            {"justificativa": "x"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)


class PerfilEClinicaTests(BaseFase2):
    def test_perfil_atualiza_dados_sem_alterar_cpf(self):
        client = self.autenticar(self.usuario_admin)

        resposta = client.patch(
            "/api/auth/perfil/",
            {
                "nome_completo": "Admin Atualizado",
                "telefone": "(11) 97777-6666",
                "cpf": "00000000000",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.usuario_admin.refresh_from_db()
        self.assertEqual(self.usuario_admin.nome_completo, "Admin Atualizado")
        self.assertEqual(self.usuario_admin.telefone, "11977776666")
        self.assertEqual(self.usuario_admin.cpf, "52998224725")

    def test_perfil_rejeita_telefone_invalido(self):
        client = self.autenticar(self.usuario_admin)

        resposta = client.patch(
            "/api/auth/perfil/",
            {"telefone": "123"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_alterar_senha_exige_senha_atual_correta(self):
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            "/api/auth/alterar-senha/",
            {"senha_atual": "errada", "nova_senha": "OutraSenha456"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_alterar_senha_troca_credencial_e_devolve_tokens(self):
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            "/api/auth/alterar-senha/",
            {"senha_atual": SENHA, "nova_senha": "OutraSenha456"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertIn("access", resposta.data)
        self.assertIn("refresh", resposta.data)

        login = APIClient().post(
            "/api/auth/login/",
            {"cpf": self.usuario_admin.cpf, "password": "OutraSenha456"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_alterar_senha_fraca_retorna_400(self):
        client = self.autenticar(self.usuario_admin)

        resposta = client.post(
            "/api/auth/alterar-senha/",
            {"senha_atual": SENHA, "nova_senha": "123"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_le_e_atualiza_clinica(self):
        client = self.autenticar(self.usuario_admin)

        leitura = client.get("/api/clinica/atual/")
        self.assertEqual(leitura.status_code, status.HTTP_200_OK, leitura.data)
        self.assertEqual(leitura.data["cnpj"], "48545800000100")

        resposta = client.patch(
            "/api/clinica/atual/",
            {
                "nome_fantasia": "Clínica Nova",
                "telefone": "(11) 3333-4444",
                "endereco": "Rua A, 10",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.clinica.refresh_from_db()
        self.assertEqual(self.clinica.nome_fantasia, "Clínica Nova")
        self.assertEqual(self.clinica.telefone, "1133334444")

    def test_profissional_nao_acessa_clinica_atual(self):
        client = self.autenticar(self.usuario_prof)

        self.assertEqual(
            client.get("/api/clinica/atual/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            client.patch(
                "/api/clinica/atual/",
                {"nome_fantasia": "X"},
                format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cnpj_duplicado_retorna_400(self):
        Clinica.objects.create(
            cnpj="11222333000181",
            razao_social="Outra",
            nome_fantasia="Outra",
            telefone="11999999999",
        )
        client = self.autenticar(self.usuario_admin)

        resposta = client.patch(
            "/api/clinica/atual/",
            {"cnpj": "11.222.333/0001-81"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cnpj", resposta.data)