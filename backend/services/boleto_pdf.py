"""Extrai linha digitável + beneficiário de um boleto a partir de um PDF.

PDFs gerados por bancos/sistemas têm o texto embedado (não imagem). Usamos
pdfplumber para ler o texto e regex para localizar:
  - A linha digitável (47 dígitos formato FEBRABAN)
  - O beneficiário (linha após "Beneficiário" / "Local de Pagamento")
"""
import re
from dataclasses import dataclass
from io import BytesIO

import pdfplumber


@dataclass
class BoletoPdfResult:
    linha_digitavel: str
    beneficiario: str | None


class BoletoPdfError(Exception):
    """Erro ao processar PDF de boleto."""


# Padrão da linha digitável com pontos e espaços (formato impresso)
_REGEX_FORMATADA = re.compile(
    r"(\d{5})[\.\-\s]*(\d{5})\s+(\d{5})[\.\-\s]*(\d{6})\s+(\d{5})[\.\-\s]*(\d{6})\s+(\d)\s+(\d{14})"
)

# Padrão sem separadores (47 dígitos consecutivos)
_REGEX_BRUTA = re.compile(r"\b(\d{47})\b")

# Beneficiário: linha que aparece após "Beneficiário" (com tolerância a acentos/caps)
_REGEX_BENEFICIARIO = re.compile(
    r"Benefici[áa]rio\s*[:\n]\s*([^\n]+)",
    re.IGNORECASE,
)


def _extrair_beneficiario(texto: str) -> str | None:
    """Tenta localizar o nome do beneficiário no texto do PDF."""
    m = _REGEX_BENEFICIARIO.search(texto)
    if not m:
        return None
    nome = m.group(1).strip()
    # Remove ruído comum: rótulos colados, CNPJ na mesma linha
    # Ex: "BRF S.A. CD JUNDIAI   01.838.723/0001-27"
    nome = re.sub(r"\s+\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}.*$", "", nome).strip()
    # Remove rótulos comuns do próximo campo que possam estar concatenados
    nome = re.sub(r"\s+(Ag[êe]ncia|Vencimento|N[uúº]\.?\s*Documento).*$", "", nome,
                  flags=re.IGNORECASE).strip()
    if len(nome) < 3:
        return None
    return nome


def extrair_linha_digitavel_de_pdf(content: bytes) -> BoletoPdfResult:
    """Extrai linha digitável + beneficiário do PDF de um boleto.

    Tenta primeiro o padrão formatado, depois o bruto de 47 dígitos seguidos.
    Beneficiário é opcional — pode vir None.

    Levanta BoletoPdfError se a linha digitável não for encontrada.
    """
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                texto = page.extract_text() or ""

                linha = None
                m = _REGEX_FORMATADA.search(texto)
                if m:
                    linha = "".join(m.groups())
                else:
                    m = _REGEX_BRUTA.search(texto.replace(" ", "").replace(".", ""))
                    if m:
                        linha = m.group(1)

                if linha:
                    beneficiario = _extrair_beneficiario(texto)
                    return BoletoPdfResult(linha_digitavel=linha, beneficiario=beneficiario)
    except Exception as e:
        raise BoletoPdfError(f"Falha ao ler PDF: {e}")

    raise BoletoPdfError(
        "Linha digitável não encontrada no PDF. "
        "Verifique se é um boleto válido ou se o PDF tem camada de texto (não é imagem)."
    )
