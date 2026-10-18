import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.conf import settings

def validate_cpf(value):
    cpf = ''.join([c for c in value if c.isdigit()])
    if len(cpf) != 11 or len(set(cpf)) == 1:
        raise ValidationError('CPF inválido.')
    for i in range(9, 11):
        val = sum((int(cpf[num]) * ((i + 1) - num) for num in range(0, i)))
        digit = ((val * 10) % 11) % 10
        if digit != int(cpf[i]):
            raise ValidationError('CPF inválido.')

def validate_cnpj(value):
    cnpj = ''.join([c for c in value if c.isdigit()])
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        raise ValidationError('CNPJ inválido.')
    calc_dvs = lambda cnpj, pesos: sum(int(digito) * peso for digito, peso in zip(cnpj, pesos)) % 11
    peso1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    peso2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv1 = 11 - calc_dvs(cnpj[:12], peso1)
    dv1 = 0 if dv1 >= 10 else dv1
    dv2 = 11 - calc_dvs(cnpj[:12] + str(dv1), peso2)
    dv2 = 0 if dv2 >= 10 else dv2
    if str(dv1) != cnpj[12] or str(dv2) != cnpj[13]:
        raise ValidationError('CNPJ inválido.')

class UsuarioManager(BaseUserManager):
    def create_user(self, cpf, nome_completo, data_nascimento, password=None, **extra_fields):
        if not cpf:
            raise ValueError('O CPF é obrigatório')
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        user = self.model(
            cpf=cpf,
            nome_completo=nome_completo,
            data_nascimento=data_nascimento,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, cpf, nome_completo, data_nascimento, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser precisa ter is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser precisa ter is_superuser=True.')

        return self.create_user(cpf, nome_completo, data_nascimento, password, **extra_fields)

class Usuario(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.CharField(max_length=11, unique=True, validators=[validate_cpf])
    nome_completo = models.CharField(max_length=255)
    data_nascimento = models.DateField()
    telefone = models.CharField(max_length=20, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = 'cpf'
    REQUIRED_FIELDS = ['nome_completo', 'data_nascimento']

    class Meta:
        db_table = 'usuarios'

    def __str__(self):
        return self.nome_completo

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

class Clinica(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cnpj = models.CharField(max_length=14, unique=True, validators=[validate_cnpj])
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255)
    telefone = models.CharField(max_length=20)
    endereco = models.CharField(max_length=255, blank=True)
    profissionais_podem_editar_agenda = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinicas'
        constraints = [
            models.CheckConstraint(condition=models.Q(cnpj__regex=r'^[0-9]{14}$'), name='chk_cnpj_format'),
            models.CheckConstraint(condition=models.Q(telefone__regex=r'^[0-9]+$'), name='chk_clinica_telefone_format')
        ]

    def __str__(self):
        return self.nome_fantasia

class Role(models.Model):
    ADMIN = 'ADMIN'
    SECRETARIO = 'SECRETARIO'
    PROFISSIONAL = 'PROFISSIONAL'

    ROLE_CHOICES = [
        (ADMIN, 'Administrador'),
        (SECRETARIO, 'Secretário'),
        (PROFISSIONAL, 'Profissional'),
    ]

    nome = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)

    class Meta:
        db_table = 'roles'

    def __str__(self):
        return self.nome

class Cliente(models.Model):
    ATIVO = 'ATIVO'
    INATIVO = 'INATIVO'

    STATUS_CHOICES = [
        (ATIVO, 'Ativo'),
        (INATIVO, 'Inativo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='vinculos_cliente')
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name='clientes')
    telefone = models.CharField(max_length=20)
    cep = models.CharField(max_length=8, blank=True)
    numero_endereco = models.CharField(max_length=20, blank=True)
    status_cadastro = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ATIVO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientes'
        unique_together = ('usuario', 'clinica')

class Colaborador(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='vinculos_colaborador')
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name='colaboradores')
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    ativo = models.BooleanField(default=True)
    pode_editar_agenda = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'colaboradores'
        unique_together = ('usuario', 'clinica')

class Servico(models.Model):
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name='servicos')
    nome = models.CharField(max_length=255)
    duracao_padrao_minutos = models.PositiveIntegerField()
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'servicos'

    def __str__(self):
        return self.nome

class Pacote(models.Model):
    ATIVO = 'ATIVO'
    CONCLUIDO = 'CONCLUIDO'
    CANCELADO = 'CANCELADO'

    STATUS_CHOICES = [
        (ATIVO, 'Ativo'),
        (CONCLUIDO, 'Concluído'),
        (CANCELADO, 'Cancelado'),
    ]

    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name='pacotes')
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='pacotes')
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, related_name='pacotes')
    quantidade_sessoes = models.PositiveIntegerField()
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ATIVO)
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pacotes'

