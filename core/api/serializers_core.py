from rest_framework import serializers
from core.models import (
    Usuario, Clinica, Role, Colaborador, Cliente, 
    Servico, Agendamento, Pacote, SessaoPacote
)

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'cpf', 'nome_completo', 'data_nascimento', 'telefone']

class ClinicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinica
        fields = '__all__'

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class ColaboradorSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.nome_completo', read_only=True)
    role_nome = serializers.CharField(source='role.nome', read_only=True)

    class Meta:
        model = Colaborador
        fields = ['id', 'usuario', 'usuario_nome', 'clinica', 'role', 'role_nome', 'ativo', 'pode_editar_agenda']

class ClienteSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.nome_completo', read_only=True)
    usuario_cpf = serializers.CharField(source='usuario.cpf', read_only=True)

    class Meta:
        model = Cliente
        fields = ['id', 'usuario', 'usuario_nome', 'usuario_cpf', 'clinica', 'telefone', 'cep', 'numero_endereco', 'status_cadastro']

class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = '__all__'

class AgendamentoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.usuario.nome_completo', read_only=True)
    profissional_nome = serializers.CharField(source='profissional.usuario.nome_completo', read_only=True)
    servico_nome = serializers.CharField(source='servico.nome', read_only=True)

    class Meta:
        model = Agendamento
        fields = '__all__'

class PacoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pacote
        fields = '__all__'

class SessaoPacoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessaoPacote
        fields = '__all__'