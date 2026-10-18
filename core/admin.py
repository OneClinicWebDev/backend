from django.contrib import admin

from .models import (
    Auditoria,
    Cliente,
    Clinica,
    Colaborador,
    ColaboradorEspecialidade,
    Especialidade,
    Role,
    Usuario,
)


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "cpf",
        "nome_completo",
        "data_nascimento",
        "is_staff",
        "is_superuser",
        "is_active",
        "date_joined",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
    )
    search_fields = (
        "cpf",
        "nome_completo",
    )
    readonly_fields = (
        "id",
        "date_joined",
        "updated_at",
    )


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = (
        "nome_fantasia",
        "razao_social",
        "cnpj",
        "telefone",
        "email",
        "profissionais_podem_editar_agenda",
        "ativo",
        "created_at",
    )
    list_filter = (
        "ativo",
        "profissionais_podem_editar_agenda",
    )
    search_fields = (
        "nome_fantasia",
        "razao_social",
        "cnpj",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
    )
    search_fields = (
        "nome",
    )


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "clinica",
        "role",
        "pode_editar_agenda",
        "ativo",
        "created_at",
    )
    list_filter = (
        "ativo",
        "pode_editar_agenda",
        "role",
        "clinica",
    )
    search_fields = (
        "usuario__cpf",
        "usuario__nome_completo",
        "clinica__nome_fantasia",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )


@admin.register(Especialidade)
class EspecialidadeAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "clinica",
        "ativo",
        "created_at",
    )
    list_filter = (
        "ativo",
        "clinica",
    )
    search_fields = (
        "nome",
        "clinica__nome_fantasia",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )


@admin.register(ColaboradorEspecialidade)
class ColaboradorEspecialidadeAdmin(admin.ModelAdmin):
    list_display = (
        "colaborador",
        "especialidade",
        "ativo",
        "created_at",
    )
    list_filter = (
        "ativo",
        "especialidade",
    )
    search_fields = (
        "colaborador__usuario__cpf",
        "colaborador__usuario__nome_completo",
        "especialidade__nome",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "clinica",
        "telefone",
        "status_cadastro",
        "status_financeiro",
        "created_at",
    )
    list_filter = (
        "status_cadastro",
        "status_financeiro",
        "clinica",
    )
    search_fields = (
        "usuario__cpf",
        "usuario__nome_completo",
        "telefone",
        "email",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "acao",
        "entidade",
        "objeto_id",
        "usuario",
        "clinica",
        "ip",
    )
    list_filter = (
        "acao",
        "entidade",
        "clinica",
    )
    search_fields = (
        "objeto_id",
        "entidade",
        "usuario__cpf",
        "usuario__nome_completo",
    )
    readonly_fields = (
        "id",
        "usuario",
        "clinica",
        "acao",
        "entidade",
        "objeto_id",
        "dados_anteriores",
        "dados_novos",
        "ip",
        "user_agent",
        "created_at",
    )