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
