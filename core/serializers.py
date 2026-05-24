from rest_framework import serializers

from .models import (
    Usuario,
    Cliente,
    Colaborador,
    Clinica,
    Role
)


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            'id',
            'cpf',
            'nome_completo'
        ]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'


class ClinicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinica
        fields = '__all__'


class ClienteSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)

    class Meta:
        model = Cliente
        fields = '__all__'


class ColaboradorSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    role = RoleSerializer(read_only=True)

    class Meta:
        model = Colaborador
        fields = '__all__'