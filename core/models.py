import uuid
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.postgres.constraints import ExclusionConstraint
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from .validators import validar_cpf, validar_cnpj

validate_cpf = validar_cpf
validate_cnpj = validar_cnpj

class UsuarioManager(BaseUserManager):
    def create_user(
        self,
        cpf,
        nome_completo,
        data_nascimento,
        password=None,
        **extra_fields,
    ):
        if not cpf:
            raise ValueError("O CPF é obrigatório.")
        cpf = validar_cpf(cpf)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)
        user = self.model(
            cpf=cpf,
            nome_completo=nome_completo,
            data_nascimento=data_nascimento,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        cpf,
        nome_completo,
        data_nascimento,
        password=None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser precisa ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa ter is_superuser=True.")
        return self.create_user(
            cpf=cpf,
            nome_completo=nome_completo,
            data_nascimento=data_nascimento,
            password=password,
            **extra_fields,
        )

class Usuario(AbstractBaseUser):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    cpf = models.CharField(
        max_length=11,
        unique=True,
        validators=[validar_cpf],
    )
    nome_completo = models.CharField(max_length=255)
    data_nascimento = models.DateField()
    telefone = models.CharField(max_length=20, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    objects = UsuarioManager()
    USERNAME_FIELD = "cpf"
    REQUIRED_FIELDS = ["nome_completo", "data_nascimento"]

    class Meta:
        db_table = "usuarios"

    def __str__(self):
        return self.nome_completo

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

class Clinica(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    cnpj = models.CharField(
        max_length=14,
        unique=True,
        validators=[validar_cnpj],
    )
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255)
    telefone = models.CharField(max_length=20)
    endereco = models.CharField(max_length=255, blank=True)
    profissionais_podem_editar_agenda = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "clinicas"
        constraints = [
            models.CheckConstraint(
                condition=Q(cnpj__regex=r"^[0-9]{14}$"),
                name="chk_cnpj_format",
            ),
            models.CheckConstraint(
                condition=Q(telefone__regex=r"^[0-9]+$"),
                name="chk_clinica_telefone_format",
            ),
        ]

    def __str__(self):
        return self.nome_fantasia

class Role(models.Model):
    ADMIN = "ADMIN"
    SECRETARIO = "SECRETARIO"
    PROFISSIONAL = "PROFISSIONAL"
    ROLE_CHOICES = [
        (ADMIN, "Administrador"),
        (SECRETARIO, "Secretário"),
        (PROFISSIONAL, "Profissional"),
    ]
    nome = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "roles"

    def __str__(self):
        return self.nome

class Especialidade(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.CASCADE,
        related_name="especialidades"
    )
    nome = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "especialidades"
        unique_together = ("clinica", "nome")

    def __str__(self):
        return self.nome

class Cliente(models.Model):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    STATUS_CHOICES = [
        (ATIVO, "Ativo"),
        (INATIVO, "Inativo"),
    ]
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vinculos_cliente",
    )
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="clientes",
    )
    telefone = models.CharField(max_length=20)
    cep = models.CharField(max_length=8, blank=True)
    numero_endereco = models.CharField(max_length=20, blank=True)
    status_cadastro = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=ATIVO,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clientes"
        unique_together = ("usuario", "clinica")

    def __str__(self):
        return self.usuario.nome_completo

class Colaborador(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vinculos_colaborador",
    )
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="colaboradores",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
    )
    ativo = models.BooleanField(default=True)
    pode_editar_agenda = models.BooleanField(default=False)
    especialidades = models.ManyToManyField(
        Especialidade,
        related_name="profissionais",
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "colaboradores"
        unique_together = ("usuario", "clinica")

    def __str__(self):
        return f"{self.usuario.nome_completo} - {self.clinica.nome_fantasia}"

class Servico(models.Model):
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="servicos",
    )
    nome = models.CharField(max_length=255)
    preco = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    duracao_padrao_minutos = models.PositiveIntegerField()
    categoria = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    descricao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_servico"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

