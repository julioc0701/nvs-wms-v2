"""Parser de código de barras / linha digitável FEBRABAN para boletos bancários.

Cobre apenas boletos bancários (primeiros 3 dígitos = código do banco).
Boletos de arrecadação (primeiro dígito = 8) NÃO são suportados — lançam BoletoInvalidoError.
"""
from datetime import date, timedelta


# Base FEBRABAN antiga: fator 1000 = 03/07/2000.
# Em 2025-02-21 o fator atingiu 9999 e foi feito o wrap.
# Base nova: fator 1000 = 22/02/2025.
_BASE_FATOR = 1000
_BASE_DATA_ANTIGA = date(2000, 7, 3)
_BASE_DATA_NOVA = date(2025, 2, 22)


def fator_para_data(fator: int) -> date:
    """Converte fator de vencimento (4 dígitos do código de barras) para data.

    Lida com o wraparound de 2025-02-21: se a data calculada com a base antiga
    cair mais de 1 ano antes de hoje, assume base nova (pós-wrap).
    """
    if fator < 0:
        raise ValueError(f"Fator inválido: {fator}")
    data_antiga = _BASE_DATA_ANTIGA + timedelta(days=fator - _BASE_FATOR)
    hoje = date.today()
    if data_antiga < hoje - timedelta(days=365):
        # Provavelmente boleto pós-wrap usando a base nova.
        return _BASE_DATA_NOVA + timedelta(days=fator - _BASE_FATOR)
    return data_antiga


def dv_mod10(campo: str) -> int:
    """Calcula o DV módulo 10 de um campo da linha digitável.

    Multiplica cada dígito (direita → esquerda) alternando pesos 2,1,2,1,...
    Se produto ≥ 10, soma os dígitos. Acumula. DV = 10 - (soma % 10).
    Se DV resultar em 10, retorna 0.
    """
    if not campo.isdigit():
        raise ValueError(f"Campo deve ser todo numérico: {campo!r}")
    pesos = [2, 1] * len(campo)
    soma = 0
    for digito, peso in zip(reversed(campo), pesos):
        produto = int(digito) * peso
        if produto >= 10:
            produto = (produto // 10) + (produto % 10)
        soma += produto
    dv = 10 - (soma % 10)
    return 0 if dv == 10 else dv


def dv_mod11_codigo_barras(codigo_sem_dv: str) -> int:
    """Calcula o DV módulo 11 do código de barras (posição 5 do código de 44 dígitos).

    Recebe os 43 dígitos do código sem o DV. Multiplica cada dígito da DIREITA para a
    ESQUERDA por pesos cíclicos 2,3,4,5,6,7,2,3,4,5,6,7,... Soma tudo. resto = soma % 11.
    DV = 11 - resto. Se DV resultar em 0, 10 ou 11, retorna 1.
    """
    if len(codigo_sem_dv) != 43 or not codigo_sem_dv.isdigit():
        raise ValueError(
            f"DV mod 11 espera exatamente 43 dígitos, recebeu {len(codigo_sem_dv)}"
        )
    pesos_ciclo = [2, 3, 4, 5, 6, 7]
    soma = 0
    for i, digito in enumerate(reversed(codigo_sem_dv)):
        peso = pesos_ciclo[i % 6]
        soma += int(digito) * peso
    resto = soma % 11
    dv = 11 - resto
    return 1 if dv in (0, 10, 11) else dv


# ── parse_boleto (função pública unificada) ──────────────────────────────────
from dataclasses import dataclass
from decimal import Decimal


class BoletoInvalidoError(ValueError):
    """Erro ao parsear código de barras / linha digitável de boleto."""


@dataclass(frozen=True)
class BoletoParsed:
    codigo_barras: str
    linha_digitavel: str
    banco: str
    valor: Decimal
    vencimento: date
    campo_livre: str
    dv_ok: bool


def _so_digitos(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _linha_digitavel_para_codigo_barras(linha: str) -> str:
    """Converte uma linha digitável de 47 dígitos no código de barras de 44 dígitos.

    Layout (sem espaços/pontos):
        AAA B CCCCC D CCCCCCCCCC E CCCCCCCCCC F G HHHH VVVVVVVVVV
        (3) (1) (5) (1) (10)    (1) (10)    (1)(1)(4) (10)
    Onde D,E,F = DVs mod10 dos campos 1,2,3 e G = DV geral mod11.
    """
    if len(linha) != 47:
        raise BoletoInvalidoError(f"Linha digitável deve ter 47 dígitos, recebeu {len(linha)}")
    campo1 = linha[0:9]    # banco(3)+moeda(1)+livre[1-5]
    # DV campo1 em linha[9]
    campo2 = linha[10:20]  # livre[6-15]
    # DV campo2 em linha[20]
    campo3 = linha[21:31]  # livre[16-25]
    # DV campo3 em linha[31]
    dv_geral = linha[32]
    fator_valor = linha[33:47]

    banco_moeda = campo1[0:4]
    livre_1_5 = campo1[4:9]
    livre_6_25 = campo2 + campo3
    return banco_moeda + dv_geral + fator_valor + livre_1_5 + livre_6_25


def _codigo_barras_para_linha_digitavel(codigo: str) -> str:
    """Converte código de barras de 44 dígitos na linha digitável de 47 dígitos."""
    banco_moeda = codigo[0:4]
    dv_geral = codigo[4]
    fator_valor = codigo[5:19]
    livre_1_5 = codigo[19:24]
    livre_6_15 = codigo[24:34]
    livre_16_25 = codigo[34:44]

    campo1 = banco_moeda + livre_1_5
    campo2 = livre_6_15
    campo3 = livre_16_25
    return (
        campo1 + str(dv_mod10(campo1))
        + campo2 + str(dv_mod10(campo2))
        + campo3 + str(dv_mod10(campo3))
        + dv_geral
        + fator_valor
    )


def parse_boleto(entrada: str) -> BoletoParsed:
    """Parseia código de barras (44 díg) ou linha digitável (47 díg) de boleto bancário.

    Levanta BoletoInvalidoError em caso de tamanho errado, DV inválido ou boleto de arrecadação.
    """
    digitos = _so_digitos(entrada)
    if len(digitos) == 44:
        codigo = digitos
    elif len(digitos) == 47:
        codigo = _linha_digitavel_para_codigo_barras(digitos)
    else:
        raise BoletoInvalidoError(
            f"tamanho inválido: esperado 44 ou 47 dígitos, recebeu {len(digitos)}"
        )

    if codigo[0] == "8":
        raise BoletoInvalidoError("Boletos de arrecadação não são suportados no MVP")

    banco = codigo[0:3]
    dv_geral_informado = int(codigo[4])
    fator = int(codigo[5:9])
    valor_cent = int(codigo[9:19])
    campo_livre = codigo[19:44]

    codigo_sem_dv = codigo[0:4] + codigo[5:44]
    dv_geral_calculado = dv_mod11_codigo_barras(codigo_sem_dv)
    dv_ok = dv_geral_informado == dv_geral_calculado

    valor = Decimal(valor_cent) / Decimal(100)
    vencimento = fator_para_data(fator)
    linha_digitavel = _codigo_barras_para_linha_digitavel(codigo)

    return BoletoParsed(
        codigo_barras=codigo,
        linha_digitavel=linha_digitavel,
        banco=banco,
        valor=valor,
        vencimento=vencimento,
        campo_livre=campo_livre,
        dv_ok=dv_ok,
    )
