import re
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, RegexValidator
from django.db import models
from django.db.models import Q, F, Func
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators

numeric_validator = RegexValidator(
    regex=r"^[0-9]+$",
    message="Este campo deve conter somente números.",
)

def validate_numeric_document(value, field_name, length):
    if value is None:
        return
    if not value.isdigit():
        raise ValidationError({field_name: f"{field_name.upper()} deve conter somente números."})
    if len(value) != length:
        raise ValidationError({field_name: f"{field_name.upper()} deve possuir {length} dígitos."})

def validate_cpf(value):
    validate_numeric_document(value, "cpf", 11)
    if value == value[0] * 11:
        raise ValidationError({"cpf": "CPF inválido."})
    digits = [int(digit) for digit in value]
    total = sum(digits[index] * (10 - index) for index in range(9))
    remainder = total % 11
    first_digit = 0 if remainder < 2 else 11 - remainder
    if digits[9] != first_digit:
        raise ValidationError({"cpf": "CPF inválido."})
    total = sum(digits[index] * (11 - index) for index in range(10))
    remainder = total % 11
    second_digit = 0 if remainder < 2 else 11 - remainder
    if digits[10] != second_digit:
        raise ValidationError({"cpf": "CPF inválido."})

def validate_cnpj(value):
    validate_numeric_document(value, "cnpj", 14)
    if value == value[0] * 14:
        raise ValidationError({"cnpj": "CNPJ inválido."})
    digits = [int(digit) for digit in value]
    weights_first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(digits[index] * weights_first[index] for index in range(12))
    remainder = total % 11
    first_digit = 0 if remainder < 2 else 11 - remainder
    if digits[12] != first_digit:
        raise ValidationError({"cnpj": "CNPJ inválido."})
    weights_second = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(digits[index] * weights_second[index] for index in range(13))
    remainder = total % 11
    second_digit = 0 if remainder < 2 else 11 - remainder
    if digits[13] != second_digit:
        raise ValidationError({"cnpj": "CNPJ inválido."})

def validate_phone(value):
    if value is None:
        return
    if not value.isdigit():
        raise ValidationError({"telefone": "Telefone deve conter somente números."})
    if len(value) not in (10, 11):
        raise ValidationError({"telefone": "Telefone deve possuir 10 ou 11 dígitos."})

def validate_cep(value):
    if value is None or value == "":
        return
    if not value.isdigit():
        raise ValidationError({"cep": "CEP deve conter somente números."})
    if len(value) != 8:
        raise ValidationError({"cep": "CEP deve possuir 8 dígitos."})

def validate_uf(value):
    if value is None or value == "":
        return
    if not re.fullmatch(r"[A-Z]{2}", value):
        raise ValidationError({"estado": "Estado deve ser informado pela sigla com 2 letras."})

