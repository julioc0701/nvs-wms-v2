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
