from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Clinica, Colaborador, Cliente

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('cpf', 'nome_completo', 'is_staff', 'is_active', 'date_joined')
    list_display_links = ('cpf', 'nome_completo')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('cpf', 'nome_completo')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('cpf', 'password')}),
        ('Informações Pessoais', {'fields': ('nome_completo',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ('date_joined', 'last_login')

@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'cnpj', 'ativo', 'created_at')
    search_fields = ('nome_fantasia', 'cnpj')
    list_filter = ('ativo',)

@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('get_usuario_nome', 'get_clinica_nome', 'role', 'ativo')
    list_filter = ('role', 'ativo', 'clinica')
    search_fields = ('usuario__nome_completo', 'usuario__cpf')
    def get_usuario_nome(self, obj):
        return obj.usuario.nome_completo
    get_usuario_nome.short_description = 'Colaborador'

    def get_clinica_nome(self, obj):
        return obj.clinica.nome_fantasia
    get_clinica_nome.short_description = 'Clínica'

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'get_clinica_nome', 'status_cadastro', 'status_financeiro')
    list_filter = ('status_cadastro', 'status_financeiro', 'clinica')
    search_fields = ('nome', 'cpf')

    def get_clinica_nome(self, obj):
        return obj.clinica.nome_fantasia
    get_clinica_nome.short_description = 'Clínica'