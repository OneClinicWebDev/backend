import re
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from core.models import Auditoria, PrimeiroAcessoCodigo, Usuario

ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODIGO_TAMANHO = 10
CODIGO_GRUPO = 5
VALIDADE_HORAS = 48
MAX_TENTATIVAS = 5


class PrimeiroAcessoIndisponivel(Exception):
    pass


def normalizar_codigo(valor):
    return re.sub(r"[^A-Z0-9]", "", str(valor or "").upper())


def formatar_codigo(codigo):
    return f"{codigo[:CODIGO_GRUPO]}-{codigo[CODIGO_GRUPO:]}"


def _sortear_codigo():
    return "".join(
        secrets.choice(ALFABETO_CODIGO) for _ in range(CODIGO_TAMANHO)
    )


@transaction.atomic
def gerar_codigo_primeiro_acesso(colaborador, criado_por=None):
    if not colaborador.ativo:
        raise PrimeiroAcessoIndisponivel(
            "Reative o colaborador antes de gerar um código de primeiro acesso."
        )

    if colaborador.usuario.has_usable_password():
        raise PrimeiroAcessoIndisponivel(
            "Este colaborador já possui senha cadastrada e entra com o "
            "CPF e a senha atuais."
        )

    agora = timezone.now()

    PrimeiroAcessoCodigo.objects.filter(
        colaborador=colaborador,
        usado_em__isnull=True,
        invalidado_em__isnull=True,
    ).update(invalidado_em=agora)

    codigo = _sortear_codigo()

    registro = PrimeiroAcessoCodigo.objects.create(
        colaborador=colaborador,
        codigo_hash=make_password(codigo),
        expira_em=agora + timedelta(hours=VALIDADE_HORAS),
        criado_por=criado_por,
    )

    return formatar_codigo(codigo), registro


def concluir_primeiro_acesso(cpf, codigo, nova_senha, ip=None, user_agent=""):
    agora = timezone.now()

    with transaction.atomic():
        usuario = (
            Usuario.objects.select_for_update()
            .filter(cpf=cpf, is_active=True)
            .first()
        )

        if usuario is None or usuario.has_usable_password():
            return False

        codigos = list(
            PrimeiroAcessoCodigo.objects.select_for_update(of=("self",))
            .select_related("colaborador__clinica")
            .filter(
                colaborador__usuario=usuario,
                colaborador__ativo=True,
                colaborador__clinica__ativo=True,
                usado_em__isnull=True,
                invalidado_em__isnull=True,
                expira_em__gt=agora,
            )
        )

        if not codigos:
            return False

        correspondente = next(
            (
                item
                for item in codigos
                if check_password(codigo, item.codigo_hash)
            ),
            None,
        )

        if correspondente is None:
            for item in codigos:
                item.tentativas_falhas += 1
                if item.tentativas_falhas >= MAX_TENTATIVAS:
                    item.invalidado_em = agora
                item.save(
                    update_fields=[
                        "tentativas_falhas",
                        "invalidado_em",
                        "updated_at",
                    ]
                )
            return False

        validate_password(nova_senha, user=usuario)

        usuario.set_password(nova_senha)
        usuario.save(update_fields=["password", "updated_at"])

        correspondente.usado_em = agora
        correspondente.save(update_fields=["usado_em", "updated_at"])

        PrimeiroAcessoCodigo.objects.filter(
            colaborador__usuario=usuario,
            usado_em__isnull=True,
            invalidado_em__isnull=True,
        ).update(invalidado_em=agora)

        Auditoria.objects.create(
            usuario=usuario,
            clinica=correspondente.colaborador.clinica,
            acao=Auditoria.UPDATE,
            entidade="Colaborador",
            objeto_id=str(correspondente.colaborador_id),
            dados_anteriores=None,
            dados_novos={"primeiro_acesso_concluido": True},
            origem="USUARIO",
            ip=ip or None,
            user_agent=user_agent or "",
        )

    return True