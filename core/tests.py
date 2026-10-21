from django.test import TransactionTestCase
from django.utils import timezone
from django.db.utils import IntegrityError
from datetime import timedelta
from core.models import Usuario, Clinica, Colaborador, Role, Cliente, Servico, Agendamento

class AgendamentoConstraintTest(TransactionTestCase):
    def setUp(self):
        self.usuario1 = Usuario.objects.create_user(cpf="11144477735", nome_completo="Profissional Teste", data_nascimento="1990-01-01", password="123")
        self.usuario2 = Usuario.objects.create_user(cpf="22255588846", nome_completo="Cliente Teste", data_nascimento="1995-01-01", password="123")
        self.clinica = Clinica.objects.create(
            cnpj="11444777000161", 
            razao_social="Clinica A", 
            nome_fantasia="Clinica A",
            telefone="11999999999"
        )
        
        role_prof = Role.objects.get_or_create(nome=Role.PROFISSIONAL)[0]
        self.profissional = Colaborador.objects.create(usuario=self.usuario1, clinica=self.clinica, role=role_prof)
        self.cliente = Cliente.objects.create(usuario=self.usuario2, clinica=self.clinica, telefone="11999999999")
        self.servico = Servico.objects.create(clinica=self.clinica, nome="Servico A", duracao_padrao_minutos=30)

        self.agora = timezone.now()

    def test_bloqueio_sobreposicao_profissional(self):
        Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            data_hora_inicio=self.agora,
            data_hora_fim=self.agora + timedelta(minutes=30),
            status=Agendamento.CONFIRMADO
        )

        with self.assertRaises(IntegrityError):
            Agendamento.objects.create(
                clinica=self.clinica,
                cliente=self.cliente,
                profissional=self.profissional,
                servico=self.servico,
                data_hora_inicio=self.agora + timedelta(minutes=15),
                data_hora_fim=self.agora + timedelta(minutes=45),
                status=Agendamento.CONFIRMADO
            )

    def test_permite_pendentes_concorrentes(self):
        Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            data_hora_inicio=self.agora,
            data_hora_fim=self.agora + timedelta(minutes=30),
            status=Agendamento.PENDENTE
        )

        Agendamento.objects.create(
            clinica=self.clinica,
            cliente=self.cliente,
            profissional=self.profissional,
            servico=self.servico,
            data_hora_inicio=self.agora + timedelta(minutes=15),
            data_hora_fim=self.agora + timedelta(minutes=45),
            status=Agendamento.PENDENTE
        )
        self.assertEqual(Agendamento.objects.count(), 2)