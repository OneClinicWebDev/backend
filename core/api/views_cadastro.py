from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from core.models import Usuario, Clinica, Colaborador, Role, Auditoria
from .serializers_cadastro import CadastroClinicaSerializer

class CadastroClinicaView(APIView):
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        serializer = CadastroClinicaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        usuario = Usuario.objects.filter(cpf=data['cpf']).first()
        
        if not usuario:
            usuario = Usuario.objects.create_user(
                cpf=data['cpf'],
                password=data['password'],
                nome_completo=data['nome_completo'],
                data_nascimento=data['data_nascimento']
            )
        else:
            if not usuario.check_password(data['password']):
                return Response(
                    {"detail": "CPF já cadastrado. Senha incorreta para vincular nova clínica."}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )

        clinica = Clinica.objects.create(
            cnpj=data['cnpj'],
            razao_social=data['razao_social'],
            nome_fantasia=data['nome_fantasia'],
            profissionais_podem_editar_agenda=data.get('profissionais_podem_editar_agenda', False)
        )

        role_admin = Role.objects.get(nome=Role.ADMIN)
        
        Colaborador.objects.create(
            usuario=usuario,
            clinica=clinica,
            role=role_admin,
            pode_editar_agenda=True
        )

        Auditoria.objects.create(
            usuario=usuario,
            clinica=clinica,
            acao=Auditoria.CREATE,
            entidade="Clinica",
            objeto_id=str(clinica.id),
            dados_novos={
                "cnpj": clinica.cnpj, 
                "profissionais_podem_editar_agenda": clinica.profissionais_podem_editar_agenda
            },
            origem="USUARIO",
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response({
            "detail": "Clínica criada com sucesso.",
            "clinica_id": clinica.id,
            "usuario_id": usuario.id
        }, status=status.HTTP_201_CREATED)