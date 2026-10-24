from datetime import date
from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from core.models import Colaborador, Role, Agendamento, Auditoria, Usuario
from .base import ClinicaContextMixin
from .permissions import IsAdmin, IsAdminOrSecretario
from .serializers_core import ColaboradorSerializer


class ColaboradorViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ColaboradorSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [IsAdminOrSecretario()]
        return [IsAdmin()]

    def get_queryset(self):
        return (
            Colaborador.objects.filter(clinica=self.get_clinica())
            .select_related("usuario", "clinica", "role")
            .prefetch_related("especialidades")
        )
    def _snapshot(self, colaborador):
        return {
            "usuario_id": str(colaborador.usuario_id),
            "role": colaborador.role.nome,
            "ativo": colaborador.ativo,
            "pode_editar_agenda": colaborador.pode_editar_agenda,
        }

    def _registrar_auditoria(
        self,
        colaborador,
        acao,
        dados_anteriores=None,
        dados_novos=None,
    ):
        ip = self.request.META.get("REMOTE_ADDR")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        Auditoria.objects.create(
            usuario=self.request.user,
            clinica=colaborador.clinica,
            acao=acao,
            entidade="Colaborador",
            objeto_id=str(colaborador.id),
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            origem="USUARIO",
            ip=ip or None,
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def _validar_desativacao_profissional(self, colaborador):
        if colaborador.role.nome != Role.PROFISSIONAL:
            return

        possui_agendamentos_futuros = Agendamento.objects.filter(
            clinica=colaborador.clinica,
            profissional=colaborador,
            status__in=[
                Agendamento.PENDENTE,
                Agendamento.CONFIRMADO,
            ],
            data_hora_inicio__gt=timezone.now(),
        ).exists()

        if possui_agendamentos_futuros:
            raise ValidationError(
                "O profissional possui agendamentos futuros. "
                "Reatribua ou cancele os compromissos afetados antes "
                "de desativá-lo ou alterar sua função."
            )

    def _validar_regras_administrador(
        self,
        colaborador,
        novo_role,
        novo_ativo,
    ):
        if colaborador.role.nome != Role.ADMIN:
            return

        alterando_funcao = novo_role.nome != Role.ADMIN
        desativando = not novo_ativo

        if not alterando_funcao and not desativando:
            return

        eh_proprio_vinculo = (
            colaborador.usuario_id == self.request.user.id
        )

        if not eh_proprio_vinculo:
            raise PermissionDenied(
                "Um administrador não pode desativar ou alterar "
                "a função de outro administrador."
            )

        existe_outro_admin_ativo = Colaborador.objects.filter(
            clinica=colaborador.clinica,
            role__nome=Role.ADMIN,
            ativo=True,
        ).exclude(pk=colaborador.pk).exists()

        if not existe_outro_admin_ativo:
            raise PermissionDenied(
                "Não é possível remover ou rebaixar o último "
                "administrador ativo da clínica."
            )

    @transaction.atomic
    def perform_create(self, serializer):
        clinica = self.get_clinica()
        cpf = serializer.validated_data.pop("cpf", None)
        nome = serializer.validated_data.pop("nome_completo", "")

        if not cpf:
            raise ValidationError({"cpf": "O CPF é obrigatório para cadastrar o colaborador."})

        try:
            usuario = Usuario.objects.get(cpf=cpf)
        except Usuario.DoesNotExist:
            from datetime import date
            usuario = Usuario.objects.create_user(
                cpf=cpf, 
                nome_completo=nome, 
                data_nascimento=date(1900, 1, 1),
                password=None
            )

        try:
            with transaction.atomic():
                colaborador = serializer.save(clinica=clinica, usuario=usuario)
        except IntegrityError:
            raise ValidationError({
                "usuario": (
                    "Este usuário já possui vínculo de colaborador "
                    "nesta clínica."
                )
            })

        self._registrar_auditoria(
            colaborador,
            Auditoria.CREATE,
            dados_novos=self._snapshot(colaborador),
        )

    @transaction.atomic
    def perform_update(self, serializer):
        colaborador = self.get_object()
        dados = serializer.validated_data

        if "usuario" in dados:
            raise ValidationError({
                "usuario": "Não é permitido trocar o usuário de um vínculo existente."
            })

        if colaborador.clinica_id != self.get_clinica().pk:
            raise PermissionDenied(
                "O colaborador não pertence à clínica ativa."
            )

        novo_role = dados.get("role", colaborador.role)
        novo_ativo = dados.get("ativo", colaborador.ativo)

        self._validar_regras_administrador(
            colaborador,
            novo_role,
            novo_ativo,
        )

        esta_deixando_de_ser_profissional = (
            colaborador.role.nome == Role.PROFISSIONAL
            and novo_role.nome != Role.PROFISSIONAL
        )
        esta_sendo_desativado = colaborador.ativo and not novo_ativo

        if esta_deixando_de_ser_profissional or esta_sendo_desativado:
            self._validar_desativacao_profissional(colaborador)

        anteriores = self._snapshot(colaborador)

        colaborador = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            colaborador,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(colaborador),
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        colaborador = self.get_object()

        if not colaborador.ativo:
            return Response(
                {"detail": "O colaborador já está inativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if colaborador.clinica_id != self.get_clinica().pk:
            raise PermissionDenied(
                "O colaborador não pertence à clínica ativa."
            )

        if colaborador.role.nome == Role.ADMIN:
            if colaborador.usuario_id != request.user.id:
                raise PermissionDenied(
                    "Um administrador não pode remover outro administrador."
                )

            existe_outro_admin_ativo = Colaborador.objects.filter(
                clinica=colaborador.clinica,
                role__nome=Role.ADMIN,
                ativo=True,
            ).exclude(pk=colaborador.pk).exists()

            if not existe_outro_admin_ativo:
                raise PermissionDenied(
                    "Não é possível remover o último administrador ativo "
                    "da clínica."
                )

        self._validar_desativacao_profissional(colaborador)

        anteriores = self._snapshot(colaborador)

        colaborador.ativo = False
        colaborador.save(update_fields=["ativo", "updated_at"])

        self._registrar_auditoria(
            colaborador,
            Auditoria.DEACTIVATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(colaborador),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)