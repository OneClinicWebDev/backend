from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import Colaborador
from .serializers_auth import LoginSerializer


class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        vinculos = Colaborador.objects.filter(
            usuario=user, 
            ativo=True
        ).select_related("clinica", "role")

        clinicas_disponiveis = [
            {
                "clinica_id": str(v.clinica.id),
                "clinica_nome": v.clinica.nome_fantasia,
                "role": v.role.nome,
                "pode_editar_agenda": v.pode_editar_agenda
            } for v in vinculos
        ]

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "usuario": {
                "id": str(user.id),
                "cpf": user.cpf,
                "nome": user.nome_completo
            },
            "vinculos": clinicas_disponiveis
        })