from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.forms import ModelForm

from .models import (
    Agendamento,
    Auditoria,
    Cliente,
    Clinica,
    Colaborador,
    Especialidade,
    HistoricoSessao,
    Pacote,
    Role,
    Servico,
    SessaoPacote,
    Usuario,
)
from .validators import (
    validar_cpf,
    validar_cnpj,
    validar_telefone,
    validar_telefone_opcional,
    validar_cep,
)

MAX_INTEGER = 2147483647

def widget_numerico(maxlength):
    return forms.TextInput(
        attrs={
            "maxlength": str(maxlength),
            "inputmode": "numeric",
            "pattern": "[0-9]*",
            "autocomplete": "off",
            "oninput": (
                "this.value = this.value.replace(/[^0-9]/g, '').slice(0, "
                f"{maxlength});"
            ),
        }
    )

class UsuarioAdminForm(ModelForm):
    cpf = forms.CharField(
        max_length=11,
        label="CPF",
        widget=widget_numerico(11),
        error_messages={
            "max_length": "O CPF deve conter exatamente 11 dígitos.",
        },
    )
    telefone = forms.CharField(
        max_length=11,
        required=False,
        label="Telefone",
        widget=widget_numerico(11),
        error_messages={
            "max_length": "O telefone deve conter no máximo 11 dígitos.",
        },
    )
    nova_senha = forms.CharField(
        label="Nova senha",
        required=False,
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
        help_text="Preencha somente se quiser definir ou alterar a senha.",
    )

    class Meta:
        model = Usuario
        fields = (
            "cpf",
            "nome_completo",
            "data_nascimento",
            "telefone",
            "is_staff",
            "is_superuser",
            "is_active",
            "nova_senha",
        )

    def clean_cpf(self):
        return validar_cpf(self.cleaned_data["cpf"])

    def clean_telefone(self):
        return validar_telefone_opcional(
            self.cleaned_data.get("telefone", "")
        )

    def clean_nome_completo(self):
        nome = self.cleaned_data["nome_completo"].strip()

        if not nome:
            raise ValidationError("O nome completo é obrigatório.")

        return nome

class ClinicaAdminForm(ModelForm):
    cnpj = forms.CharField(
        max_length=14,
        label="CNPJ",
        widget=widget_numerico(14),
        error_messages={
            "max_length": "O CNPJ deve conter exatamente 14 dígitos.",
        },
    )
    telefone = forms.CharField(
        max_length=11,
        label="Telefone",
        widget=widget_numerico(11),
        error_messages={
            "max_length": "O telefone deve conter no máximo 11 dígitos.",
        },
    )

    class Meta:
        model = Clinica
        fields = "__all__"

    def clean_cnpj(self):
        return validar_cnpj(self.cleaned_data["cnpj"])

    def clean_telefone(self):
        return validar_telefone(self.cleaned_data["telefone"])

    def clean_razao_social(self):
        valor = self.cleaned_data["razao_social"].strip()

        if not valor:
            raise ValidationError("A razão social é obrigatória.")

        return valor

    def clean_nome_fantasia(self):
        valor = self.cleaned_data["nome_fantasia"].strip()

        if not valor:
            raise ValidationError("O nome fantasia é obrigatório.")

        return valor

class ClienteAdminForm(ModelForm):
    telefone = forms.CharField(
        max_length=11,
        label="Telefone",
        widget=widget_numerico(11),
        error_messages={
            "max_length": "O telefone deve conter no máximo 11 dígitos.",
        },
    )
    cep = forms.CharField(
        max_length=8,
        required=False,
        label="CEP",
        widget=widget_numerico(8),
        error_messages={
            "max_length": "O CEP deve conter no máximo 8 dígitos.",
        },
    )

    class Meta:
        model = Cliente
        fields = "__all__"

    def clean_telefone(self):
        return validar_telefone(self.cleaned_data["telefone"])

    def clean_cep(self):
        cep = self.cleaned_data.get("cep", "")

        if not cep or not cep.strip():
            return ""

        return validar_cep(cep)

    def clean_numero_endereco(self):
        return self.cleaned_data.get("numero_endereco", "").strip()

class ServicoAdminForm(ModelForm):
    class Meta:
        model = Servico
        fields = "__all__"

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()

        if not nome:
            raise ValidationError("O nome do serviço é obrigatório.")

        return nome

    def clean_duracao_padrao_minutos(self):
        duracao = self.cleaned_data["duracao_padrao_minutos"]

        if not 1 <= duracao <= MAX_INTEGER:
            raise ValidationError(
                "A duração deve ser um número inteiro positivo válido."
            )

        return duracao

