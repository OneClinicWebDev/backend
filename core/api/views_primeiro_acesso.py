from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from core.servicos_primeiro_acesso import concluir_primeiro_acesso

from .serializers_primeiro_acesso import PrimeiroAcessoSerializer

MENSAGEM_CODIGO_INVALIDO = "CPF ou código inválido, expirado ou já utilizado."


class PrimeiroAcessoThrottle(AnonRateThrottle):
    rate = "10/min"


class PrimeiroAcessoView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PrimeiroAcessoThrottle]

    def post(self, request):
        serializer = PrimeiroAcessoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            concluido = concluir_primeiro_acesso(
                cpf=data["cpf"],
                codigo=data["codigo"],
                nova_senha=data["nova_senha"],
                ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except DjangoValidationError as exc:
            raise ValidationError({"nova_senha": list(exc.messages)}) from exc

        if not concluido:
            return Response(
                {"detail": MENSAGEM_CODIGO_INVALIDO},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": (
                    "Senha definida com sucesso. Você já pode entrar "
                    "com seu CPF e sua nova senha."
                )
            },
            status=status.HTTP_200_OK,
        )