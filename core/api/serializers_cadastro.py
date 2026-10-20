from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.models import Clinica
from core.validators import (
    validar_cpf,
    validar_cnpj,
    validar_telefone,
)


class CadastroClinicaSerializer(serializers.Serializer):
    cpf = serializers.CharField(max_length=14, trim_whitespace=True)
    nome_completo = serializers.CharField(max_length=255)
    data_nascimento = serializers.DateField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        validators=[validate_password],
    )
    cnpj = serializers.CharField(max_length=18, trim_whitespace=True)
    razao_social = serializers.CharField(max_length=255)
    nome_fantasia = serializers.CharField(max_length=255)
    telefone = serializers.CharField(max_length=20, trim_whitespace=True)
    profissionais_podem_editar_agenda = serializers.BooleanField(
        default=False
    )

    def validate_cpf(self, value):
        try:
            return validar_cpf(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_cnpj(self, value):
        try:
            cnpj = validar_cnpj(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

        if Clinica.objects.filter(cnpj=cnpj).exists():
            raise serializers.ValidationError(
                "Já existe uma clínica cadastrada com este CNPJ."
            )

        return cnpj

    def validate_telefone(self, value):
        try:
            return validar_telefone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_nome_completo(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "O nome completo é obrigatório."
            )

        return value

    def validate_razao_social(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A razão social é obrigatória."
            )

        return value

    def validate_nome_fantasia(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "O nome fantasia é obrigatório."
            )

        return value

    def validate_data_nascimento(self, value):
        if value >= date.today():
            raise serializers.ValidationError(
                "A data de nascimento deve ser anterior à data atual."
            )

        return value
