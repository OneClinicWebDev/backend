from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, APIException
from django.db import transaction
from django.db.models import Q

from core.models import Agendamento, Colaborador, Role
from .base import ClinicaContextMixin
from .permissions import HasClinicaContext
from .serializers_core import AgendamentoSerializer


class ConflictException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflito de horário identificado."
    default_code = "conflict"


class AgendamentoViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = AgendamentoSerializer
    permission_classes = [HasClinicaContext]

    def get_queryset(self):
        return Agendamento.objects.filter(
            clinica=self.get_clinica()
        ).select_related("cliente__usuario", "profissional__usuario", "servico")

    def _validar_autonomia_agenda(self, clinica, profissional_id):
        # Valida a Regra Definitiva de Autonomia da Agenda (Seção 5.5)
        vinculo_logado = Colaborador.objects.get(
            usuario=self.request.user, 
            clinica=clinica, 
            ativo=True
        )

        if vinculo_logado.role.nome in [Role.ADMIN, Role.SECRETARIO]:
            return # Admin e Secretário possuem autonomia operacional por padrão

        if vinculo_logado.role.nome == Role.PROFISSIONAL:
            if str(vinculo_logado.id) != str(profissional_id):
                raise PermissionDenied("Profissional não pode editar a agenda de terceiros.")

            if not clinica.profissionais_podem_editar_agenda:
                raise PermissionDenied("A clínica não autoriza a autonomia da agenda.")
                
            if not vinculo_logado.pode_editar_agenda:
                raise PermissionDenied("Você não possui permissão individual para editar a agenda.")

    def _validar_conflitos(self, clinica, profissional_id, cliente_id, inicio, fim, agendamento_id=None):
        # Valida Regras de Sobreposição (Seção 9.3 e 9.4)
        conflitos = Agendamento.objects.filter(
            clinica=clinica,
            status__in=[Agendamento.PENDENTE, Agendamento.CONFIRMADO],
            data_hora_inicio__lt=fim,
            data_hora_fim__gt=inicio
        )
        
        if agendamento_id:
            conflitos = conflitos.exclude(id=agendamento_id)

        conflitos_profissional = conflitos.filter(profissional_id=profissional_id).exists()
        conflitos_cliente = conflitos.filter(cliente_id=cliente_id).exists()

        if conflitos_profissional or conflitos_cliente:
            raise ConflictException(
                "Conflito com agendamento PENDENTE ou CONFIRMADO no mesmo intervalo. "
                "Resolva o conflito explicitamente antes de confirmar."
            )

    @transaction.atomic
    def perform_create(self, serializer):
        clinica = self.get_clinica()
        profissional_id = serializer.validated_data.get("profissional").id
        cliente_id = serializer.validated_data.get("cliente").id
        inicio = serializer.validated_data.get("data_hora_inicio")
        fim = serializer.validated_data.get("data_hora_fim")

        self._validar_autonomia_agenda(clinica, profissional_id)
        self._validar_conflitos(clinica, profissional_id, cliente_id, inicio, fim)

        # Se não há conflito, nasce como CONFIRMADO, conforme Seção 9.2
        status_agendamento = serializer.validated_data.get("status", Agendamento.CONFIRMADO)

        serializer.save(
            clinica=clinica,
            status=status_agendamento
        )

    @transaction.atomic
    def perform_update(self, serializer):
        clinica = self.get_clinica()
        agendamento = self.get_object()
        
        profissional_id = serializer.validated_data.get("profissional", agendamento.profissional).id
        cliente_id = serializer.validated_data.get("cliente", agendamento.cliente).id
        inicio = serializer.validated_data.get("data_hora_inicio", agendamento.data_hora_inicio)
        fim = serializer.validated_data.get("data_hora_fim", agendamento.data_hora_fim)

        self._validar_autonomia_agenda(clinica, profissional_id)
        self._validar_conflitos(clinica, profissional_id, cliente_id, inicio, fim, agendamento_id=agendamento.id)

        serializer.save()