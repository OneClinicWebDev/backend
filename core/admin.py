
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
)


class UsuarioAdminForm(ModelForm):
    cpf = forms.CharField(max_length=14, label="CPF")
    telefone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
    )
    nova_senha = forms.CharField(
        label="Nova senha",
        required=False,
        widget=forms.PasswordInput,
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
            "nova_senha",
        )

    def clean_cpf(self):
        return validar_cpf(self.cleaned_data["cpf"])

    def clean_telefone(self):
        return validar_telefone_opcional(
            self.cleaned_data.get("telefone", "")
        )


class ClinicaAdminForm(ModelForm):
    cnpj = forms.CharField(max_length=18, label="CNPJ")
    telefone = forms.CharField(max_length=20, label="Telefone")

    class Meta:
        model = Clinica
        fields = "__all__"

    def clean_cnpj(self):
        return validar_cnpj(self.cleaned_data["cnpj"])

    def clean_telefone(self):
        return validar_telefone(self.cleaned_data["telefone"])


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
    list_filter = ("profissionais_podem_editar_agenda",)
    readonly_fields = ("id", "created_at", "updated_at")


class ClienteAdminForm(ModelForm):
    telefone = forms.CharField(max_length=20, label="Telefone")

    class Meta:
        model = Cliente
        fields = "__all__"

    def clean_telefone(self):
        return validar_telefone(self.cleaned_data["telefone"])


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    form = UsuarioAdminForm

    list_display = (
        "cpf",
        "nome_completo",
        "telefone",
        "is_staff",
        "is_superuser",
    )
    search_fields = ("cpf", "nome_completo")
    list_filter = ("is_staff", "is_superuser")
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


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    form = ClienteAdminForm

    list_display = ("usuario", "clinica", "telefone", "status_cadastro")
    search_fields = ("usuario__nome_completo", "usuario__cpf")
    list_filter = ("status_cadastro",)
    readonly_fields = ("id", "created_at", "updated_at")


admin.site.register(Role)
admin.site.register(Colaborador)
admin.site.register(Servico)
admin.site.register(Pacote)
admin.site.register(Agendamento)
admin.site.register(SessaoPacote)
admin.site.register(HistoricoSessao)
admin.site.register(Auditoria)