class PacoteAdminForm(ModelForm):
    class Meta:
        model = Pacote
        fields = "__all__"

    def clean_quantidade_sessoes(self):
        quantidade = self.cleaned_data["quantidade_sessoes"]

        if not 1 <= quantidade <= MAX_INTEGER:
            raise ValidationError(
                "A quantidade de sessões deve ser um inteiro positivo válido."
            )

        return quantidade

    def clean_valor_total(self):
        valor = self.cleaned_data["valor_total"]

        if valor < 0:
            raise ValidationError(
                "O valor total do pacote não pode ser negativo."
            )

        return valor

    def clean(self):
        cleaned_data = super().clean()

        clinica = cleaned_data.get("clinica")
        cliente = cleaned_data.get("cliente")
        servico = cleaned_data.get("servico")

        if clinica is not None and cliente is not None:
            if cliente.clinica_id != clinica.pk:
                self.add_error(
                    "cliente",
                    "O cliente não pertence à clínica selecionada.",
                )

        if clinica is not None and servico is not None:
            if servico.clinica_id != clinica.pk:
                self.add_error(
                    "servico",
                    "O serviço não pertence à clínica selecionada.",
                )

        return cleaned_data

@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    form = ClinicaAdminForm

    list_display = (
        "nome_fantasia",
        "razao_social",
        "cnpj",
        "telefone",
        "profissionais_podem_editar_agenda",
    )
    search_fields = ("nome_fantasia", "razao_social", "cnpj")
    list_filter = ("profissionais_podem_editar_agenda", "ativo")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    form = UsuarioAdminForm

    list_display = (
        "cpf",
        "nome_completo",
        "telefone",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    search_fields = ("cpf", "nome_completo")
    list_filter = ("is_staff", "is_superuser", "is_active")
    ordering = ("nome_completo",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_login",
    )
    fields = (
        "id",
        "cpf",
        "nome_completo",
        "data_nascimento",
        "telefone",
        "nova_senha",
        "is_staff",
        "is_superuser",
        "is_active",
        "last_login",
        "created_at",
        "updated_at",
    )

    def save_model(self, request, obj, form, change):
        nova_senha = form.cleaned_data.get("nova_senha")

        if nova_senha:
            obj.password = make_password(nova_senha)
        elif not change and not obj.password:
            obj.set_unusable_password()

        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    form = ClienteAdminForm

    list_display = ("usuario", "clinica", "telefone", "status_cadastro")
    search_fields = ("usuario__nome_completo", "usuario__cpf")
    list_filter = ("status_cadastro",)
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    form = ServicoAdminForm

    list_display = (
        "nome",
        "clinica",
        "duracao_padrao_minutos",
        "ativo",
    )
    search_fields = ("nome",)
    list_filter = ("ativo",)
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Pacote)
class PacoteAdmin(admin.ModelAdmin):
    form = PacoteAdminForm

    list_display = (
        "cliente",
        "servico",
        "quantidade_sessoes",
        "valor_total",
        "status",
    )
    search_fields = (
        "cliente__usuario__nome_completo",
        "servico__nome",
    )
    list_filter = ("status",)
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Especialidade)
class EspecialidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "clinica")
    list_filter = ("clinica",)
    search_fields = ("nome", "clinica__nome_fantasia")

@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ("usuario", "clinica", "role", "ativo")
    list_filter = ("clinica", "role", "ativo")
    search_fields = ("usuario__nome_completo", "clinica__nome_fantasia")
    filter_horizontal = ("especialidades",)

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(SessaoPacote)
class SessaoPacoteAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "data_hora",
        "clinica",
        "usuario",
        "acao",
        "entidade",
        "objeto_id",
        "origem",
    )
    list_filter = (
        "acao",
        "entidade",
        "origem",
        "data_hora",
    )
    search_fields = (
        "objeto_id",
        "entidade",
        "usuario__cpf",
        "clinica__nome_fantasia",
    )
    readonly_fields = (
        "clinica",
        "usuario",
        "acao",
        "entidade",
        "objeto_id",
        "dados_anteriores",
        "dados_novos",
        "origem",
        "ip",
        "user_agent",
        "data_hora",
    )
    date_hierarchy = "data_hora"
    ordering = ("-data_hora",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(HistoricoSessao)
class HistoricoSessaoAdmin(admin.ModelAdmin):
    list_display = (
        "sessao",
        "estado_anterior",
        "estado_novo",
        "usuario_executor",
        "data_alteracao",
    )
    list_filter = (
        "estado_anterior",
        "estado_novo",
        "data_alteracao",
    )
    search_fields = (
        "sessao__id",
        "motivo",
        "justificativa",
    )
    readonly_fields = (
        "sessao",
        "estado_anterior",
        "estado_novo",
        "usuario_executor",
        "agendamento_relacionado",
        "motivo",
        "justificativa",
        "data_alteracao",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False