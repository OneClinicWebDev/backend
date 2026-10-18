from django.contrib import admin
from .models import Usuario, Clinica, Role, Cliente, Colaborador, Servico, Pacote, Agendamento, SessaoPacote, Auditoria

admin.site.register(Usuario)
admin.site.register(Clinica)
admin.site.register(Role)
admin.site.register(Cliente)
admin.site.register(Colaborador)
admin.site.register(Servico)
admin.site.register(Pacote)
admin.site.register(Agendamento)
admin.site.register(SessaoPacote)
admin.site.register(Auditoria)