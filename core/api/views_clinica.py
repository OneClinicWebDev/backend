from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction

from core.models import Clinica, Auditoria
from .base import ClinicaContextMixin
from .permissions import IsAdmin
from .serializers_core import (
    ClinicaAtualizacaoSerializer,
    ClinicaSerializer,
)

class ClinicaViewSet(ClinicaContextMixin, viewsets.GenericViewSet):
    serializer_class = ClinicaSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return Clinica.objects.filter(id=self.get_clinica().id)

    @action(detail=False, methods=['get', 'patch'])
    @transaction.atomic
    def atual(self, request):
        clinica = self.get_clinica()

        if request.method == 'GET':
            return Response(
                ClinicaAtualizacaoSerializer(clinica).data,
                status=status.HTTP_200_OK,
            )

        anteriores = ClinicaAtualizacaoSerializer(clinica).data

        serializer = ClinicaAtualizacaoSerializer(
            clinica,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        Auditoria.objects.create(
            usuario=request.user,
            clinica=clinica,
            acao=Auditoria.UPDATE,
            entidade="Clinica",
            objeto_id=str(clinica.id),
            dados_anteriores=dict(anteriores),
            dados_novos=dict(serializer.data),
            origem="USUARIO",
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    @transaction.atomic
    def autonomia_agenda(self, request):
        clinica = self.get_clinica()
        
        if 'profissionais_podem_editar_agenda' not in request.data:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        valor_anterior = clinica.profissionais_podem_editar_agenda
        novo_valor = str(request.data['profissionais_podem_editar_agenda']).lower() in ['true', '1', 't']

        if valor_anterior != novo_valor:
            clinica.profissionais_podem_editar_agenda = novo_valor
            clinica.save(update_fields=['profissionais_podem_editar_agenda', 'updated_at'])

            Auditoria.objects.create(
                usuario=request.user,
                clinica=clinica,
                acao=Auditoria.UPDATE,
                entidade="Clinica",
                objeto_id=str(clinica.id),
                dados_anteriores={"profissionais_podem_editar_agenda": valor_anterior},
                dados_novos={"profissionais_podem_editar_agenda": novo_valor},
                origem="USUARIO",
                ip=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

        return Response(self.get_serializer(clinica).data, status=status.HTTP_200_OK)