import uuid

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from django.db import transaction
from core.models import Auditoria, Colaborador
from .serializers_auth import (
    AlterarSenhaSerializer,
    LoginSerializer,
    PerfilSerializer,
)

def _dados_usuario(user):
    return {
        "id": str(user.id),
        "cpf": user.cpf,
        "nome": user.nome_completo,
        "data_nascimento": (
            user.data_nascimento.isoformat() if user.data_nascimento else ""
        ),
        "telefone": user.telefone,
    }


def _vinculos_do_usuario(user):
    """
    Clínicas que o usuário pode selecionar: vínculos de colaborador ativos
    em clínicas ativas (as mesmas condições exigidas por HasClinicaContext).
    """
    vinculos = (
        Colaborador.objects.filter(
            usuario=user,
            ativo=True,
            clinica__ativo=True,
        )
        .select_related("clinica", "role")
        .order_by("clinica__nome_fantasia", "clinica_id")
    )

    return [
        {
            "clinica_id": str(v.clinica.id),
            "clinica_nome": v.clinica.nome_fantasia,
            "role": v.role.nome,
            "colaborador_id": str(v.id),
            "pode_editar_agenda": v.pode_editar_agenda,
            "profissionais_podem_editar_agenda": (
                v.clinica.profissionais_podem_editar_agenda
            ),
        }
        for v in vinculos
    ]


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "usuario": _dados_usuario(user),
            "vinculos": _vinculos_do_usuario(user),
        })


class MeView(APIView):
    """
    Devolve o usuário autenticado e suas clínicas selecionáveis, para o
    frontend restaurar a sessão sem novo login. Não exige X-Clinica-ID.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "usuario": _dados_usuario(request.user),
            "vinculos": _vinculos_do_usuario(request.user),
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.exceptions import TokenError

        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "O refresh token é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)

            if str(token["user_id"]) != str(request.user.pk):
                return Response(
                    {"detail": "Token inválido para este usuário."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token.blacklist()

        except (TokenError, KeyError, TypeError, ValueError):
            return Response(
                {"detail": "Refresh token inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_205_RESET_CONTENT)


class PerfilView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PerfilSerializer(request.user).data)

    @transaction.atomic
    def patch(self, request):
        user = request.user
        anteriores = PerfilSerializer(user).data

        serializer = PerfilSerializer(
            user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        vinculo = None

        try:
            clinica_id = uuid.UUID(request.headers.get("X-Clinica-ID", ""))
        except (ValueError, AttributeError, TypeError):
            clinica_id = None

        if clinica_id is not None:
            vinculo = (
                Colaborador.objects.select_related("clinica")
                .filter(usuario=user, clinica_id=clinica_id, ativo=True)
                .first()
            )

        if vinculo is not None:
            Auditoria.objects.create(
                usuario=user,
                clinica=vinculo.clinica,
                acao=Auditoria.UPDATE,
                entidade="Usuario",
                objeto_id=str(user.id),
                dados_anteriores=dict(anteriores),
                dados_novos=dict(serializer.data),
                origem="USUARIO",
                ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

        return Response(serializer.data)


class AlterarSenhaView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = AlterarSenhaSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["nova_senha"])
        user.save(update_fields=["password", "updated_at"])

        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)

        refresh = RefreshToken.for_user(user)

        return Response({
            "detail": "Senha alterada com sucesso.",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })