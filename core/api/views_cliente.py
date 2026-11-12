from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.models import (
    Agendamento,
    Auditoria,
    Cliente,
    HistoricoSessao,
    Pacote,
    ProcedimentoRealizado,
    SessaoPacote,
    Usuario,
)
from .base import ClinicaContextMixin
from .permissions import (
    IsAdminOrSecretario,
    IsAdminOrSecretarioOuProfissionalAgenda,
)
from .serializers_core import ClienteSerializer


class ClienteViewSet(ClinicaContextMixin, viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [IsAdminOrSecretario]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAdminOrSecretarioOuProfissionalAgenda()]
        return [IsAdminOrSecretario()]

    def get_queryset(self):
        return (
            Cliente.objects.filter(clinica=self.get_clinica())
            .select_related("usuario", "clinica")
        )

    def _snapshot(self, cliente):
        return {
            "usuario_id": str(cliente.usuario_id),
            "telefone": cliente.telefone,
            "cep": cliente.cep,
            "numero_endereco": cliente.numero_endereco,
            "status_cadastro": cliente.status_cadastro,
        }

    def _registrar_auditoria(
        self,
        cliente,
        acao,
        dados_anteriores=None,
        dados_novos=None,
    ):
        ip = self.request.META.get("REMOTE_ADDR")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        Auditoria.objects.create(
            usuario=self.request.user,
            clinica=cliente.clinica,
            acao=acao,
            entidade="Cliente",
            objeto_id=str(cliente.id),
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            origem="USUARIO",
            ip=ip or None,
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @action(detail=True, methods=["get"])
    def historico(self, request, pk=None):
        cliente = self.get_object()
        clinica = self.get_clinica()

        try:
            limite = max(1, min(int(request.query_params.get("limite", 200)), 500))
        except (TypeError, ValueError):
            limite = 200

        procedimentos = (
            ProcedimentoRealizado.objects.filter(clinica=clinica, cliente=cliente)
            .order_by("-realizado_em", "-pk")[:limite]
        )

        agendamentos = (
            Agendamento.objects.filter(clinica=clinica, cliente=cliente)
            .select_related("servico", "profissional__usuario", "pacote_origem__modelo")
            .order_by("-data_hora_inicio", "-pk")[:limite]
        )

        pacotes = (
            Pacote.objects.filter(clinica=clinica, cliente=cliente)
            .select_related("servico", "modelo")
            .annotate(
                total_disponiveis=Count("sessoes", filter=Q(sessoes__status=SessaoPacote.DISPONIVEL)),
                total_agendadas=Count("sessoes", filter=Q(sessoes__status=SessaoPacote.AGENDADA)),
                total_utilizadas=Count("sessoes", filter=Q(sessoes__status=SessaoPacote.UTILIZADA)),
                total_perdidas=Count("sessoes", filter=Q(sessoes__status=SessaoPacote.PERDIDA)),
                total_canceladas=Count("sessoes", filter=Q(sessoes__status=SessaoPacote.CANCELADA)),
            )
            .order_by("-created_at", "-pk")
        )

        movimentos = (
            HistoricoSessao.objects.filter(sessao__pacote__clinica=clinica, sessao__pacote__cliente=cliente)
            .select_related("usuario_executor", "sessao__pacote__servico", "sessao__pacote__modelo")
            .order_by("-data_alteracao", "-pk")[:limite]
        )

        lista_agendamentos = []
        cancelamentos = []
        faltas = []

        for item in agendamentos:
            dado = {
                "id": item.pk,
                "servico_nome": item.servico.nome,
                "profissional_nome": item.profissional.usuario.nome_completo,
                "pacote_id": item.pacote_origem_id,
                "pacote_nome": (
                    (item.pacote_origem.modelo.nome if item.pacote_origem.modelo_id else f"Pacote {item.pacote_origem_id}")
                    if item.pacote_origem_id
                    else ""
                ),
                "data_hora_inicio": item.data_hora_inicio,
                "data_hora_fim": item.data_hora_fim,
                "status": item.status,
                "resultado": item.resultado,
                "motivo_cancelamento": item.motivo_cancelamento,
            }
            lista_agendamentos.append(dado)
            if item.status == Agendamento.CANCELADO:
                cancelamentos.append(dado)
            if item.resultado == Agendamento.FALTA:
                faltas.append(dado)

        lista_pacotes = [
            {
                "id": p.pk,
                "nome": p.modelo.nome if p.modelo_id else f"Pacote {p.pk}",
                "servico_nome": p.servico.nome,
                "status": p.status,
                "quantidade_sessoes": p.quantidade_sessoes,
                "valor_total": str(p.valor_total),
                "disponiveis": p.total_disponiveis,
                "agendadas": p.total_agendadas,
                "utilizadas": p.total_utilizadas,
                "perdidas": p.total_perdidas,
                "canceladas": p.total_canceladas,
                "saldo": p.total_disponiveis,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in pacotes
        ]

        lista_procedimentos = [
            {
                "id": p.pk,
                "agendamento_id": p.agendamento_id,
                "servico_nome": p.servico_nome,
                "profissional_nome": p.profissional_nome,
                "pacote_id": p.pacote_id,
                "pacote_nome": p.pacote_nome,
                "sessao_id": p.sessao_id,
                "valor": str(p.valor),
                "duracao_minutos": p.duracao_minutos,
                "realizado_em": p.realizado_em,
                "origem": p.origem,
                "status": p.status,
                "estornado_em": p.estornado_em,
                "motivo_estorno": p.motivo_estorno,
            }
            for p in procedimentos
        ]

        lista_movimentos = [
            {
                "id": m.pk,
                "sessao_id": m.sessao_id,
                "pacote_id": m.sessao.pacote_id,
                "pacote_nome": (
                    m.sessao.pacote.modelo.nome
                    if m.sessao.pacote.modelo_id
                    else f"Pacote {m.sessao.pacote_id}"
                ),
                "estado_anterior": m.estado_anterior,
                "estado_novo": m.estado_novo,
                "motivo": m.motivo,
                "justificativa": m.justificativa,
                "responsavel": m.usuario_executor.nome_completo if m.usuario_executor else "Sistema",
                "agendamento_id": m.agendamento_relacionado_id,
                "data_alteracao": m.data_alteracao,
            }
            for m in movimentos
        ]

        return Response({
            "cliente_id": str(cliente.pk),
            "resumo": {
                "procedimentos_realizados": sum(1 for p in lista_procedimentos if p["status"] == ProcedimentoRealizado.REALIZADO),
                "atendimentos": len(lista_agendamentos),
                "cancelamentos": len(cancelamentos),
                "faltas": len(faltas),
                "pacotes": len(lista_pacotes),
                "sessoes_utilizadas": sum(p["utilizadas"] for p in lista_pacotes),
                "sessoes_disponiveis": sum(p["disponiveis"] for p in lista_pacotes),
                "sessoes_perdidas": sum(p["perdidas"] for p in lista_pacotes),
            },
            "procedimentos": lista_procedimentos,
            "atendimentos": lista_agendamentos,
            "cancelamentos": cancelamentos,
            "faltas": faltas,
            "pacotes": lista_pacotes,
            "movimentos_sessao": lista_movimentos,
        })

    @transaction.atomic
    def perform_create(self, serializer):
        cpf = serializer.validated_data.pop("cpf", None)
        nome = serializer.validated_data.pop("nome_completo", "")

        if not cpf:
            raise ValidationError({"cpf": "O CPF é obrigatório para cadastrar o cliente."})

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
                cliente = serializer.save(clinica=self.get_clinica(), usuario=usuario)
        except IntegrityError:
            raise ValidationError({
                "usuario": (
                    "Este usuário já possui cadastro de cliente "
                    "nesta clínica."
                )
            })

        self._registrar_auditoria(
            cliente,
            Auditoria.CREATE,
            dados_novos=self._snapshot(cliente),
        )

    @transaction.atomic
    def perform_update(self, serializer):
        cliente = self.get_object()
        anteriores = self._snapshot(cliente)

        cliente = serializer.save(clinica=self.get_clinica())

        self._registrar_auditoria(
            cliente,
            Auditoria.UPDATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(cliente),
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        cliente = self.get_object()

        if cliente.status_cadastro == Cliente.INATIVO:
            return Response(
                {"detail": "O cliente já está inativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        anteriores = self._snapshot(cliente)

        cliente.status_cadastro = Cliente.INATIVO
        cliente.save(update_fields=["status_cadastro", "updated_at"])

        self._registrar_auditoria(
            cliente,
            Auditoria.DEACTIVATE,
            dados_anteriores=anteriores,
            dados_novos=self._snapshot(cliente),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)