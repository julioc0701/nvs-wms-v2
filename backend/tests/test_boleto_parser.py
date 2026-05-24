"""Unit tests do parser FEBRABAN de boletos."""
import pytest


def test_dv_mod10_todos_zeros_retorna_zero():
    """Soma 0 → DV = 10 → wrap para 0."""
    from services.boleto_parser import dv_mod10
    assert dv_mod10("0000000000") == 0


def test_dv_mod10_caso_simples():
    """
    '1234567890' → pesos R→L (2,1,2,1,2,1,2,1,2,1):
      0*2=0, 9*1=9, 8*2=16→7, 7*1=7, 6*2=12→3, 5*1=5, 4*2=8, 3*1=3, 2*2=4, 1*1=1
    Soma = 47, DV = 10 - 7 = 3.
    """
    from services.boleto_parser import dv_mod10
    assert dv_mod10("1234567890") == 3


def test_dv_mod10_todos_noves():
    """
    '9999999999' → cada 9*2=18→9 e 9*1=9. Soma = 90, DV = 10 - 0 = 10 → wrap 0.
    """
    from services.boleto_parser import dv_mod10
    assert dv_mod10("9999999999") == 0


def test_dv_mod10_um_a_esquerda():
    """'1000000000' → único produto: 1*1=1. Soma=1. DV=10-1=9."""
    from services.boleto_parser import dv_mod10
    assert dv_mod10("1000000000") == 9


def test_dv_mod10_rejeita_nao_digito():
    from services.boleto_parser import dv_mod10
    with pytest.raises(ValueError):
        dv_mod10("12345abc90")


# ── DV mod 11 (DV geral do código de barras) ─────────────────────────────────


def test_dv_mod11_todos_zeros_resulta_em_um():
    """Soma 0 → resto 0 → DV bruto = 11 → wrap para 1."""
    from services.boleto_parser import dv_mod11_codigo_barras
    assert dv_mod11_codigo_barras("0" * 43) == 1


def test_dv_mod11_todos_uns():
    """
    43 dígitos '1', pesos cíclicos [2,3,4,5,6,7] R→L.
    Cada ciclo de 6 pos: soma = 2+3+4+5+6+7 = 27.
    7 ciclos completos (42 pos) + 1 pos extra (peso 2) = 7*27 + 2 = 191.
    191 % 11 = 4; DV = 11 - 4 = 7.
    """
    from services.boleto_parser import dv_mod11_codigo_barras
    assert dv_mod11_codigo_barras("1" * 43) == 7


def test_dv_mod11_boleto_construido_manualmente():
    """
    Boleto fictício: banco=237, moeda=9, fator=3380, valor=0000010005, livre=25 zeros.
    Código sem DV: "2379" + "3380" + "0000010005" + ("0" * 25)
    Cálculo manual produz soma = 171, resto = 6, DV = 5.
    """
    from services.boleto_parser import dv_mod11_codigo_barras
    codigo_sem_dv = "2379" + "3380" + "0000010005" + ("0" * 25)
    assert len(codigo_sem_dv) == 43
    assert dv_mod11_codigo_barras(codigo_sem_dv) == 5


def test_dv_mod11_rejeita_tamanho_errado():
    from services.boleto_parser import dv_mod11_codigo_barras
    with pytest.raises(ValueError):
        dv_mod11_codigo_barras("123")


# ── Fator vencimento → data ───────────────────────────────────────────────────


def test_fator_para_data_usa_base_nova_pos_wrap():
    """
    Após o wrap de 2025-02-21, FEBRABAN definiu fator 1000 = 22/02/2025.
    Como hoje (>2026) é muito posterior à base antiga, o parser opta pela nova.
    """
    from datetime import date
    from services.boleto_parser import fator_para_data
    assert fator_para_data(1000) == date(2025, 2, 22)


def test_fator_para_data_dia_seguinte():
    from datetime import date
    from services.boleto_parser import fator_para_data
    assert fator_para_data(1001) == date(2025, 2, 23)


def test_fator_para_data_3380_no_futuro():
    """Caso usado no teste de construção de boleto fictício."""
    from datetime import date, timedelta
    from services.boleto_parser import fator_para_data
    esperado = date(2025, 2, 22) + timedelta(days=2380)
    assert fator_para_data(3380) == esperado


# ── parse_boleto (função pública unificada) ──────────────────────────────────


def test_parse_boleto_a_partir_do_codigo_de_barras():
    """Boleto fictício Bradesco com DV mod 11 = 5 (calculado no teste anterior)."""
    from datetime import date, timedelta
    from decimal import Decimal
    from services.boleto_parser import parse_boleto

    # Banco=237, moeda=9, DV=5, fator=3380, valor=0000010005 (R$ 100,05), livre=25 zeros
    codigo = "237" + "9" + "5" + "3380" + "0000010005" + ("0" * 25)
    assert len(codigo) == 44

    r = parse_boleto(codigo)
    assert r.codigo_barras == codigo
    assert r.banco == "237"
    assert r.valor == Decimal("100.05")
    assert r.vencimento == date(2025, 2, 22) + timedelta(days=2380)
    assert r.campo_livre == "0" * 25
    assert r.dv_ok is True
    # Linha digitável tem 47 dígitos
    assert len(r.linha_digitavel) == 47


def test_parse_boleto_a_partir_da_linha_digitavel():
    """Linha digitável gerada a partir do mesmo código fictício acima.

    Campos:
      Campo 1 (banco_moeda + livre_1-5 + DV): "23790000 0" → DV mod10 de "237900000" = 9
      Campo 2 (livre_6-15 + DV):              "0000000000 0"
      Campo 3 (livre_16-25 + DV):             "0000000000 0"
      DV geral: 5
      Fator + valor: "3380 0000010005"
    """
    from services.boleto_parser import parse_boleto

    linha = "2379000009" + "00000000000" + "00000000000" + "5" + "33800000010005"
    assert len(linha) == 47
    r = parse_boleto(linha)
    assert r.banco == "237"
    assert r.dv_ok is True


def test_parse_boleto_remove_espacos_e_pontos():
    from services.boleto_parser import parse_boleto

    # Mesma linha "2379000009 00000000000 00000000000 5 33800000010005" formatada
    # como aparece num boleto físico (47 dígitos no total).
    linha_suja = "  23790.00009 00000.000000 00000.000000 5 33800000010005  "
    r = parse_boleto(linha_suja)
    assert r.banco == "237"
    assert r.dv_ok is True


def test_parse_boleto_arrecadacao_lanca_erro():
    """Boletos de arrecadação começam com 8 → fora de escopo no MVP."""
    from services.boleto_parser import parse_boleto, BoletoInvalidoError
    with pytest.raises(BoletoInvalidoError, match="arrecada"):
        parse_boleto("8" + "0" * 43)


def test_parse_boleto_dv_invalido_retorna_dv_ok_false():
    """Boleto com DV geral errado é parseado mesmo assim, com dv_ok=False."""
    from services.boleto_parser import parse_boleto
    codigo_dv_errado = "237" + "9" + "1" + "3380" + "0000010005" + ("0" * 25)
    r = parse_boleto(codigo_dv_errado)
    assert r.dv_ok is False
    assert r.banco == "237"


def test_parse_boleto_tamanho_invalido_lanca_erro():
    from services.boleto_parser import parse_boleto, BoletoInvalidoError
    with pytest.raises(BoletoInvalidoError, match="tamanho"):
        parse_boleto("123")
