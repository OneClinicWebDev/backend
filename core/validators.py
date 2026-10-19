import re

from django.core.exceptions import ValidationError


def somente_digitos(value):
    return re.sub(r"\D", "", str(value or ""))


def validar_cpf(value):
    cpf = somente_digitos(value)

    if len(cpf) != 11 or len(set(cpf)) == 1:
        raise ValidationError("CPF inválido. Informe os 11 dígitos corretamente.")

    for tamanho in (9, 10):
        soma = sum(
            int(cpf[indice]) * (tamanho + 1 - indice)
            for indice in range(tamanho)
        )
        resto = (soma * 10) % 11
        digito = 0 if resto == 10 else resto

        if digito != int(cpf[tamanho]):
            raise ValidationError("CPF inválido. Informe os 11 dígitos corretamente.")

    return cpf


def validar_cnpj(value):
    cnpj = somente_digitos(value)

    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        raise ValidationError("CNPJ inválido. Informe os 14 dígitos corretamente.")

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
        raise ValidationError("CNPJ inválido. Informe os 14 dígitos corretamente.")

    return cnpj


def validar_telefone(value):
    telefone = somente_digitos(value)

    if not 10 <= len(telefone) <= 11:
        raise ValidationError(
            "Telefone inválido. Informe o DDD e um número com 10 ou 11 dígitos."
        )

    return telefone


def validar_telefone_opcional(value):
    telefone = somente_digitos(value)

    if not telefone:
        return ""

    return validar_telefone(telefone)