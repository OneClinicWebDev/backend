
import re

from django.core.exceptions import ValidationError


def somente_digitos(value):
    return re.sub(r"[^0-9]", "", str(value or ""))


def _normalizar_campo(value, campo, padroes):
    valor = str(value or "").strip()

    if not valor:
        raise ValidationError(f"{campo} é obrigatório.")

    if not any(re.fullmatch(padrao, valor) for padrao in padroes):
        raise ValidationError(
            f"{campo} contém caracteres inválidos ou está em formato incorreto."
        )

    return somente_digitos(valor)


def validar_cpf(value):
    cpf = _normalizar_campo(
        value,
        "CPF",
        (
            r"[0-9]{11}",
            r"[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}",
        ),
    )

    if len(cpf) != 11 or len(set(cpf)) == 1:
        raise ValidationError(
            "CPF inválido. Informe os 11 dígitos corretamente."
        )

    soma = sum(
        int(cpf[indice]) * (10 - indice)
        for indice in range(9)
    )
    resto = soma % 11
    primeiro_digito = 0 if resto < 2 else 11 - resto

    soma = sum(
        int(cpf[indice]) * (11 - indice)
        for indice in range(9)
    ) + primeiro_digito * 2

    resto = soma % 11
    segundo_digito = 0 if resto < 2 else 11 - resto

    if cpf[-2:] != f"{primeiro_digito}{segundo_digito}":
        raise ValidationError(
            "CPF inválido. Informe os 11 dígitos corretamente."
        )

    return cpf


def validar_cnpj(value):
    cnpj = _normalizar_campo(
        value,
        "CNPJ",
        (
            r"[0-9]{14}",
            r"[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}",
        ),
    )

    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        raise ValidationError(
            "CNPJ inválido. Informe os 14 dígitos corretamente."
        )

    pesos1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    pesos2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

    soma1 = sum(
        int(digito) * peso
        for digito, peso in zip(cnpj[:12], pesos1)
    )
    resto1 = soma1 % 11
    digito1 = 0 if resto1 < 2 else 11 - resto1

    soma2 = sum(
        int(digito) * peso
        for digito, peso in zip(cnpj[:12] + str(digito1), pesos2)
    )
    resto2 = soma2 % 11
    digito2 = 0 if resto2 < 2 else 11 - resto2

    if cnpj[-2:] != f"{digito1}{digito2}":
        raise ValidationError(
            "CNPJ inválido. Informe os 14 dígitos corretamente."
        )

    return cnpj


def validar_telefone(value):
    telefone = _normalizar_campo(
        value,
        "Telefone",
        (
            r"[0-9]{10,11}",
            r"\([0-9]{2}\) ?[0-9]{4,5}-?[0-9]{4}",
            r"[0-9]{2} ?[0-9]{4,5}-?[0-9]{4}",
        ),
    )

    if len(telefone) not in (10, 11):
        raise ValidationError(
            "Telefone inválido. Informe o DDD e um número com 10 ou 11 dígitos."
        )

    return telefone


def validar_telefone_opcional(value):
    if not str(value or "").strip():
        return ""

    return validar_telefone(value)


def validar_cep(value):
    cep = _normalizar_campo(
        value,
        "CEP",
        (
            r"[0-9]{8}",
            r"[0-9]{5}-[0-9]{3}",
        ),
    )

    if len(cep) != 8:
        raise ValidationError(
            "CEP inválido. Informe os 8 dígitos corretamente."
        )

    return cep
