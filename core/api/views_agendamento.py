import uuid
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

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
        queryset = (
            Agendamento.objects.filter(clinica=self.get_clinica())
            .select_related(
                "cliente__usuario",
                "profissional__usuario",
                "profissional__role",
                "servico",
                "pacote_origem",
            )
        )

        if self.action == "list":
            queryset = self._aplicar_filtros_listagem(queryset).order_by(
                "data_hora_inicio",
                "pk",
            )

        return queryset

    def _filtro_data(self, valor, campo, fim_exclusivo=False):
        """
        Aceita AAAA-MM-DD ou data e hora ISO 8601. Sem fuso, usa o fuso do
        projeto. Uma data sem hora em data_fim inclui o dia inteiro.
        """
        valor = valor.strip()

        try:
            dia = parse_date(valor)
            data_hora = None if dia else parse_datetime(valor)
        except ValueError:
            dia = None
            data_hora = None

        if dia is not None:
            if fim_exclusivo:
                dia = dia + timedelta(days=1)
            data_hora = datetime.combine(dia, time.min)

        if data_hora is None:
            raise ValidationError({
                campo: (
                    "Informe uma data (AAAA-MM-DD) ou data e hora "
                    "em formato ISO 8601."
                )
            })

        if timezone.is_naive(data_hora):
            data_hora = timezone.make_aware(
                data_hora,
                timezone.get_current_timezone(),
            )

        return data_hora

    def _aplicar_filtros_listagem(self, queryset):
        """
        Filtros opcionais da listagem (a resposta continua sendo um array):
        data_inicio, data_fim, profissional, cliente e status. O período
        retorna os agendamentos que se sobrepõem a [data_inicio, data_fim).
        """
        params = self.request.query_params

        data_inicio = params.get("data_inicio")
        if data_inicio:
            inicio = self._filtro_data(data_inicio, "data_inicio")
            queryset = queryset.filter(data_hora_fim__gt=inicio)

        data_fim = params.get("data_fim")
        if data_fim:
            fim = self._filtro_data(
                data_fim,
                "data_fim",
                fim_exclusivo=True,
            )
            queryset = queryset.filter(data_hora_inicio__lt=fim)

        for campo in ("profissional", "cliente"):
            valor = params.get(campo)

            if valor:
                try:
                    identificador = uuid.UUID(valor)
                except ValueError:
                    raise ValidationError({
                        campo: "Informe um identificador (UUID) válido."
                    })

                queryset = queryset.filter(**{f"{campo}_id": identificador})

        status_filtro = params.get("status")
        if status_filtro:
            if status_filtro not in dict(Agendamento.STATUS_CHOICES):
                raise ValidationError({
                    "status": (
                        "Utilize PENDENTE, CONFIRMADO, CANCELADO ou CONCLUIDO."
                    )
                })

            queryset = queryset.filter(status=status_filtro)

        return queryset

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

    def _buscar_conflitos(
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
                "data_hora_fim": (
                    "O horário final deve ser posterior ao inicial."
                )
            })

        conflitos = Agendamento.objects.filter(
            clinica=clinica,
            status__in=[
                Agendamento.PENDENTE,
                Agendamento.CONFIRMADO,
            ],
            data_hora_inicio__lt=fim,
            data_hora_fim__gt=inicio,
        ).filter(
            Q(profissional_id=profissional_id)
            | Q(cliente_id=cliente_id)
        )

        if agendamento_id is not None:
            conflitos = conflitos.exclude(pk=agendamento_id)

        return conflitos.select_for_update().order_by("pk")

    def _validar_conflitos(
        self,
        clinica,
        profissional_id,
        cliente_id,
        inicio,
        fim,
        agendamento_id=None,
    ):
        conflitos = self._buscar_conflitos(
            clinica,
            profissional_id,
            cliente_id,
            inicio,
            fim,
            agendamento_id,
        )

        if conflitos.exists():
            raise ConflictException(
                "Existe um agendamento PENDENTE ou CONFIRMADO "
                "no mesmo intervalo. Resolva o conflito explicitamente."
            )

    def _snapshot(self, agendamento):
        return {
            "status": agendamento.status,
            "resultado": agendamento.resultado,
            "motivo_cancelamento": agendamento.motivo_cancelamento,
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

    def _registrar_historico_sessao(
        self,
        sessao,
        agendamento,
        estado_anterior,
        estado_novo,
        motivo,
        justificativa="",
    ):
        HistoricoSessao.objects.create(
            sessao=sessao,
            estado_anterior=estado_anterior,
            estado_novo=estado_novo,
            usuario_executor=self.request.user,
            agendamento_relacionado=agendamento,
            motivo=motivo,
            justificativa=justificativa,
        )

    def _liberar_sessao_pacote(
        self,
        agendamento,
        motivo,
        justificativa="",
    ):
        sessao = (
            SessaoPacote.objects.select_for_update()
            .filter(agendamento=agendamento)
            .first()
        )

        if not sessao or sessao.status != SessaoPacote.AGENDADA:
            return

        estado_anterior = sessao.status
        sessao.status = SessaoPacote.DISPONIVEL
        sessao.agendamento = None
        sessao.save(update_fields=[
            "status",
            "agendamento",
            "updated_at",
        ])

        self._registrar_historico_sessao(
            sessao=sessao,
            agendamento=agendamento,
            estado_anterior=estado_anterior,
            estado_novo=SessaoPacote.DISPONIVEL,
            motivo=motivo,
            justificativa=justificativa,
        )

    def _cancelar_por_sobreposicao(self, agendamento):
        anteriores = self._snapshot(agendamento)

        agendamento.status = Agendamento.CANCELADO
        agendamento.motivo_cancelamento = "SOBREPOSICAO"
        agendamento.save(update_fields=[
            "status",
            "motivo_cancelamento",
            "updated_at",
        ])

        self._liberar_sessao_pacote(
            agendamento,
            motivo="Cancelamento por sobreposição de horário",
            justificativa="SOBREPOSICAO",
        )

        self._registrar_auditoria(
            agendamento,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(agendamento),
        )

    def _interpretar_data_hora(self, valor, campo):
        if not isinstance(valor, str) or not valor.strip():
            raise ValidationError({
                campo: (
                    "Informe uma data e hora válidas em formato ISO 8601."
                )
            })

        data_hora = parse_datetime(valor.strip())

        if data_hora is None:
            raise ValidationError({
                campo: (
                    "Informe uma data e hora válidas em formato ISO 8601."
                )
            })

        if timezone.is_naive(data_hora):
            data_hora = timezone.make_aware(
                data_hora,
                timezone.get_current_timezone(),
            )

        return data_hora

    def _resolver_conflito_criacao(
        self,
        clinica,
        profissional,
        cliente,
        inicio,
        fim,
    ):
        conflitos = list(
            self._buscar_conflitos(
                clinica,
                profissional.id,
                cliente.id,
                inicio,
                fim,
            )
        )

        confirmados = [
            item
            for item in conflitos
            if item.status == Agendamento.CONFIRMADO
        ]

        if confirmados:
            raise ConflictException({
                "detail": (
                    "O horário possui agendamento confirmado. "
                    "Nenhum agendamento foi alterado."
                ),
                "conflitos_confirmados": [
                    {
                        "id": item.pk,
                        "inicio": item.data_hora_inicio.isoformat(),
                        "fim": item.data_hora_fim.isoformat(),
                    }
                    for item in confirmados
                ],
            })

        pendentes = [
            item
            for item in conflitos
            if item.status == Agendamento.PENDENTE
        ]

        if not pendentes:
            return

        if len(pendentes) > 1:
            raise ConflictException({
                "detail": (
                    "Existem vários agendamentos pendentes conflitantes. "
                    "Remaneje os agendamentos individualmente e tente "
                    "novamente, ou resolva os conflitos antes de confirmar "
                    "um novo agendamento."
                ),
                "conflitos_pendentes": [
                    {
                        "id": item.pk,
                        "inicio": item.data_hora_inicio.isoformat(),
                        "fim": item.data_hora_fim.isoformat(),
                    }
                    for item in pendentes
                ],
            })

        request_data = self.request.data
        decisao = request_data.get("resolucao_conflito")
        conflito_id = request_data.get("agendamento_conflitante_id")

        if not decisao:
            raise ConflictException({
                "detail": (
                    "Existe um agendamento pendente no mesmo intervalo. "
                    "Informe uma resolução explícita."
                ),
                "opcoes": [
                    "REMANEJAR",
                    "CANCELAR_E_CONFIRMAR",
                ],
                "conflitos_pendentes": [
                    {
                        "id": item.pk,
                        "inicio": item.data_hora_inicio.isoformat(),
                        "fim": item.data_hora_fim.isoformat(),
                    }
                    for item in pendentes
                ],
            })

        if decisao not in (
            "REMANEJAR",
            "CANCELAR_E_CONFIRMAR",
        ):
            raise ValidationError({
                "resolucao_conflito": (
                    "Utilize REMANEJAR ou CANCELAR_E_CONFIRMAR."
                )
            })

        if conflito_id is None:
            raise ValidationError({
                "agendamento_conflitante_id": (
                    "Informe o ID do agendamento pendente que será resolvido."
                )
            })

        try:
            conflito_id = int(conflito_id)
        except (TypeError, ValueError):
            raise ValidationError({
                "agendamento_conflitante_id": (
                    "Informe um ID de agendamento válido."
                )
            })

        conflito = next(
            (item for item in pendentes if item.pk == conflito_id),
            None,
        )

        if conflito is None:
            raise ValidationError({
                "agendamento_conflitante_id": (
                    "O ID informado não corresponde a um agendamento "
                    "pendente conflitante desta clínica."
                )
            })

        if decisao == "CANCELAR_E_CONFIRMAR":
            self._cancelar_por_sobreposicao(conflito)

        else:
            novo_inicio = self._interpretar_data_hora(
                request_data.get("conflito_novo_inicio"),
                "conflito_novo_inicio",
            )
            novo_fim = self._interpretar_data_hora(
                request_data.get("conflito_novo_fim"),
                "conflito_novo_fim",
            )

            if novo_inicio >= novo_fim:
                raise ValidationError({
                    "conflito_novo_fim": (
                        "O horário final deve ser posterior ao inicial."
                    )
                })

            conflitos_novo_horario = self._buscar_conflitos(
                clinica=conflito.clinica,
                profissional_id=conflito.profissional_id,
                cliente_id=conflito.cliente_id,
                inicio=novo_inicio,
                fim=novo_fim,
                agendamento_id=conflito.pk,
            )

            if conflitos_novo_horario.exists():
                raise ConflictException({
                    "detail": (
                        "O novo horário escolhido para o agendamento "
                        "pendente também possui conflitos."
                    ),
                    "conflitos_novo_horario": [
                        {
                            "id": item.pk,
                            "status": item.status,
                            "inicio": item.data_hora_inicio.isoformat(),
                            "fim": item.data_hora_fim.isoformat(),
                        }
                        for item in conflitos_novo_horario
                    ],
                })

            anteriores = self._snapshot(conflito)

            conflito.data_hora_inicio = novo_inicio
            conflito.data_hora_fim = novo_fim
            conflito.save(update_fields=[
                "data_hora_inicio",
                "data_hora_fim",
                "updated_at",
            ])

            self._registrar_auditoria(
                conflito,
                Auditoria.UPDATE,
                dados_anteriores=anteriores,
                dados_novos=self._snapshot(conflito),
            )

        conflitos_restantes = list(
            self._buscar_conflitos(
                clinica,
                profissional.id,
                cliente.id,
                inicio,
                fim,
            )
        )

        if conflitos_restantes:
            raise ConflictException({
                "detail": (
                    "Ainda existem conflitos no horário solicitado. "
                    "Nenhuma alteração parcial foi mantida."
                ),
                "conflitos": [
                    {
                        "id": item.pk,
                        "status": item.status,
                        "inicio": item.data_hora_inicio.isoformat(),
                        "fim": item.data_hora_fim.isoformat(),
                    }
                    for item in conflitos_restantes
                ],
            })

    @transaction.atomic
    def perform_create(self, serializer):
        clinica = self.get_clinica()
        profissional = serializer.validated_data["profissional"]
        cliente = serializer.validated_data["cliente"]
        inicio = serializer.validated_data["data_hora_inicio"]
        fim = serializer.validated_data["data_hora_fim"]

        self._validar_cliente_ativo(cliente, clinica)
        self._validar_autonomia_agenda(clinica, profissional.id)

        self._resolver_conflito_criacao(
            clinica,
            profissional,
            cliente,
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
            dados_novos=self._snapshot(agendamento),
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
        self._validar_autonomia_agenda(clinica, profissional.id)

        conflitos = self._buscar_conflitos(
            clinica,
            profissional.id,
            cliente.id,
            inicio,
            fim,
            agendamento_id=agendamento.id,
        ).filter(status=Agendamento.CONFIRMADO)

        if conflitos.exists():
            raise ConflictException(
                "Existe um agendamento CONFIRMADO no mesmo intervalo."
            )

        anteriores = self._snapshot(agendamento)

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
            dados_novos=self._snapshot(agendamento),
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def registrar_falta(self, request, pk=None):
        agendamento = (
            self.get_queryset()
            .select_for_update(of=("self",))
            .get(pk=pk)
        )
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

        anteriores = self._snapshot(agendamento)

        agendamento.status = Agendamento.CONCLUIDO
        agendamento.resultado = Agendamento.FALTA
        agendamento.save(update_fields=[
            "status",
            "resultado",
            "updated_at",
        ])

        decisao_registrada = None

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

            self._registrar_historico_sessao(
                sessao=sessao,
                agendamento=agendamento,
                estado_anterior=estado_anterior,
                estado_novo=estado_novo,
                motivo="Registro manual de falta",
                justificativa=justificativa,
            )

            decisao_registrada = decisao

        self._registrar_auditoria(
            agendamento,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos={
                **self._snapshot(agendamento),
                "decisao_sessao": decisao_registrada,
                "justificativa": justificativa,
            },
        )

        return Response({
            "detail": "Falta registrada.",
            "agendamento_id": str(agendamento.id),
            "resultado": agendamento.resultado,
            "decisao_sessao": decisao_registrada,
        })

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancelar(self, request, pk=None):
        agendamento = (
            self.get_queryset()
            .select_for_update(of=("self",))
            .get(pk=pk)
        )
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

        anteriores = self._snapshot(agendamento)

        agendamento.status = Agendamento.CANCELADO
        agendamento.motivo_cancelamento = motivo.strip()[:50]
        agendamento.save(update_fields=[
            "status",
            "motivo_cancelamento",
            "updated_at",
        ])

        self._liberar_sessao_pacote(
            agendamento,
            motivo="Cancelamento de agendamento",
            justificativa=motivo.strip(),
        )

        self._registrar_auditoria(
            agendamento,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(agendamento),
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