class ModeloPacote(models.Model):
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="modelos_pacote",
    )
    nome = models.CharField(max_length=255)
    servico = models.ForeignKey(
        Servico,
        on_delete=models.PROTECT,
        related_name="modelos_pacote",
    )
    quantidade_sessoes = models.PositiveIntegerField()
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    categoria = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    descricao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "modelos_pacote"
        ordering = ["nome"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantidade_sessoes__gte=1),
                name="chk_modelo_pacote_sessoes_positivas",
            ),
            models.CheckConstraint(
                condition=Q(valor_total__gte=0),
                name="chk_modelo_pacote_valor_nao_negativo",
            ),
        ]

    def __str__(self):
        return self.nome

class Pacote(models.Model):
    ATIVO = "ATIVO"
    CONCLUIDO = "CONCLUIDO"
    CANCELADO = "CANCELADO"
    STATUS_CHOICES = [
        (ATIVO, "Ativo"),
        (CONCLUIDO, "Concluído"),
        (CANCELADO, "Cancelado"),
    ]
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="pacotes",
    )

    modelo = models.ForeignKey(
        ModeloPacote,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="aquisicoes",
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pacotes",
    )
    servico = models.ForeignKey(
        Servico,
        on_delete=models.PROTECT,
        related_name="pacotes",
    )
    quantidade_sessoes = models.PositiveIntegerField()
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=ATIVO,
    )
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pacotes"

    @property
    def saldo_sessoes(self):
        return self.sessoes.filter(
            status__in=[
                SessaoPacote.DISPONIVEL,
                SessaoPacote.AGENDADA,
            ]
        ).count()

    def __str__(self):
        return f"Pacote {self.pk}"

class ExclusaoFisicaBloqueadaQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError(
            "A exclusão física não é permitida para este registro."
        )

objects = ExclusaoFisicaBloqueadaQuerySet.as_manager()

class Agendamento(models.Model):
    PENDENTE = "PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    CONCLUIDO = "CONCLUIDO"
    CANCELADO = "CANCELADO"
    STATUS_CHOICES = [
        (PENDENTE, "Pendente"),
        (CONFIRMADO, "Confirmado"),
        (CONCLUIDO, "Concluído"),
        (CANCELADO, "Cancelado"),
    ]
    AGUARDANDO_RESULTADO = "AGUARDANDO_RESULTADO"
    REALIZADO = "REALIZADO"
    FALTA = "FALTA"
    RESULTADO_CHOICES = [
        (AGUARDANDO_RESULTADO, "Aguardando resultado"),
        (REALIZADO, "Realizado"),
        (FALTA, "Falta"),
    ]
    objects = ExclusaoFisicaBloqueadaQuerySet.as_manager()
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="agendamentos",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="agendamentos",
    )
    profissional = models.ForeignKey(
        Colaborador,
        on_delete=models.PROTECT,
        related_name="agendamentos_profissional",
    )
    servico = models.ForeignKey(
        Servico,
        on_delete=models.PROTECT,
        related_name="agendamentos",
    )
    pacote_origem = models.ForeignKey(
        Pacote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agendamentos",
    )
    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDENTE,
    )
    resultado = models.CharField(
        max_length=30,
        choices=RESULTADO_CHOICES,
        default=AGUARDANDO_RESULTADO,
    )
    motivo_cancelamento = models.CharField(max_length=50, blank=True)
    observacoes = models.TextField(blank=True)
    preco_acordado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agendamentos"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_hora_fim__gt=F("data_hora_inicio")),
                name="chk_data_fim_maior_inicio",
            ),
            ExclusionConstraint(
                name="chk_sobreposicao_profissional",
                expressions=[
                    ("profissional", "="),
                    (
                        models.Func(
                            F("data_hora_inicio"),
                            F("data_hora_fim"),
                            function="tstzrange",
                        ),
                        "&&",
                    ),
                ],
                condition=Q(status="CONFIRMADO"),
            ),
            ExclusionConstraint(
                name="chk_sobreposicao_cliente",
                expressions=[
                    ("cliente", "="),
                    (
                        models.Func(
                            F("data_hora_inicio"),
                            F("data_hora_fim"),
                            function="tstzrange",
                        ),
                        "&&",
                    ),
                ],
                condition=Q(status="CONFIRMADO"),
            ),
        ]

    def __str__(self):
        return f"Agendamento {self.pk}"

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Agendamentos não podem ser excluídos fisicamente. Utilize o cancelamento."
        )

