from django.db import IntegrityError, transaction

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    APIException,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response

from core.models import (
    Agendamento,
    Cliente,
    Colaborador,
    Role,
    SessaoPacote,
    HistoricoSessao,
    Auditoria,
)
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
        return (
            Agendamento.objects.filter(clinica=self.get_clinica())
            .select_related(
                "cliente__usuario",
                "profissional__usuario",
                "profissional__role",
                "servico",
                "pacote_origem",
            )
        )

    def _colaborador_logado(self):
        try:
            return Colaborador.objects.select_related("role").get(
                usuario=self.request.user,
                clinica=self.get_clinica(),
                ativo=True,
            )
        except Colaborador.DoesNotExist:
            raise PermissionDenied(
                "Não existe vínculo ativo com a clínica selecionada."
            )

    def _validar_autonomia_agenda(self, clinica, profissional_id):
        colaborador = self._colaborador_logado()

        if colaborador.role.nome in (Role.ADMIN, Role.SECRETARIO):
            return

        if colaborador.role.nome != Role.PROFISSIONAL:
            raise PermissionDenied("Você não pode gerenciar a agenda.")

        if str(colaborador.id) != str(profissional_id):
            raise PermissionDenied(
                "O profissional só pode editar a própria agenda."
            )

        if not clinica.profissionais_podem_editar_agenda:
            raise PermissionDenied(
                "A clínica não permite autonomia de edição da agenda."
            )

        if not colaborador.pode_editar_agenda:
            raise PermissionDenied(
                "Você não possui permissão individual para editar a agenda."
            )

    def _validar_cliente_ativo(self, cliente, clinica):
        if cliente.clinica_id != clinica.pk:
            raise ValidationError({
                "cliente": "O cliente não pertence à clínica ativa."
            })

        if cliente.status_cadastro != Cliente.ATIVO:
            raise ValidationError({
                "cliente": "Não é possível agendar para um cliente inativo."
            })

    def _validar_conflitos(
        self,
        clinica,
        profissional_id,
        cliente_id,
        inicio,
        fim,
        agendamento_id=None,
    ):
        if inicio >= fim:
            raise ValidationError({
                "data_hora_fim": "O horário final deve ser posterior ao inicial."
            })

        conflitos = Agendamento.objects.filter(
            clinica=clinica,
            status__in=[
                Agendamento.PENDENTE,
                Agendamento.CONFIRMADO,
            ],
            data_hora_inicio__lt=fim,
            data_hora_fim__gt=inicio,
        )

        if agendamento_id:
            conflitos = conflitos.exclude(id=agendamento_id)

        if (
            conflitos.filter(profissional_id=profissional_id).exists()
            or conflitos.filter(cliente_id=cliente_id).exists()
        ):
            raise ConflictException(
                "Existe um agendamento PENDENTE ou CONFIRMADO "
                "no mesmo intervalo. Resolva o conflito explicitamente."
            )

    def _registrar_auditoria(
        self,
        agendamento,
        acao,
        dados_anteriores=None,
        dados_novos=None,
    ):
        request = self.request
        ip = request.META.get("REMOTE_ADDR")

        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        Auditoria.objects.create(
            usuario=(
                request.user
                if getattr(request.user, "is_authenticated", False)
                else None
            ),
            clinica=agendamento.clinica,
            acao=acao,
            entidade="Agendamento",
            objeto_id=str(agendamento.id),
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            origem="USUARIO",
            ip=ip or None,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

    @transaction.atomic
    def perform_create(self, serializer):
        clinica = self.get_clinica()
        profissional = serializer.validated_data["profissional"]
        cliente = serializer.validated_data["cliente"]
        inicio = serializer.validated_data["data_hora_inicio"]
        fim = serializer.validated_data["data_hora_fim"]

        self._validar_cliente_ativo(cliente, clinica)

        self._validar_autonomia_agenda(
            clinica,
            profissional.id,
        )

        self._validar_conflitos(
            clinica,
            profissional.id,
            cliente.id,
            inicio,
            fim,
        )

        try:
            agendamento = serializer.save(
                clinica=clinica,
                status=Agendamento.CONFIRMADO,
                resultado=Agendamento.AGUARDANDO_RESULTADO,
            )
        except IntegrityError:
            raise ConflictException(
                "O horário acabou de ser ocupado por outro agendamento. "
                "Atualize a agenda e tente novamente."
            )

        self._registrar_auditoria(
            agendamento,
            Auditoria.CREATE,
            dados_novos={
                "status": agendamento.status,
                "resultado": agendamento.resultado,
                "cliente_id": str(agendamento.cliente_id),
                "profissional_id": str(agendamento.profissional_id),
                "servico_id": str(agendamento.servico_id),
                "pacote_origem_id": (
                    str(agendamento.pacote_origem_id)
                    if agendamento.pacote_origem_id
                    else None
                ),
                "inicio": agendamento.data_hora_inicio.isoformat(),
                "fim": agendamento.data_hora_fim.isoformat(),
            },
        )

    @transaction.atomic
    def perform_update(self, serializer):
        clinica = self.get_clinica()
        agendamento = self.get_object()

        if agendamento.status in (
            Agendamento.CANCELADO,
            Agendamento.CONCLUIDO,
        ):
            raise ValidationError(
                "Agendamentos cancelados ou concluídos não podem ser editados."
            )

        profissional = serializer.validated_data.get(
            "profissional",
            agendamento.profissional,
        )
        cliente = serializer.validated_data.get(
            "cliente",
            agendamento.cliente,
        )
        inicio = serializer.validated_data.get(
            "data_hora_inicio",
            agendamento.data_hora_inicio,
        )
        fim = serializer.validated_data.get(
            "data_hora_fim",
            agendamento.data_hora_fim,
        )

        self._validar_cliente_ativo(cliente, clinica)

        self._validar_autonomia_agenda(
            clinica,
            profissional.id,
        )

        self._validar_conflitos(
            clinica,
            profissional.id,
            cliente.id,
            inicio,
            fim,
            agendamento_id=agendamento.id,
        )

        anteriores = {
            "status": agendamento.status,
            "resultado": agendamento.resultado,
            "cliente_id": str(agendamento.cliente_id),
            "profissional_id": str(agendamento.profissional_id),
            "servico_id": str(agendamento.servico_id),
            "pacote_origem_id": (
                str(agendamento.pacote_origem_id)
                if agendamento.pacote_origem_id
                else None
            ),
            "inicio": agendamento.data_hora_inicio.isoformat(),
            "fim": agendamento.data_hora_fim.isoformat(),
        }

        try:
            agendamento = serializer.save()
        except IntegrityError:
            raise ConflictException(
                "O horário acabou de ser ocupado por outro agendamento."
            )

        self._registrar_auditoria(
            agendamento,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos={
                "status": agendamento.status,
                "resultado": agendamento.resultado,
                "cliente_id": str(agendamento.cliente_id),
                "profissional_id": str(agendamento.profissional_id),
                "servico_id": str(agendamento.servico_id),
                "pacote_origem_id": (
                    str(agendamento.pacote_origem_id)
                    if agendamento.pacote_origem_id
                    else None
                ),
                "inicio": agendamento.data_hora_inicio.isoformat(),
                "fim": agendamento.data_hora_fim.isoformat(),
            },
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def registrar_falta(self, request, pk=None):
        agendamento = self.get_queryset().select_for_update().get(pk=pk)
        colaborador = self._colaborador_logado()

        if colaborador.role.nome not in (Role.ADMIN, Role.SECRETARIO):
            raise PermissionDenied(
                "Somente ADMIN ou SECRETARIO pode registrar a falta."
            )

        if agendamento.status not in (
            Agendamento.PENDENTE,
            Agendamento.CONFIRMADO,
        ):
            raise ValidationError(
                "A falta só pode ser registrada em um agendamento pendente "
                "ou confirmado."
            )

        if agendamento.resultado == Agendamento.FALTA:
            raise ValidationError("A falta já foi registrada.")

        sessao = (
            SessaoPacote.objects.select_for_update()
            .filter(agendamento=agendamento)
            .first()
        )

        decisao = request.data.get("decisao_sessao")
        justificativa = request.data.get("justificativa", "")

        if not isinstance(justificativa, str):
            raise ValidationError({
                "justificativa": "A justificativa deve ser um texto."
            })

        if sessao and sessao.status == SessaoPacote.AGENDADA:
            if decisao not in ("PRESERVAR", "PERDER"):
                raise ValidationError({
                    "decisao_sessao": (
                        "Informe PRESERVAR ou PERDER para decidir "
                        "o destino da sessão do pacote."
                    )
                })

        anteriores = {
            "status": agendamento.status,
            "resultado": agendamento.resultado,
        }

        agendamento.status = Agendamento.CONCLUIDO
        agendamento.resultado = Agendamento.FALTA
        agendamento.save(update_fields=[
            "status",
            "resultado",
            "updated_at",
        ])

        if sessao and sessao.status == SessaoPacote.AGENDADA:
            estado_anterior = sessao.status
            estado_novo = (
                SessaoPacote.DISPONIVEL
                if decisao == "PRESERVAR"
                else SessaoPacote.PERDIDA
            )

            sessao.status = estado_novo
            sessao.agendamento = None
            sessao.save(update_fields=[
                "status",
                "agendamento",
                "updated_at",
            ])

            HistoricoSessao.objects.create(
                sessao=sessao,
                estado_anterior=estado_anterior,
                estado_novo=estado_novo,
                usuario_executor=request.user,
                agendamento_relacionado=agendamento,
                motivo="Registro manual de falta",
                justificativa=justificativa,
            )

        self._registrar_auditoria(
            agendamento,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos={
                "status": agendamento.status,
                "resultado": agendamento.resultado,
                "decisao_sessao": (
                    decisao
                    if sessao and sessao.status != SessaoPacote.AGENDADA
                    else None
                ),
                "justificativa": justificativa,
            },
        )

        return Response({
            "detail": "Falta registrada.",
            "agendamento_id": str(agendamento.id),
            "resultado": agendamento.resultado,
            "decisao_sessao": decisao if sessao else None,
        })

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancelar(self, request, pk=None):
        agendamento = self.get_queryset().select_for_update().get(pk=pk)
        colaborador = self._colaborador_logado()

        if colaborador.role.nome not in (Role.ADMIN, Role.SECRETARIO):
            raise PermissionDenied(
                "Somente ADMIN ou SECRETARIO pode cancelar agendamentos."
            )

        if agendamento.status in (
            Agendamento.CANCELADO,
            Agendamento.CONCLUIDO,
        ):
            raise ValidationError(
                "Este agendamento já está encerrado."
            )

        motivo = request.data.get("motivo")

        if not isinstance(motivo, str) or not motivo.strip():
            raise ValidationError({
                "motivo": "Informe o motivo do cancelamento."
            })

        anteriores = {
            "status": agendamento.status,
            "resultado": agendamento.resultado,
            "motivo_cancelamento": agendamento.motivo_cancelamento,
        }

        agendamento.status = Agendamento.CANCELADO
        agendamento.motivo_cancelamento = motivo.strip()[:50]
        agendamento.save(update_fields=[
            "status",
            "motivo_cancelamento",
            "updated_at",
        ])

        sessao = (
            SessaoPacote.objects.select_for_update()
            .filter(agendamento=agendamento)
            .first()
        )

        if sessao and sessao.status == SessaoPacote.AGENDADA:
            estado_anterior = sessao.status

            sessao.status = SessaoPacote.DISPONIVEL
            sessao.agendamento = None
            sessao.save(update_fields=[
                "status",
                "agendamento",
                "updated_at",
            ])

            HistoricoSessao.objects.create(
                sessao=sessao,
                estado_anterior=estado_anterior,
                estado_novo=SessaoPacote.DISPONIVEL,
                usuario_executor=request.user,
                agendamento_relacionado=agendamento,
                motivo="Cancelamento de agendamento",
                justificativa=motivo.strip(),
            )

        self._registrar_auditoria(
            agendamento,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos={
                "status": agendamento.status,
                "resultado": agendamento.resultado,
                "motivo_cancelamento": agendamento.motivo_cancelamento,
            },
        )

        return Response({
            "detail": "Agendamento cancelado.",
            "agendamento_id": str(agendamento.id),
        })

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "A exclusão física não é permitida. "
                    "Utilize a ação cancelar informando o motivo."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