class Agendamento(models.Model):
    PENDENTE = 'PENDENTE'
    CONFIRMADO = 'CONFIRMADO'
    CONCLUIDO = 'CONCLUIDO'
    CANCELADO = 'CANCELADO'
    FALTA = 'FALTA'

    STATUS_CHOICES = [
        (PENDENTE, 'Pendente'),
        (CONFIRMADO, 'Confirmado'),
        (CONCLUIDO, 'Concluído'),
        (CANCELADO, 'Cancelado'),
        (FALTA, 'Falta'),
    ]

    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name='agendamentos')
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='agendamentos')
    profissional = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name='agendamentos_profissional')
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, related_name='agendamentos')
    pacote_origem = models.ForeignKey(Pacote, on_delete=models.SET_NULL, null=True, blank=True, related_name='agendamentos')
    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDENTE)
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agendamentos'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_hora_fim__gt=models.F('data_hora_inicio')),
                name='chk_data_fim_maior_inicio'
            ),
            ExclusionConstraint(
                name='chk_sobreposicao_profissional',
                expressions=[
                    ('profissional', '='),
                    (models.Func(models.F('data_hora_inicio'), models.F('data_hora_fim'), function='tstzrange'), '&&'),
                ],
                condition=models.Q(status='CONFIRMADO'),
            ),
            ExclusionConstraint(
                name='chk_sobreposicao_cliente',
                expressions=[
                    ('cliente', '='),
                    (models.Func(models.F('data_hora_inicio'), models.F('data_hora_fim'), function='tstzrange'), '&&'),
                ],
                condition=models.Q(status='CONFIRMADO'),
            )
        ]

class SessaoPacote(models.Model):
    AGENDADA = 'AGENDADA'
    REALIZADA = 'REALIZADA'
    CANCELADA = 'CANCELADA'
    FALTA = 'FALTA'

    STATUS_CHOICES = [
        (AGENDADA, 'Agendada'),
        (REALIZADA, 'Realizada'),
        (CANCELADA, 'Cancelada'),
        (FALTA, 'Falta'),
    ]

    pacote = models.ForeignKey(Pacote, on_delete=models.CASCADE, related_name='sessoes')
    agendamento = models.OneToOneField(Agendamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessao_pacote')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AGENDADA)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sessoes_pacote'

class HistoricoSessao(models.Model):
    sessao = models.ForeignKey(SessaoPacote, on_delete=models.CASCADE, related_name='historico')
    estado_anterior = models.CharField(max_length=20)
    estado_novo = models.CharField(max_length=20)
    data_alteracao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historico_sessoes'

class Auditoria(models.Model):
    ACAO_CHOICES = [
        ('CREATE', 'Criação'),
        ('UPDATE', 'Atualização'),
        ('DELETE', 'Exclusão'),
        ('DEACTIVATE', 'Desativação'),
    ]

    ORIGEM_CHOICES = [
        ('USUARIO', 'Usuário via API'),
        ('SISTEMA', 'Rotina Automática / Sistema'),
    ]

    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name='auditorias')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='auditorias')
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    entidade = models.CharField(max_length=50)
    objeto_id = models.CharField(max_length=255)
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default='USUARIO')
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auditoria'
        ordering = ['-data_hora']