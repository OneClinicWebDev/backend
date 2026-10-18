from rest_framework import status, viewsets
from rest_framework.response import Response
from django.db import transaction

from core.models import Cliente, Auditoria
from .base import ClinicaContextMixin
from .permissions import IsAdminOrSecretario
from .serializers_core import ClienteSerializer


class ClienteViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_queryset(self):
        return Cliente.objects.filter(
            clinica=self.get_clinica()
        ).select_related(
            "usuario",
            "clinica",
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Regra 4.4: Desativação exclusiva do vínculo local. 
        Não altera o Usuario global nem apaga histórico físico.
        """
        cliente = self.get_object()

        if cliente.status_cadastro == Cliente.INATIVO:
            return Response(
                {"detail": "O cliente já está inativo."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        cliente.status_cadastro = Cliente.INATIVO
        cliente.save(
            update_fields=[
                "status_cadastro",
                "updated_at",
            ]
        )

        # Auditoria da Desativação
        Auditoria.objects.create(
            usuario=request.user,
            clinica=cliente.clinica,
            acao=Auditoria.DEACTIVATE,
            entidade="Cliente",
            objeto_id=str(cliente.id),
            origem="USUARIO",
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response(status=status.HTTP_204_NO_CONTENT)