class SessaoPacote(models.Model):
    DISPONIVEL = "DISPONIVEL"
    AGENDADA = "AGENDADA"
    UTILIZADA = "UTILIZADA"
    PERDIDA = "PERDIDA"
    CANCELADA = "CANCELADA"
    STATUS_CHOICES = [
        (DISPONIVEL, "Disponível"),
        (AGENDADA, "Agendada"),
        (UTILIZADA, "Utilizada"),
        (PERDIDA, "Perdida"),
        (CANCELADA, "Cancelada"),
    ]
    objects = ExclusaoFisicaBloqueadaQuerySet.as_manager()
    pacote = models.ForeignKey(
        Pacote,
        on_delete=models.PROTECT,
        related_name="sessoes",
    )
    agendamento = models.OneToOneField(
        Agendamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessao_pacote",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DISPONIVEL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    TRANSICOES_PERMITIDAS = {
        DISPONIVEL: {AGENDADA, CANCELADA},
        AGENDADA: {DISPONIVEL, UTILIZADA, PERDIDA, CANCELADA},
        UTILIZADA: {DISPONIVEL, PERDIDA},
        PERDIDA: set(),
        CANCELADA: set(),
    }

    class Meta:
        db_table = "sessoes_pacote"

    def __str__(self):
        return f"Sessão {self.pk} - {self.status}"

    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            return
        with transaction.atomic():
            anterior = (
                type(self)
                .objects.select_for_update()
                .filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
            if anterior is not None and anterior != self.status:
                permitidos = self.TRANSICOES_PERMITIDAS.get(anterior, set())
                if self.status not in permitidos:
                    raise ValidationError(
                        f"Transição de sessão não permitida: {anterior} para {self.status}."
                    )
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Sessões de pacotes não podem ser excluídas fisicamente."
        )

class HistoricoSessao(models.Model):
    sessao = models.ForeignKey(
        SessaoPacote,
        on_delete=models.PROTECT,
        related_name="historico",
    )
    estado_anterior = models.CharField(max_length=20, blank=True)
    estado_novo = models.CharField(max_length=20)
    usuario_executor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historicos_sessao_executados",
    )
    agendamento_relacionado = models.ForeignKey(
        Agendamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historicos_sessao",
    )
    motivo = models.CharField(max_length=255, blank=True)
    justificativa = models.TextField(blank=True)
    data_alteracao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historico_sessoes"

    @property
    def created_at(self):
        return self.data_alteracao

    def __str__(self):
        return f"Histórico da sessão {self.sessao_id}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(
                "Registros do histórico de sessões são imutáveis."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Registros do histórico de sessões não podem ser excluídos."
        )