class UsuarioManager(BaseUserManager):
    def create_user(self, cpf, password=None, **extra_fields):
        if not cpf:
            raise ValueError("CPF é obrigatório.")
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        if not extra_fields.get("is_staff") and not extra_fields.get("is_superuser") and not extra_fields.get("data_nascimento"):
            raise ValueError("Data de nascimento é obrigatória para usuários comuns.")
        user = self.model(cpf=cpf, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, cpf, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário deve possuir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário deve possuir is_superuser=True.")
        return self.create_user(cpf=cpf, password=password, **extra_fields)

class Usuario(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.CharField(max_length=11, unique=True, validators=[numeric_validator])
    nome_completo = models.CharField(max_length=150)
    data_nascimento = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "cpf"
    REQUIRED_FIELDS = ["nome_completo"]

    class Meta:
        db_table = "usuarios"
        constraints = [
            models.CheckConstraint(
                condition=Q(is_staff=True, is_superuser=True) | Q(data_nascimento__isnull=False),
                name="usuario_data_nascimento_ou_conta_tecnica",
            ),
            models.CheckConstraint(
                condition=Q(cpf__regex=r"^[0-9]{11}$"),
                name="usuario_cpf_somente_numeros",
            ),
        ]

    def clean(self):
        super().clean()
        validate_cpf(self.cpf)
        if not self.is_staff and not self.is_superuser and not self.data_nascimento:
            raise ValidationError({"data_nascimento": "Data de nascimento é obrigatória para usuários comuns."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome_completo} - {self.cpf}"

class Clinica(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cnpj = models.CharField(max_length=14, unique=True, validators=[numeric_validator])
    razao_social = models.CharField(max_length=150)
    nome_fantasia = models.CharField(max_length=100)
    telefone = models.CharField(max_length=11, blank=True, validators=[numeric_validator])
    email = models.EmailField(blank=True, validators=[EmailValidator()])
    cep = models.CharField(max_length=8, blank=True, validators=[numeric_validator])
    logradouro = models.CharField(max_length=150, blank=True)
    numero = models.CharField(max_length=10, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    
    profissionais_podem_editar_agenda = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinicas"
        indexes = [models.Index(fields=["ativo"], name="idx_clinica_ativo")]
        constraints = [
            models.CheckConstraint(condition=Q(cnpj__regex=r"^[0-9]{14}$"), name="clinica_cnpj_somente_numeros"),
        ]

    def clean(self):
        super().clean()
        validate_cnpj(self.cnpj)
        validate_phone(self.telefone)
        validate_cep(self.cep)
        if self.estado:
            self.estado = self.estado.upper()
        validate_uf(self.estado)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome_fantasia

class Role(models.Model):
    ADMIN = "ADMIN"
    SECRETARIO = "SECRETARIO"
    PROFISSIONAL = "PROFISSIONAL"

    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (SECRETARIO, "Secretário"),
        (PROFISSIONAL, "Profissional"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)

    class Meta:
        db_table = "roles"

    def __str__(self):
        return self.nome

class Colaborador(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="colaboracoes")
    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name="colaboradores")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="colaboradores")
    pode_editar_agenda = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "colaboradores"
        constraints = [models.UniqueConstraint(fields=["usuario", "clinica"], name="uq_colaborador_usuario_clinica")]
        indexes = [
            models.Index(fields=["clinica", "ativo"], name="idx_colaborador_clinica_ativo"),
            models.Index(fields=["usuario", "ativo"], name="idx_colaborador_usuario_ativo"),
            models.Index(fields=["clinica", "role", "ativo"], name="idx_colaborador_clinica_role"),
        ]

    def clean(self):
        super().clean()
        if not self.role_id: return
        if self.role.nome not in (Role.ADMIN, Role.SECRETARIO, Role.PROFISSIONAL):
            raise ValidationError({"role": "Função de colaborador inválida."})
        if self.role.nome != Role.PROFISSIONAL and self.pk:
            if self.especialidades_vinculadas.exists():
                raise ValidationError({"role": "O colaborador possui especialidades vinculadas. Remova-as antes."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.usuario.nome_completo} - {self.clinica.nome_fantasia}"

class Especialidade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name="especialidades")
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "especialidades"
        constraints = [models.UniqueConstraint(fields=["clinica", "nome"], name="uq_especialidade_clinica_nome")]
        indexes = [models.Index(fields=["clinica", "ativo"], name="idx_espec_clinica_ativo")]

    def __str__(self):
        return self.nome

class ColaboradorEspecialidade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    colaborador = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="especialidades_vinculadas")
    especialidade = models.ForeignKey(Especialidade, on_delete=models.PROTECT, related_name="colaboradores_vinculados")
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "colaboradores_especialidades"
        constraints = [models.UniqueConstraint(fields=["colaborador", "especialidade"], name="uq_colaborador_especialidade")]
        indexes = [
            models.Index(fields=["colaborador", "ativo"], name="idx_colab_especialidade_colab"),
            models.Index(fields=["especialidade", "ativo"], name="idx_colab_especialidade_espec"),
        ]

    def clean(self):
        super().clean()
        if not self.colaborador_id or not self.especialidade_id: return
        if self.colaborador.clinica_id != self.especialidade.clinica_id:
            raise ValidationError("O colaborador e a especialidade devem pertencer à mesma clínica.")
        if self.colaborador.role.nome != Role.PROFISSIONAL:
            raise ValidationError("Somente colaboradores PROFISSIONAIS podem possuir especialidades.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.colaborador.usuario.nome_completo} - {self.especialidade.nome}"

class Cliente(models.Model):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    STATUS_CADASTRO_CHOICES = [(ATIVO, "Ativo"), (INATIVO, "Inativo")]

    EM_DIA = "EM_DIA"
    INADIMPLENTE = "INADIMPLENTE"
    STATUS_FINANCEIRO_CHOICES = [(EM_DIA, "Em dia"), (INADIMPLENTE, "Inadimplente")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="vinculos_cliente")
    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name="clientes")
    telefone = models.CharField(max_length=11, validators=[numeric_validator])
    email = models.EmailField(blank=True, validators=[EmailValidator()])
    cep = models.CharField(max_length=8, blank=True, validators=[numeric_validator])
    logradouro = models.CharField(max_length=150, blank=True)
    numero = models.CharField(max_length=10, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    
    status_cadastro = models.CharField(max_length=20, choices=STATUS_CADASTRO_CHOICES, default=ATIVO)
    status_financeiro = models.CharField(max_length=20, choices=STATUS_FINANCEIRO_CHOICES, default=EM_DIA)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clientes"
        constraints = [models.UniqueConstraint(fields=["usuario", "clinica"], name="uq_cliente_usuario_clinica")]
        indexes = [
            models.Index(fields=["clinica", "status_cadastro"], name="idx_cliente_clinica_status"),
            models.Index(fields=["clinica", "status_financeiro"], name="idx_cliente_clinica_financeiro"),
        ]

    def clean(self):
        super().clean()
        validate_phone(self.telefone)
        validate_cep(self.cep)
        if self.estado: self.estado = self.estado.upper()
        validate_uf(self.estado)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.usuario.nome_completo} - {self.clinica.nome_fantasia}"

class Auditoria(models.Model):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DEACTIVATE = "DEACTIVATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    OTHER = "OTHER"

    ACAO_CHOICES = [
        (CREATE, "Criação"), (UPDATE, "Atualização"), (DEACTIVATE, "Desativação"),
        (DELETE, "Exclusão"), (LOGIN, "Login"), (LOGOUT, "Logout"), (OTHER, "Outro"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="auditorias")
    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, null=True, blank=True, related_name="auditorias")
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    entidade = models.CharField(max_length=100)
    objeto_id = models.CharField(max_length=100, blank=True)
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    origem = models.CharField(max_length=50, default="USUARIO")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auditorias"
        indexes = [
            models.Index(fields=["clinica", "created_at"], name="idx_auditoria_clinica_data"),
            models.Index(fields=["usuario", "created_at"], name="idx_auditoria_usuario_data"),
            models.Index(fields=["entidade", "objeto_id"], name="idx_auditoria_entidade_objeto"),
            models.Index(fields=["acao", "created_at"], name="idx_auditoria_acao_data"),
        ]

    def __str__(self):
        return f"{self.acao} - {self.entidade} - {self.objeto_id}"

class Servico(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name="servicos")
    nome = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    duracao_padrao_minutos = models.PositiveIntegerField(default=30)
    preco = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "servicos"
        constraints = [
            models.UniqueConstraint(fields=["clinica", "nome"], name="uq_servico_clinica_nome")
        ]

    def __str__(self):
        return f"{self.nome} - {self.clinica.nome_fantasia}"

class Agendamento(models.Model):
    PENDENTE = "PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    CANCELADO = "CANCELADO"
    CONCLUIDO = "CONCLUIDO"
    STATUS_CHOICES = [
        (PENDENTE, "Pendente"), (CONFIRMADO, "Confirmado"), 
        (CANCELADO, "Cancelado"), (CONCLUIDO, "Concluído")
    ]

    AGUARDANDO_RESULTADO = "AGUARDANDO_RESULTADO"
    REALIZADO = "REALIZADO"
    FALTA = "FALTA"
    RESULTADO_CHOICES = [
        (AGUARDANDO_RESULTADO, "Aguardando Resultado"), 
        (REALIZADO, "Realizado"), (FALTA, "Falta")
    ]

    MOTIVOS_CANCELAMENTO = [
        ("CLIENTE", "Cliente"), ("CLINICA", "Clínica"), ("REAGENDADO", "Reagendado"),
        ("SUBSTITUICAO", "Substituição"), ("EXPIRADO", "Expirado"), 
        ("SOBREPOSICAO", "Sobreposição"), ("PACOTE_CANCELADO", "Pacote Cancelado")
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name="agendamentos")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="agendamentos")
    profissional = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="agendamentos_profissional")
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, related_name="agendamentos")
    
    agendamento_anterior = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reagendamentos"
    )

    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDENTE)
    resultado = models.CharField(max_length=30, choices=RESULTADO_CHOICES, default=AGUARDANDO_RESULTADO)
    motivo_cancelamento = models.CharField(max_length=30, choices=MOTIVOS_CANCELAMENTO, null=True, blank=True)
    
    observacoes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agendamentos"
        indexes = [
            models.Index(fields=["clinica", "status"], name="idx_agendamento_clinica_status"),
            models.Index(fields=["profissional", "data_hora_inicio"], name="idx_agendamento_prof_data"),
            models.Index(fields=["cliente", "data_hora_inicio"], name="idx_agendamento_cliente_data"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(data_hora_inicio__lt=F('data_hora_fim')),
                name="chk_agendamento_datas_validas"
            ),
            ExclusionConstraint(
                name="chk_sobreposicao_profissional",
                expressions=[
                    (Func(F("data_hora_inicio"), F("data_hora_fim"), function="TSTZRANGE"), RangeOperators.OVERLAPS),
                    ("profissional", RangeOperators.EQUAL),
                ],
                condition=Q(status="CONFIRMADO")
            ),
            ExclusionConstraint(
                name="chk_sobreposicao_cliente",
                expressions=[
                    (Func(F("data_hora_inicio"), F("data_hora_fim"), function="TSTZRANGE"), RangeOperators.OVERLAPS),
                    ("cliente", RangeOperators.EQUAL),
                ],
                condition=Q(status="CONFIRMADO")
            )
        ]

    def clean(self):
        super().clean()
        if self.cliente and self.clinica and self.cliente.clinica_id != self.clinica.id:
            raise ValidationError("O cliente deve pertencer à clínica do agendamento.")
        if self.profissional and self.clinica and self.profissional.clinica_id != self.clinica.id:
            raise ValidationError("O profissional deve pertencer à clínica do agendamento.")
        if self.servico and self.clinica and self.servico.clinica_id != self.clinica.id:
            raise ValidationError("O serviço deve pertencer à clínica do agendamento.")

