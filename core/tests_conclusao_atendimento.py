from datetime import timedelta
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Agendamento,
    Auditoria,
    Cliente,
    Clinica,
    Colaborador,
    HistoricoSessao,
    Pacote,
    ProcedimentoRealizado,
    Role,
    Servico,
    SessaoPacote,
    Usuario,
)
from core.servicos_atendimento import (
    RegraAtendimentoError,
    concluir_atendimento,
    estornar_procedimento,
)


class ConclusaoAtendimentoTestCase(TestCase):
    def setUp(self):
        self.usuario_admin = Usuario.objects.create_user(
            cpf="11144477735",
            nome_completo="Admin Teste",
            data_nascimento="1990-01-01",
            password="Teste!Senha2026",
        )
        self.usuario_cliente = Usuario.objects.create_user(
            cpf="22255588846",
            nome_completo="Cliente Teste",
            data_nascimento="1995-01-01",
            password="Teste!Senha2026",
        )
        self.clinica = Clinica.objects.create(
            cnpj="11444777000161",
            razao_social="Clínica Teste LTDA",
            nome_fantasia="Clínica Teste",
            telefone="47999999999",
        )
        role = Role.objects.get_or_create(nome=Role.ADMIN)[0]
        self.admin = Colaborador.objects.create(
            usuario=self.usuario_admin,
            clinica=self.clinica,
            role=role,
        )
        self.cliente = Cliente.objects.create(
            usuario=self.usuario_cliente,
            clinica=self.clinica,
            telefone="47999999999",
        )
        self.servico = Servico.objects.create(
            clinica=self.clinica,
            nome="Limpeza de pele",
            preco="100.00",
            duracao_padrao_minutos=30,
        )
        self.pacote = Pacote.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            servico=self.servico,
            quantidade_sessoes=2,
            valor_total="180.00",
        )
        self.sessoes = [
            SessaoPacote.objects.create(pacote=self.pacote)
            for _ in range(2)
        ]
        self.api = APIClient()
        self.api.force_authenticate(self.usuario_admin)

    def agendar(self, horas_atras=2, pacote=True, status=Agendamento.CONFIRMADO):
        inicio = timezone.now() - timedelta(hours=horas_atras)
        agendamento = Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.admin,
            servico=self.servico,
            pacote_origem=self.pacote if pacote else None,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=30),
            status=status,
        )
        if pacote:
            sessao = (
                SessaoPacote.objects.filter(
                    pacote=self.pacote,
                    status=SessaoPacote.DISPONIVEL,
                )
                .order_by("pk")
                .first()
            )
            sessao.status = SessaoPacote.AGENDADA
            sessao.agendamento = agendamento
            sessao.save()
        return agendamento

    def test_conclusao_consome_uma_sessao_e_gera_procedimento(self):
        agendamento = self.agendar()
        procedimento, consumidas = concluir_atendimento(
            agendamento.pk, usuario=self.usuario_admin, origem="MANUAL"
        )
        self.assertEqual(consumidas, 1)
        self.assertEqual(procedimento.cliente_id, self.cliente.pk)
        self.assertEqual(procedimento.profissional_id, self.admin.pk)
        self.assertEqual(procedimento.servico_id, self.servico.pk)
        self.assertEqual(procedimento.agendamento_id, agendamento.pk)
        self.assertEqual(
            SessaoPacote.objects.filter(status=SessaoPacote.UTILIZADA).count(),
            1,
        )

    def test_segunda_conclusao_e_rejeitada(self):
        agendamento = self.agendar()
        concluir_atendimento(agendamento.pk, usuario=None)
        with self.assertRaises(RegraAtendimentoError):
            concluir_atendimento(agendamento.pk, usuario=self.usuario_admin)
        self.assertEqual(ProcedimentoRealizado.objects.count(), 1)
        self.assertEqual(
            SessaoPacote.objects.filter(status=SessaoPacote.UTILIZADA).count(),
            1,
        )

    def test_cancelado_nao_conclui(self):
        agendamento = self.agendar(status=Agendamento.CANCELADO)
        with self.assertRaises(RegraAtendimentoError):
            concluir_atendimento(agendamento.pk, usuario=None)
        self.assertEqual(ProcedimentoRealizado.objects.count(), 0)

    def test_sessao_de_pacote_de_outro_cliente_e_rejeitada(self):
        agendamento = self.agendar()
        outro_usuario = Usuario.objects.create_user(
            cpf="33366699957",
            nome_completo="Outro Cliente",
            data_nascimento="1992-01-01",
            password="Teste!Senha2026",
        )
        outro = Cliente.objects.create(
            usuario=outro_usuario,
            clinica=self.clinica,
            telefone="47988888888",
        )
        Agendamento.objects.filter(pk=agendamento.pk).update(cliente=outro)
        with self.assertRaises(RegraAtendimentoError):
            concluir_atendimento(agendamento.pk, usuario=None)
        self.assertEqual(ProcedimentoRealizado.objects.count(), 0)

    def test_comando_automatico_usa_o_mesmo_servico_e_e_idempotente(self):
        agendamento = self.agendar()
        call_command("concluir_agendamentos", stdout=StringIO())
        call_command("concluir_agendamentos", stdout=StringIO())
        agendamento.refresh_from_db()
        self.assertEqual(agendamento.status, Agendamento.CONCLUIDO)
        self.assertEqual(ProcedimentoRealizado.objects.count(), 1)
        procedimento = ProcedimentoRealizado.objects.get()
        self.assertEqual(procedimento.origem, "AUTOMATICA")

    def test_endpoint_concluir_manual(self):
        agendamento = self.agendar()
        resposta = self.api.post(
            f"/api/agendamentos/{agendamento.pk}/concluir/",
            {},
            format="json",
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )
        self.assertIn(resposta.status_code, (200, 201), resposta.content)
        self.assertEqual(ProcedimentoRealizado.objects.count(), 1)
        repetida = self.api.post(
            f"/api/agendamentos/{agendamento.pk}/concluir/",
            {},
            format="json",
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )
        self.assertEqual(repetida.status_code, 400)

    def test_pacote_conclui_quando_todas_as_sessoes_sao_usadas(self):
        for _ in range(2):
            agendamento = self.agendar()
            concluir_atendimento(agendamento.pk, usuario=None)
            agendamento.refresh_from_db()
            Agendamento.objects.filter(pk=agendamento.pk).update(
                data_hora_inicio=agendamento.data_hora_inicio - timedelta(days=_ + 1),
                data_hora_fim=agendamento.data_hora_fim - timedelta(days=_ + 1),
            )
        self.pacote.refresh_from_db()
        self.assertEqual(self.pacote.status, Pacote.CONCLUIDO)

    def test_estorno_registra_responsavel_motivo_e_destino(self):
        agendamento = self.agendar()
        procedimento, _ = concluir_atendimento(agendamento.pk, usuario=None)
        estornado = estornar_procedimento(
            agendamento, self.usuario_admin, "Cliente não compareceu", "PRESERVAR"
        )
        estornado.refresh_from_db()
        self.assertEqual(estornado.status, ProcedimentoRealizado.ESTORNADO)
        self.assertEqual(estornado.estornado_por_id, self.usuario_admin.pk)
        self.assertIsNotNone(estornado.estornado_em)
        self.assertEqual(estornado.motivo_estorno, "Cliente não compareceu")
        self.assertEqual(estornado.destino_sessao, "DEVOLVIDA")
        self.assertTrue(
            Auditoria.objects.filter(
                entidade="ProcedimentoRealizado",
                objeto_id=str(procedimento.pk),
            ).exists()
        )

    def test_falta_apos_conclusao_estorna_e_devolve_sessao(self):
        agendamento = self.agendar()
        concluir_atendimento(agendamento.pk, usuario=None)
        resposta = self.api.post(
            f"/api/agendamentos/{agendamento.pk}/registrar_falta/",
            {"decisao_sessao": "PRESERVAR", "justificativa": "Erro de lançamento"},
            format="json",
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        procedimento = ProcedimentoRealizado.objects.get(agendamento=agendamento)
        self.assertEqual(procedimento.status, ProcedimentoRealizado.ESTORNADO)
        self.assertEqual(procedimento.destino_sessao, "DEVOLVIDA")
        self.pacote.refresh_from_db()
        self.assertEqual(self.pacote.status, Pacote.ATIVO)
        self.assertEqual(
            SessaoPacote.objects.filter(status=SessaoPacote.DISPONIVEL).count(),
            2,
        )

    def test_falta_com_perda_marca_sessao_perdida(self):
        agendamento = self.agendar()
        concluir_atendimento(agendamento.pk, usuario=None)
        self.api.post(
            f"/api/agendamentos/{agendamento.pk}/registrar_falta/",
            {"decisao_sessao": "PERDER", "justificativa": "Política da clínica"},
            format="json",
            HTTP_X_CLINICA_ID=str(self.clinica.pk),
        )
        procedimento = ProcedimentoRealizado.objects.get(agendamento=agendamento)
        self.assertEqual(procedimento.destino_sessao, "PERDIDA")
        self.assertEqual(
            SessaoPacote.objects.filter(status=SessaoPacote.PERDIDA).count(),
            1,
        )

    def test_transicao_invalida_de_sessao_e_bloqueada(self):
        sessao = self.sessoes[0]
        sessao.status = SessaoPacote.PERDIDA
        with self.assertRaises(ValidationError):
            sessao.save()

    def test_procedimento_e_imutavel_e_nao_pode_ser_excluido(self):
        agendamento = self.agendar()
        procedimento, _ = concluir_atendimento(agendamento.pk, usuario=None)
        procedimento.valor = "999.00"
        with self.assertRaises(ValidationError):
            procedimento.save()
        with self.assertRaises(ValidationError):
            procedimento.delete()

    def test_historico_preserva_dados_apos_alteracoes_cadastrais(self):
        agendamento = self.agendar()
        procedimento, _ = concluir_atendimento(agendamento.pk, usuario=None)
        self.servico.nome = "Nome alterado"
        self.servico.save()
        self.usuario_cliente.nome_completo = "Cliente Renomeado"
        self.usuario_cliente.save()
        self.cliente.status_cadastro = Cliente.INATIVO
        self.cliente.save()
        self.pacote.status = Pacote.CANCELADO
        self.pacote.save()
        procedimento.refresh_from_db()
        self.assertEqual(procedimento.servico_nome, "Limpeza de pele")
        self.assertEqual(procedimento.cliente_nome, "Cliente Teste")
        self.assertEqual(procedimento.profissional_nome, "Admin Teste")

    def test_historico_do_cliente_e_historico_de_sessoes_da_api(self):
        agendamento = self.agendar()
        concluir_atendimento(agendamento.pk, usuario=self.usuario_admin, origem="MANUAL")
        cabecalho = {"HTTP_X_CLINICA_ID": str(self.clinica.pk)}
        historico = self.api.get(
            f"/api/clientes/{self.cliente.pk}/historico/", **cabecalho
        )
        self.assertEqual(historico.status_code, 200, historico.content)
        self.assertEqual(historico.data["resumo"]["procedimentos_realizados"], 1)
        self.assertEqual(historico.data["resumo"]["sessoes_utilizadas"], 1)
        sessoes = self.api.get(
            f"/api/pacotes/{self.pacote.pk}/sessoes/", **cabecalho
        )
        self.assertEqual(sessoes.status_code, 200, sessoes.content)
        self.assertEqual(len(sessoes.data["sessoes"]), 2)
        self.assertTrue(
            HistoricoSessao.objects.filter(
                estado_novo=SessaoPacote.UTILIZADA
            ).exists()
        )