from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Colaborador, Cliente


class LoginView(APIView):
    def post(self, request):
        cpf = request.data.get('cpf')
        password = request.data.get('password')

        user = authenticate(request, cpf=cpf, password=password)

        if not user:
            return Response({'error': 'Credenciais inválidas'}, status=400)

        colaboradores = Colaborador.objects.filter(usuario=user)
        clientes = Cliente.objects.filter(cpf=cpf)

        return Response({
            'user_id': str(user.id),
            'colaboradores': [
                {
                    'clinica_id': str(c.clinica.id),
                    'role': c.role
                } for c in colaboradores
            ],
            'clientes': [
                {
                    'clinica_id': str(c.clinica.id)
                } for c in clientes
            ]
        })