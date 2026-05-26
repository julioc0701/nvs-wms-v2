"""Agregador puro. Sem I/O. Recebe dados, devolve KPIs e tabela.

Implementa as fórmulas validadas em Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md §3.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP

ME1_OR_OUTROS_BUCKETS = {"me1", "outros"}


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_line_mc(*, produto_total: Decimal, frete_comprador: Decimal,
                     frete_vendedor: Decimal, custo: Decimal, imposto: Decimal,
                     tarifa_liquida: Decimal, refund_parcial: Decimal,
                     logistic_type: str | None, shipping_mode: str | None) -> dict:
    """Calcula MC e MC% pra uma linha de venda.

    Regra: frete_comprador é subtraído da base salvo quando modalidade é ME1
    ou "Outro (a combinar)" — nestes casos o vendedor absorve o frete.
    """
    bucket = _logistic_bucket(logistic_type, shipping_mode)
    keeps_buyer_freight = bucket in ME1_OR_OUTROS_BUCKETS

    vendas_aprovadas_linha = produto_total + frete_comprador  # = Faturamento ML linha

    if keeps_buyer_freight:
        base = vendas_aprovadas_linha
    else:
        base = produto_total

    mc = base - custo - imposto - tarifa_liquida - frete_vendedor - refund_parcial
    mc_pct = (mc / produto_total * Decimal("100")) if produto_total > 0 else Decimal("0")

    return {
        "mc": _q(mc),
        "mc_pct": _q(mc_pct),
        "vendas_aprovadas_linha": _q(vendas_aprovadas_linha),
    }


def _logistic_bucket(logistic_type: str | None, shipping_mode: str | None) -> str:
    """Mapeia campos ML pra bucket do breakdown logístico.

    Mapping inicial — refinar quando testes ML revelarem combinações reais.
    """
    if shipping_mode == "me1":
        return "me1"
    if logistic_type == "fulfillment":
        return "full"
    if logistic_type == "self_service":
        return "flex"
    if logistic_type in ("drop_off", "cross_docking"):
        return "places_coleta"
    return "outros"