class Pacote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinica = models.ForeignKey(Clinica, on_delete=models.PROTECT, related_name="pacotes")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="pacotes")
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, related_name="pacotes")
    
    quantidade_contratada = models.PositiveIntegerField()
    ativo = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pacotes"
        indexes = [
            models.Index(fields=["cliente", "ativo"], name="idx_pacote_cliente_ativo"),
        ]

    def __str__(self):
        return f"Pacote: {self.servico.nome} - {self.cliente.usuario.nome_completo}"

class SessaoPacote(models.Model):
    DISPONIVEL = "DISPONIVEL"
    AGENDADA = "AGENDADA"
    UTILIZADA = "UTILIZADA"
    PERDIDA = "PERDIDA"
    CANCELADA = "CANCELADA"

    ESTADO_CHOICES = [
        (DISPONIVEL, "Disponível"), (AGENDADA, "Agendada"),
        (UTILIZADA, "Utilizada"), (PERDIDA, "Perdida"), (CANCELADA, "Cancelada")
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pacote = models.ForeignKey(Pacote, on_delete=models.PROTECT, related_name="sessoes")
    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessoes_associadas"
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=DISPONIVEL)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sessoes_pacote"
        indexes = [
            models.Index(fields=["pacote", "estado"], name="idx_sessao_pacote_estado"),
        ]

    def __str__(self):
        return f"Sessão {self.id} - {self.estado}"

class HistoricoSessao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sessao = models.ForeignKey(SessaoPacote, on_delete=models.PROTECT, related_name="historico")
    pacote = models.ForeignKey(Pacote, on_delete=models.PROTECT, related_name="historico_sessoes")
    
    agendamento_relacionado = models.ForeignKey(
        Agendamento, on_delete=models.SET_NULL, null=True, blank=True, related_name="historico_sessoes"
    )
    usuario_executor = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="historico_sessoes_executadas"
    )
    
    estado_anterior = models.CharField(max_length=20, choices=SessaoPacote.ESTADO_CHOICES, null=True, blank=True)
    estado_posterior = models.CharField(max_length=20, choices=SessaoPacote.ESTADO_CHOICES)
    
    motivo = models.CharField(max_length=100)
    justificativa = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historico_sessoes"
        indexes = [
            models.Index(fields=["sessao", "created_at"], name="idx_historico_sessao_data"),
        ]