from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import authenticate
from rest_framework import serializers

from core.validators import validar_cpf


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