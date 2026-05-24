"""Parser de código de barras / linha digitável FEBRABAN para boletos bancários.

Cobre apenas boletos bancários (primeiros 3 dígitos = código do banco).
Boletos de arrecadação (primeiro dígito = 8) NÃO são suportados — lançam BoletoInvalidoError.
"""


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
