from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.models import (
    Colaborador,
    Cliente
)


class LoginView(APIView):
    def post(self, request):
        cpf = request.data.get('cpf')
        password = request.data.get('password')

        if not cpf or not password:
            return Response(
                {'error': 'CPF e senha obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(
            request,
            cpf=cpf,
            password=password
        )

        if not user:
            return Response(
                {'error': 'Credenciais inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        colaboradores = Colaborador.objects.filter(
            usuario=user,
            ativo=True
        ).select_related(
            'clinica',
            'role'
        )

        clientes = Cliente.objects.filter(
            usuario=user
        ).select_related(
            'clinica'
        )

        return Response({
            'user': {
                'id': str(user.id),
                'cpf': user.cpf,
                'nome_completo': user.nome_completo,
            },

            'colaboradores': [
                {
                    'colaborador_id': str(c.id),
                    'clinica_id': str(c.clinica.id),
                    'clinica_nome': c.clinica.nome_fantasia,
                    'role': c.role.nome,
                    'especialidade': c.especialidade,
                }
                for c in colaboradores
            ],

            'clientes': [
                {
                    'cliente_id': str(c.id),
                    'clinica_id': str(c.clinica.id),
                    'clinica_nome': c.clinica.nome_fantasia,
                }
                for c in clientes
            ]
        })