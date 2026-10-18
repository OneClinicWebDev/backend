from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone

from core.models import Colaborador, Role, Agendamento, Auditoria
from .base import ClinicaContextMixin
from .permissions import IsAdmin
from .serializers_core import ColaboradorSerializer


class ColaboradorViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ColaboradorSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return Colaborador.objects.filter(
            clinica=self.get_clinica()
        ).select_related(
            "usuario",
            "clinica",
            "role",
        )

    def _validar_desativacao_profissional(self, colaborador):
        """Impede a desativação se houver agendamentos futuros (Regra 11.4)."""
        if colaborador.role.nome == Role.PROFISSIONAL:
            agendamentos_futuros = Agendamento.objects.filter(
                profissional=colaborador,
                status__in=[Agendamento.PENDENTE, Agendamento.CONFIRMADO],
                data_hora_inicio__gt=timezone.now()
            ).exists()

            if agendamentos_futuros:
                raise ValidationError(
                    "O profissional possui agendamentos futuros. "
                    "Reatribua ou cancele os compromissos afetados antes de desativá-lo."
                )

    @transaction.atomic
    def perform_update(self, serializer):
        colaborador = self.get_object()
        dados = serializer.validated_data

        # Proteções do Administrador
        if colaborador.role.nome == Role.ADMIN:
            if dados.get("ativo") is False and colaborador.usuario_id == self.request.user.id:
                admins_ativos = Colaborador.objects.filter(
                    clinica=colaborador.clinica, role__nome=Role.ADMIN, ativo=True
                ).exclude(pk=colaborador.pk).exists()
                if not admins_ativos:
                    raise PermissionDenied("Não é possível remover o último administrador ativo da clínica.")

            if dados.get("role") and dados["role"].nome != Role.ADMIN and colaborador.usuario_id != self.request.user.id:
                raise PermissionDenied("Um administrador não pode alterar a função de outro administrador.")

            if dados.get("ativo") is False and colaborador.usuario_id != self.request.user.id:
                raise PermissionDenied("Um administrador não pode desativar outro administrador.")

        # Proteção do Profissional (Verifica na edição via PATCH/PUT)
        if dados.get("ativo") is False and colaborador.ativo:
            self._validar_desativacao_profissional(colaborador)

        serializer.save()

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        colaborador = self.get_object()

        # Proteções do Administrador no Delete lógico
        if colaborador.role.nome == Role.ADMIN:
            if colaborador.usuario_id != request.user.id:
                raise PermissionDenied("Um administrador não pode remover outro administrador.")

            admins_ativos = Colaborador.objects.filter(
                clinica=colaborador.clinica, role__nome=Role.ADMIN, ativo=True
            ).exclude(pk=colaborador.pk).exists()

            if not admins_ativos:
                raise PermissionDenied("Não é possível remover o último administrador ativo da clínica.")

        # Validação de Profissional
        self._validar_desativacao_profissional(colaborador)

        # Desativação Lógica e Salvar
        colaborador.ativo = False
        colaborador.save(update_fields=["ativo", "updated_at"])

        # Auditoria (Regra 12)
        Auditoria.objects.create(
            usuario=request.user,
            clinica=colaborador.clinica,
            acao=Auditoria.DEACTIVATE,
            entidade="Colaborador",
            objeto_id=str(colaborador.id),
            origem="USUARIO",
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response(status=status.HTTP_204_NO_CONTENT)