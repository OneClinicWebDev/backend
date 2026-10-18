from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

class CadastroClinicaSerializer(serializers.Serializer):
    cpf = serializers.CharField(max_length=11)
    nome_completo = serializers.CharField(max_length=150)
    data_nascimento = serializers.DateField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    cnpj = serializers.CharField(max_length=14)
    razao_social = serializers.CharField(max_length=150)
    nome_fantasia = serializers.CharField(max_length=100)
    profissionais_podem_editar_agenda = serializers.BooleanField(default=False)