class ProcedimentoRealizado(models.Model):
    REALIZADO = "REALIZADO"
    ESTORNADO = "ESTORNADO"
    STATUS_CHOICES = [
        (REALIZADO, "Realizado"),
        (ESTORNADO, "Estornado"),
    ]
    ORIGEM_AUTOMATICA = "AUTOMATICA"
    ORIGEM_MANUAL = "MANUAL"
    ORIGEM_MIGRACAO = "MIGRACAO"
    ORIGEM_CHOICES = [
        (ORIGEM_AUTOMATICA, "Conclusão automática"),
        (ORIGEM_MANUAL, "Conclusão manual"),
        (ORIGEM_MIGRACAO, "Migração de histórico"),
    ]
    DESTINO_DEVOLVIDA = "DEVOLVIDA"
    DESTINO_PERDIDA = "PERDIDA"
    DESTINO_NAO_APLICAVEL = "NAO_APLICAVEL"
    DESTINO_CHOICES = [
        (DESTINO_DEVOLVIDA, "Sessão devolvida"),
        (DESTINO_PERDIDA, "Sessão perdida"),
        (DESTINO_NAO_APLICAVEL, "Sem sessão de pacote"),
    ]
    CAMPOS_ESTORNO = {
        "destino_sessao",
        "status",
        "estornado_em",
        "estornado_por",
        "motivo_estorno",
        "updated_at",
    }
    objects = ExclusaoFisicaBloqueadaQuerySet.as_manager()
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="procedimentos_realizados",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="procedimentos_realizados",
    )
    profissional = models.ForeignKey(
        Colaborador,
        on_delete=models.PROTECT,
        related_name="procedimentos_realizados",
    )
    servico = models.ForeignKey(
        Servico,
        on_delete=models.PROTECT,
        related_name="procedimentos_realizados",
    )
    agendamento = models.OneToOneField(
        Agendamento,
        on_delete=models.PROTECT,
        related_name="procedimento_realizado",
    )
    pacote = models.ForeignKey(
        Pacote,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="procedimentos_realizados",
    )
    sessao = models.ForeignKey(
        SessaoPacote,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="procedimentos_realizados",
    )
    cliente_nome = models.CharField(max_length=255)
    profissional_nome = models.CharField(max_length=255)
    servico_nome = models.CharField(max_length=255)
    pacote_nome = models.CharField(max_length=255, blank=True, default="")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    duracao_minutos = models.PositiveIntegerField()
    realizado_em = models.DateTimeField()
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procedimentos_registrados",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=REALIZADO,
    )
    estornado_em = models.DateTimeField(null=True, blank=True)
    estornado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procedimentos_estornados",
    )
    motivo_estorno = models.TextField(blank=True, default="")
    destino_sessao = models.CharField(
        max_length=20,
        choices=DESTINO_CHOICES,
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "procedimentos_realizados"
        ordering = ["-realizado_em", "-pk"]
        indexes = [
            models.Index(
                fields=["cliente", "realizado_em"],
                name="idx_proc_cliente_data",
            ),
            models.Index(
                fields=["clinica", "realizado_em"],
                name="idx_proc_clinica_data",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gte=0),
                name="chk_proc_realizado_valor_nao_negativo",
            ),
        ]

    def __str__(self):
        return f"Procedimento realizado {self.pk}"

    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            return
        with transaction.atomic():
            anterior = (
                type(self)
                .objects.select_for_update()
                .filter(pk=self.pk)
                .first()
            )
            if anterior is not None:
                if anterior.status == self.ESTORNADO:
                    raise ValidationError(
                        "Procedimentos estornados são imutáveis."
                    )
                for campo in self._meta.concrete_fields:
                    if campo.name in self.CAMPOS_ESTORNO:
                        continue
                    if getattr(anterior, campo.attname) != getattr(
                        self, campo.attname
                    ):
                        raise ValidationError(
                            "Registros de procedimentos realizados são "
                            "imutáveis, exceto pelo estorno."
                        )
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Procedimentos realizados não podem ser excluídos."
        )

class AuditoriaQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(
            "Registros de auditoria não podem ser alterados em lote."
        )

    def delete(self):
        raise ValidationError(
            "Registros de auditoria não podem ser excluídos em lote."
        )

class Auditoria(models.Model):
    objects = AuditoriaQuerySet.as_manager()
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DEACTIVATE = "DEACTIVATE"
    ACAO_CHOICES = [
        (CREATE, "Criação"),
        (UPDATE, "Atualização"),
        (DELETE, "Exclusão"),
        (DEACTIVATE, "Desativação"),
    ]
    ORIGEM_CHOICES = [
        ("USUARIO", "Usuário via API"),
        ("SISTEMA", "Rotina Automática / Sistema"),
    ]
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="auditorias",
    )   
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias",
    )
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    entidade = models.CharField(max_length=50)
    objeto_id = models.CharField(max_length=255)
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    origem = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default="USUARIO",
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auditoria"
        ordering = ["-data_hora"]

    @property
    def created_at(self):
        return self.data_hora

    def __str__(self):
        return f"{self.entidade} - {self.acao} - {self.objeto_id}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(
                "Registros de auditoria são imutáveis."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Registros de auditoria não podem ser excluídos."
        )

class PrimeiroAcessoCodigo(models.Model):
    objects = ExclusaoFisicaBloqueadaQuerySet.as_manager()
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.PROTECT,
        related_name="codigos_primeiro_acesso",
    )
    codigo_hash = models.CharField(max_length=255)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)
    invalidado_em = models.DateTimeField(null=True, blank=True)
    tentativas_falhas = models.PositiveSmallIntegerField(default=0)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="codigos_primeiro_acesso_gerados",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "codigos_primeiro_acesso"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["colaborador", "usado_em", "invalidado_em"],
                name="idx_primeiro_acesso_ativo",
            ),
        ]

    def __str__(self):
        return f"Código de primeiro acesso {self.pk}"

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Códigos de primeiro acesso não podem ser excluídos fisicamente."
        )