from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from core.models import (
    Agendamento,
    Auditoria,
    HistoricoSessao,
    Pacote,
    ProcedimentoRealizado,
    SessaoPacote,
)


class RegraAtendimentoError(Exception):
    pass


def sincronizar_status_pacote(pacote):
    if pacote is None or pacote.status == Pacote.CANCELADO:
        return pacote.status if pacote else None

    ainda_ativas = SessaoPacote.objects.filter(
        pacote=pacote,
        status__in=[SessaoPacote.DISPONIVEL, SessaoPacote.AGENDADA],
    ).exists()

    novo = Pacote.ATIVO if ainda_ativas else Pacote.CONCLUIDO

    if pacote.status != novo:
        pacote.status = novo
        pacote.save(update_fields=["status", "updated_at"])

    return pacote.status


def _registrar_historico(sessao, agendamento, anterior, novo, usuario, motivo, justificativa=""):
    HistoricoSessao.objects.create(
        sessao=sessao,
        estado_anterior=anterior,
        estado_novo=novo,
        usuario_executor=usuario,
        agendamento_relacionado=agendamento,
        motivo=motivo,
        justificativa=justificativa,
    )


def _nome_usuario(usuario_obj):
    return getattr(usuario_obj, "nome_completo", "") or str(usuario_obj)


def concluir_atendimento(
    agendamento_id,
    usuario=None,
    origem=ProcedimentoRealizado.ORIGEM_AUTOMATICA,
    exigir_inicio=False,
):
    with transaction.atomic():
        agendamento = (
            Agendamento.objects.select_for_update(of=("self",))
            .select_related(
                "clinica",
                "cliente__usuario",
                "profissional__usuario",
                "servico",
            )
            .filter(pk=agendamento_id)
            .first()
        )

        if agendamento is None:
            raise RegraAtendimentoError("Agendamento não encontrado.")

        if agendamento.status == Agendamento.CANCELADO:
            raise RegraAtendimentoError(
                "Agendamentos cancelados não podem ser concluídos."
            )

        if agendamento.status != Agendamento.CONFIRMADO:
            raise RegraAtendimentoError(
                "Somente agendamentos confirmados podem ser concluídos."
            )

        if agendamento.resultado == Agendamento.FALTA:
            raise RegraAtendimentoError(
                "Agendamentos com falta registrada não podem ser concluídos."
            )

        agora = timezone.now()

        if exigir_inicio and agendamento.data_hora_inicio > agora:
            raise RegraAtendimentoError(
                "O atendimento ainda não começou e não pode ser concluído."
            )

        if ProcedimentoRealizado.objects.filter(
            agendamento=agendamento
        ).exists():
            raise RegraAtendimentoError(
                "Este atendimento já possui procedimento registrado."
            )

        sessao = (
            SessaoPacote.objects.select_for_update()
            .filter(agendamento=agendamento)
            .first()
        )

        pacote = None

        if sessao is not None:
            pacote = Pacote.objects.select_for_update().get(
                pk=sessao.pacote_id
            )

            if (
                pacote.clinica_id != agendamento.clinica_id
                or pacote.cliente_id != agendamento.cliente_id
                or pacote.servico_id != agendamento.servico_id
            ):
                raise RegraAtendimentoError(
                    "A sessão reservada pertence a um pacote de outro "
                    "cliente ou de outro procedimento."
                )

            if pacote.status == Pacote.CANCELADO:
                raise RegraAtendimentoError(
                    "O pacote da sessão reservada está cancelado."
                )

            if sessao.status != SessaoPacote.AGENDADA:
                raise RegraAtendimentoError(
                    "A sessão vinculada não está reservada para este "
                    f"atendimento (estado atual: {sessao.status})."
                )
        elif agendamento.pacote_origem_id:
            raise RegraAtendimentoError(
                "O agendamento usa um pacote, mas não possui sessão "
                "reservada. Corrija a reserva antes de concluir."
            )

        resultado_anterior = agendamento.resultado

        agendamento.status = Agendamento.CONCLUIDO
        agendamento.resultado = Agendamento.REALIZADO
        agendamento.save(update_fields=["status", "resultado", "updated_at"])

        sessoes_consumidas = 0

        if sessao is not None:
            sessao.status = SessaoPacote.UTILIZADA
            sessao.save(update_fields=["status", "updated_at"])
            _registrar_historico(
                sessao,
                agendamento,
                SessaoPacote.AGENDADA,
                SessaoPacote.UTILIZADA,
                usuario,
                "Conclusão do atendimento",
                "Conclusão automática pela rotina do sistema."
                if usuario is None
                else "Conclusão manual do atendimento.",
            )
            sessoes_consumidas = 1

        cliente = agendamento.cliente
        profissional = agendamento.profissional
        servico = agendamento.servico

        valor = agendamento.preco_acordado
        if valor is None:
            valor = Decimal("0.00") if pacote is not None else servico.preco
        if valor is None:
            valor = Decimal("0.00")

        duracao = int(
            (
                agendamento.data_hora_fim - agendamento.data_hora_inicio
            ).total_seconds()
            // 60
        )
        if duracao <= 0:
            duracao = servico.duracao_padrao_minutos

        procedimento = ProcedimentoRealizado.objects.create(
            clinica=agendamento.clinica,
            cliente=cliente,
            profissional=profissional,
            servico=servico,
            agendamento=agendamento,
            pacote=pacote,
            sessao=sessao,
            cliente_nome=_nome_usuario(cliente.usuario),
            profissional_nome=_nome_usuario(profissional.usuario),
            servico_nome=servico.nome,
            pacote_nome=(
                (
                    pacote.modelo.nome
                    if pacote.modelo_id
                    else f"Pacote {pacote.pk}"
                )
                if pacote is not None
                else ""
            ),
            valor=valor,
            duracao_minutos=duracao,
            realizado_em=agendamento.data_hora_fim,
            origem=origem,
            registrado_por=usuario,
        )

        status_pacote = (
            sincronizar_status_pacote(pacote) if pacote is not None else None
        )

        Auditoria.objects.create(
            clinica=agendamento.clinica,
            usuario=usuario,
            acao=Auditoria.UPDATE,
            entidade="Agendamento",
            objeto_id=str(agendamento.id),
            dados_anteriores={
                "status": Agendamento.CONFIRMADO,
                "resultado": resultado_anterior,
            },
            dados_novos={
                "status": Agendamento.CONCLUIDO,
                "resultado": agendamento.resultado,
                "sessoes_consumidas": sessoes_consumidas,
                "procedimento_realizado_id": procedimento.pk,
                "status_pacote": status_pacote,
                "origem": origem,
            },
            origem="SISTEMA" if usuario is None else "USUARIO",
        )

        return procedimento, sessoes_consumidas


