from datetime import timedelta, date
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from core.models import Usuario, Clinica, Role, Colaborador, Cliente, Agendamento, Servico

class RegrasFinaisTestCase(APITestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(
            cnpj="11222333000181", razao_social="Clinica Teste Finais",
            nome_fantasia="Teste", telefone="47999999999"
        )
        
        self.role_admin, _ = Role.objects.get_or_create(nome=Role.ADMIN)
        self.role_sec, _ = Role.objects.get_or_create(nome=Role.SECRETARIO)
        self.role_prof, _ = Role.objects.get_or_create(nome=Role.PROFISSIONAL)
        self.user_admin = Usuario.objects.create_user(
            cpf="52998224725", nome_completo="Admin", data_nascimento=date(1990, 1, 1), password="senha"
        )
        self.colab_admin = Colaborador.objects.create(
            usuario=self.user_admin, clinica=self.clinica, role=self.role_admin
        )

        self.user_sec = Usuario.objects.create_user(
            cpf="10950875929", nome_completo="Secretario", data_nascimento=date(1990, 1, 1), password="senha"
        )
        self.colab_sec = Colaborador.objects.create(
            usuario=self.user_sec, clinica=self.clinica, role=self.role_sec
        )

        self.user_prof = Usuario.objects.create_user(
            cpf="11144477735", nome_completo="Profissional", data_nascimento=date(1990, 1, 1), password="senha"
        )
        self.colab_prof = Colaborador.objects.create(
            usuario=self.user_prof, clinica=self.clinica, role=self.role_prof
        )

        self.client.defaults['HTTP_X_CLINICA_ID'] = str(self.clinica.id)

    def autenticar(self, cpf):
        resp = self.client.post("/api/auth/login/", {"cpf": cpf, "password": "senha"})
        token = resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_secretario_pode_listar_colaboradores_mas_nao_editar(self):
        self.autenticar("10950875929") 
        
        resp_get = self.client.get("/api/colaboradores/")
        self.assertEqual(resp_get.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_get.data), 3)

        resp_post = self.client.post("/api/colaboradores/", {
            "cpf": "12345678909", "nome_completo": "Invasor", "role": self.role_prof.id
        })
        self.assertEqual(resp_post.status_code, status.HTTP_403_FORBIDDEN)

    def test_criacao_automatica_usuario_e_mascara_cpf_lgpd(self):
        self.autenticar("52998224725") 
        
        cpf_novo = "12345678909"
        resp = self.client.post("/api/clientes/", {
            "cpf": cpf_novo,
            "nome_completo": "Cliente Novo Automata",
            "telefone": "47988888888"
        })
        
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Usuario.objects.filter(cpf=cpf_novo).exists())
        self.assertEqual(resp.data["usuario_cpf"], "***.456.789-**")

    def test_edicao_agenda_ignora_conflito_pendente(self):
        self.autenticar("52998224725") 
        
        user_cli = Usuario.objects.create_user(
            cpf="98765432100", nome_completo="Cli", data_nascimento=date(1990, 1, 1), password=None
        )
        cliente = Cliente.objects.create(usuario=user_cli, clinica=self.clinica, telefone="47999999999")
        servico = Servico.objects.create(clinica=self.clinica, nome="Consulta", duracao_padrao_minutos=60)

        hoje = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        ag1 = Agendamento.objects.create(
            clinica=self.clinica, profissional=self.colab_prof, cliente=cliente, servico=servico,
            data_hora_inicio=hoje.replace(hour=10), data_hora_fim=hoje.replace(hour=11),
            status=Agendamento.PENDENTE
        )

        ag2 = Agendamento.objects.create(
            clinica=self.clinica, profissional=self.colab_prof, cliente=cliente, servico=servico,
            data_hora_inicio=hoje.replace(hour=13), data_hora_fim=hoje.replace(hour=14),
            status=Agendamento.CONFIRMADO
        )

        resp_ok = self.client.patch(f"/api/agendamentos/{ag2.id}/", {
            "data_hora_inicio": hoje.replace(hour=10, minute=30).isoformat(),
            "data_hora_fim": hoje.replace(hour=11, minute=30).isoformat()
        })
        self.assertEqual(resp_ok.status_code, status.HTTP_200_OK)

        ag2.refresh_from_db()
        ag2.data_hora_inicio = hoje.replace(hour=13)
        ag2.data_hora_fim = hoje.replace(hour=14)
        ag2.save()
        ag1.status = Agendamento.CONFIRMADO
        ag1.save()
        resp_conflito = self.client.patch(f"/api/agendamentos/{ag2.id}/", {
            "data_hora_inicio": hoje.replace(hour=10, minute=30).isoformat(),
            "data_hora_fim": hoje.replace(hour=11, minute=30).isoformat()
        })
        self.assertEqual(resp_conflito.status_code, status.HTTP_409_CONFLICT)