from rest_framework import serializers
from .models import Cliente, Colaborador, Servico, Agendamento, Usuario, Clinica
from .validators import validar_cpf, validar_cnpj

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'cpf', 'nome_completo', 'telefone']

class ClinicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinica
        fields = '__all__'

class ClienteSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    
    class Meta:
        model = Cliente
        fields = '__all__'
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

class UsuarioSerializer(serializers.ModelSerializer):
    cpf = serializers.CharField()

    def validate_cpf(self, value):
        return validar_cpf(value)

    class Meta:
        model = Usuario
        fields = ['id', 'cpf', 'nome_completo', 'data_nascimento', 'telefone', 'email', 'is_active']

class ClinicaSerializer(serializers.ModelSerializer):
    cnpj = serializers.CharField()

    def validate_cnpj(self, value):
        return validar_cnpj(value)

    class Meta:
        model = Clinica
        fields = '__all__'

class ClienteSerializer(serializers.ModelSerializer):
    cpf = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_cpf(self, value):
        if value:
            return validar_cpf(value)
        return value

    class Meta:
        model = Cliente
        fields = '__all__'
        read_only_fields = ['clinica']

class ColaboradorSerializer(serializers.ModelSerializer):
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