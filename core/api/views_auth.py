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

        colab = Colaborador.objects.filter(usuario=user).select_related("clinica", "role").first()

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "usuario": {
                "id": str(user.id),
                "cpf": user.cpf,
                "nome": user.nome_completo
            },
            "clinica": str(colab.clinica.id) if colab else None,
            "role": colab.role.nome if colab else None
        })