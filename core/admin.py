from django.contrib import admin
from .models import Usuario, Clinica, Colaborador, Cliente, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('nome',)


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('cpf', 'nome_completo', 'is_staff', 'is_active')


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'cnpj', 'ativo')


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'clinica', 'role', 'ativo')


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'clinica', 'telefone', 'status_cadastro')