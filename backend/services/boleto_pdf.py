"""Extrai a linha digitável de um boleto a partir de um PDF.

PDFs gerados por bancos/sistemas têm o texto da linha digitável embedado
(não imagem). Usamos pdfplumber para ler o texto e regex para localizar
a linha de 47 dígitos no formato padrão FEBRABAN.

Cobre os layouts mais comuns:
  - "23792.37213 90016.790967 25000.527306 3 14580000058182" (padrão com pontos/espaços)
  - "23792372139001679096725000527306314580000058182" (sem separadores)
"""
import re
from io import BytesIO

import pdfplumber


class BoletoPdfError(Exception):
    """Erro ao processar PDF de boleto."""


# Padrão da linha digitável com pontos e espaços (formato impresso)
_REGEX_FORMATADA = re.compile(
    r"(\d{5})[\.\-\s]*(\d{5})\s+(\d{5})[\.\-\s]*(\d{6})\s+(\d{5})[\.\-\s]*(\d{6})\s+(\d)\s+(\d{14})"
)

# Padrão sem separadores (47 dígitos consecutivos)
_REGEX_BRUTA = re.compile(r"\b(\d{47})\b")


def extrair_linha_digitavel_de_pdf(content: bytes) -> str:
    """Extrai a linha digitável de 47 dígitos do PDF de um boleto.

    Tenta primeiro o padrão formatado (5 dígitos pontos/espaços), depois
    o padrão bruto de 47 dígitos seguidos. Retorna apenas os números.

    Levanta BoletoPdfError se não encontrar.
    """
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                texto = page.extract_text() or ""

                # Tentativa 1: padrão formatado
                m = _REGEX_FORMATADA.search(texto)
                if m:
                    return "".join(m.groups())  # 5+5+5+6+5+6+1+14 = 47

                # Tentativa 2: 47 dígitos seguidos
                m = _REGEX_BRUTA.search(texto.replace(" ", "").replace(".", ""))
                if m:
                    return m.group(1)
    except Exception as e:
        raise BoletoPdfError(f"Falha ao ler PDF: {e}")

    raise BoletoPdfError(
        "Linha digitável não encontrada no PDF. "
        "Verifique se é um boleto válido ou se o PDF tem camada de texto (não é imagem)."
    )
