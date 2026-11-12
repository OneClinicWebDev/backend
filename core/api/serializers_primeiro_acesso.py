from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.servicos_primeiro_acesso import CODIGO_TAMANHO, normalizar_codigo
from core.validators import validar_cpf

from .serializers_core import ColaboradorSerializer


class ColaboradorComPrimeiroAcessoSerializer(ColaboradorSerializer):
    primeiro_acesso_pendente = serializers.SerializerMethodField()

    class Meta(ColaboradorSerializer.Meta):
        fields = ColaboradorSerializer.Meta.fields + ["primeiro_acesso_pendente"]

    def get_primeiro_acesso_pendente(self, obj):
        return not obj.usuario.has_usable_password()


class PrimeiroAcessoSerializer(serializers.Serializer):
    cpf = serializers.CharField(max_length=14, trim_whitespace=True)
    codigo = serializers.CharField(max_length=32, trim_whitespace=True)
    nova_senha = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    confirmar_senha = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate_cpf(self, value):
        try:
            return validar_cpf(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_codigo(self, value):
        codigo = normalizar_codigo(value)

        if len(codigo) != CODIGO_TAMANHO:
            raise serializers.ValidationError(
                "Informe o código de primeiro acesso completo."
            )

        return codigo

    def validate(self, attrs):
        if attrs["nova_senha"] != attrs["confirmar_senha"]:
            raise serializers.ValidationError({
                "confirmar_senha": "A confirmação da senha não confere."
            })

        try:
            validate_password(attrs["nova_senha"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "nova_senha": list(exc.messages)
            }) from exc

        return attrs