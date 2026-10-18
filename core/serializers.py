from rest_framework import serializers
from .models import Usuario, Clinica, Cliente, Colaborador, Servico, Agendamento

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'cpf', 'nome_completo', 'telefone']

class ClinicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinica
        fields = '__all__'

class ClienteSerializer(serializers.ModelSerializer):
    # Vamos aninhar o usuário para devolver o nome e CPF junto com o cliente
    usuario = UsuarioSerializer(read_only=True)
    
    class Meta:
        model = Cliente
        fields = '__all__'
        # O campo clinica será preenchido automaticamente pela View, não pelo usuário
        read_only_fields = ['clinica', 'status_cadastro'] 

class ColaboradorSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    
    class Meta:
        model = Colaborador
        fields = '__all__'
        read_only_fields = ['clinica']

class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = '__all__'
        read_only_fields = ['clinica']

class AgendamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agendamento
        fields = '__all__'
        read_only_fields = ['clinica']