def estornar_procedimento(agendamento, usuario, motivo, destino_sessao=None):
    procedimento = (
        ProcedimentoRealizado.objects.select_for_update()
        .filter(agendamento=agendamento, status=ProcedimentoRealizado.REALIZADO)
        .first()
    )

    if procedimento is None:
        return None

    destino = {
        "PRESERVAR": ProcedimentoRealizado.DESTINO_DEVOLVIDA,
        "PERDER": ProcedimentoRealizado.DESTINO_PERDIDA,
    }.get(destino_sessao, ProcedimentoRealizado.DESTINO_NAO_APLICAVEL)

    agora = timezone.now()

    procedimento.status = ProcedimentoRealizado.ESTORNADO
    procedimento.estornado_em = agora
    procedimento.estornado_por = usuario
    procedimento.motivo_estorno = motivo or ""
    procedimento.destino_sessao = destino

    try:
        procedimento.save(update_fields=[
            "status",
            "estornado_em",
            "estornado_por",
            "motivo_estorno",
            "destino_sessao",
            "updated_at",
        ])
    except DjangoValidationError as exc:
        raise RegraAtendimentoError("; ".join(exc.messages))

    Auditoria.objects.create(
        clinica=procedimento.clinica,
        usuario=usuario,
        acao=Auditoria.UPDATE,
        entidade="ProcedimentoRealizado",
        objeto_id=str(procedimento.pk),
        dados_anteriores={"status": ProcedimentoRealizado.REALIZADO},
        dados_novos={
            "status": ProcedimentoRealizado.ESTORNADO,
            "agendamento_id": agendamento.pk,
            "sessao_id": procedimento.sessao_id,
            "destino_sessao": destino,
            "motivo": motivo or "",
            "estornado_em": agora.isoformat(),
        },
        origem="USUARIO" if usuario is not None else "SISTEMA",
    )

    return procedimento