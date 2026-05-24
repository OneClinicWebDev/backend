import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


# =========================
# USER MANAGER
# =========================
class UsuarioManager(BaseUserManager):
    def create_user(self, cpf, password=None, **extra_fields):
        if not cpf:
            raise ValueError("CPF é obrigatório")

        user = self.model(cpf=cpf, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, cpf, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(cpf, password, **extra_fields)


# =========================
# USER
# =========================
class Usuario(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.CharField(max_length=11, unique=True)
    nome_completo = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "cpf"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "usuarios"


# =========================
# CLINICA
# =========================
class Clinica(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cnpj = models.CharField(max_length=14, unique=True)
    nome_fantasia = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinicas"


# =========================
# ROLE (RBAC PRÓPRIO)
# =========================
class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "roles"

    def __str__(self):
        return self.nome


# =========================
# COLABORADOR
# =========================
class Colaborador(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)

    especialidade = models.CharField(max_length=100, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "colaboradores"
        unique_together = ("usuario", "clinica")


# =========================
# CLIENTE
# =========================
class Cliente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE)

    telefone = models.CharField(max_length=20)
    email = models.EmailField()
    endereco_completo = models.TextField()

    status_cadastro = models.CharField(max_length=20, default="ATIVO")
    status_financeiro = models.CharField(max_length=20, default="EM_DIA")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clientes"
        unique_together = ("usuario", "clinica")

        permissions = [
            ("can_view_all_clients", "Pode ver todos os clientes"),
            ("can_manage_finance", "Pode gerenciar financeiro"),
        ]