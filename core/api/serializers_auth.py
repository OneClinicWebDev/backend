from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.models import Usuario
from core.validators import validar_cpf, validar_telefone_opcional


class LoginSerializer(serializers.Serializer):
    cpf = serializers.CharField(
        max_length=14,
        trim_whitespace=True,
    )
    password = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
    )

    def validate(self, data):
        try:
            cpf = validar_cpf(data["cpf"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                "Credenciais inválidas ou usuário inativo."
            ) from exc

        user = authenticate(
            username=cpf,
            password=data["password"],
        )

        if not user:
            raise serializers.ValidationError(
                "Credenciais inválidas ou usuário inativo."
            )

        data["cpf"] = cpf
        data["user"] = user

        return data


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            "id",
            "cpf",
            "nome_completo",
            "data_nascimento",
            "telefone",
        ]
        read_only_fields = ["id", "cpf"]

    def validate_nome_completo(self, value):
        value = value.strip()

        if len(value) < 3:
            raise serializers.ValidationError(
                "Informe um nome com pelo menos 3 caracteres."
            )

        return value

    def validate_data_nascimento(self, value):
        if value < date(1900, 1, 1) or value >= date.today():
            raise serializers.ValidationError(
                "Informe uma data de nascimento válida."
            )

        return value

    def validate_telefone(self, value):
        try:
            return validar_telefone_opcional(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    nova_senha = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate_senha_atual(self, value):
        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError("A senha atual está incorreta.")

        return value

    def validate(self, attrs):
        user = self.context["request"].user

        if attrs["senha_atual"] == attrs["nova_senha"]:
            raise serializers.ValidationError({
                "nova_senha": "A nova senha deve ser diferente da atual."
            })

        try:
            validate_password(attrs["nova_senha"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "nova_senha": list(exc.messages)
            }) from exc

        return attrs