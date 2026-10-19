
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Usuario,
    Clinica,
    Colaborador,
    Role,
    Auditoria,
)
from .serializers_cadastro import CadastroClinicaSerializer


class CadastroClinicaView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        serializer = CadastroClinicaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        usuario = (
            Usuario.objects.select_for_update()
            .filter(cpf=data["cpf"])
            .first()
        )

        if usuario:
            if not usuario.check_password(data["password"]):
                return Response(
                    {
                        "detail": (
                            "Não foi possível validar as credenciais "
                            "informadas."
                        )
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        else:
            usuario = Usuario.objects.create_user(
                cpf=data["cpf"],
                password=data["password"],
                nome_completo=data["nome_completo"],
                data_nascimento=data["data_nascimento"],
            )

        role_admin = Role.objects.get(nome=Role.ADMIN)

        clinica = Clinica.objects.create(
            cnpj=data["cnpj"],
            razao_social=data["razao_social"],
            nome_fantasia=data["nome_fantasia"],
            telefone=data["telefone"],
            profissionais_podem_editar_agenda=data[
                "profissionais_podem_editar_agenda"
            ],
        )

        Colaborador.objects.create(
            usuario=usuario,
            clinica=clinica,
            role=role_admin,
            ativo=True,
            pode_editar_agenda=True,
        )

        Auditoria.objects.create(
            usuario=usuario,
            clinica=clinica,
            acao="CREATE",
            entidade="Clinica",
            objeto_id=str(clinica.id),
            dados_novos={
                "cnpj": clinica.cnpj,
                "razao_social": clinica.razao_social,
                "nome_fantasia": clinica.nome_fantasia,
                "telefone": clinica.telefone,
                "profissionais_podem_editar_agenda": (
                    clinica.profissionais_podem_editar_agenda
                ),
                "administrador_inicial_id": str(usuario.id),
            },
            origem="USUARIO",
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return Response(
            {
                "detail": "Clínica criada com sucesso.",
                "clinica_id": str(clinica.id),
                "usuario_id": str(usuario.id),
            },
            status=status.HTTP_201_CREATED,
        )
