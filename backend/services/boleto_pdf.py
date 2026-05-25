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

# Padrões pra identificar o beneficiário em ordem de confiabilidade.
# Cada padrão captura o NOME (group 1).
_PADROES_BENEFICIARIO = [
    # "Cedente" — comum em boletos. Texto após o rótulo na linha de baixo.
    # Ex: "Cedente Agencia / Código cedente\nLELLO CONDOMINIOS LTDA CNPJ: ..."
    re.compile(
        r"Cedente[^\n]*\n([^\n]+)",
        re.IGNORECASE,
    ),
    # "Beneficiário final" — rotula explicitamente o nome
    re.compile(
        r"Benefici[áa]rio\s+final\s+([^\n]+?)(?:\s+CNPJ|\s+CPF|\n)",
        re.IGNORECASE,
    ),
    # "Beneficiário" com `:` ou na linha de baixo, ignorando cabeçalhos de tabela
    re.compile(
        r"Benefici[áa]rio\s*[:\n]\s*([^\n]+)",
        re.IGNORECASE,
    ),
]

# Rótulos de campos adjacentes que devem ser removidos do final do nome
_RUIDO_ADJACENTE = re.compile(
    r"\s+(CNPJ|CPF|Ag[êe]ncia|Vencimento|N[uúº]\.?\s*Documento|Carteira|"
    r"Nosso\s*Numero|N[uú]mero|C[oó]digo|Carteira).*$",
    re.IGNORECASE,
)

# Cabeçalhos de tabela que NÃO são nomes de empresa
_CABECALHOS = {
    "carteira",
    "carteira / nosso numero",
    "carteira/nosso numero",
    "agencia",
    "agência",
    "vencimento",
    "carteira nosso numero",
}


def _limpar_nome(nome: str) -> str:
    """Remove ruído comum (CNPJ, rótulos de campos adjacentes)."""
    nome = nome.strip()
    # Remove CNPJ/CPF na mesma linha (formato XX.XXX.XXX/XXXX-XX ou XXX.XXX.XXX-XX)
    nome = re.sub(r"\s+\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}.*$", "", nome).strip()
    nome = re.sub(r"\s+\d{3}\.\d{3}\.\d{3}-\d{2}.*$", "", nome).strip()
    # Remove rótulos colados de campos adjacentes
    nome = _RUIDO_ADJACENTE.sub("", nome).strip()
    return nome


def _extrair_beneficiario(texto: str) -> str | None:
    """Tenta localizar o nome do beneficiário usando múltiplos padrões."""
    for padrao in _PADROES_BENEFICIARIO:
        for m in padrao.finditer(texto):
            nome = _limpar_nome(m.group(1))
            # Descarta cabeçalhos de tabela e nomes muito curtos
            if len(nome) < 3:
                continue
            if nome.lower() in _CABECALHOS:
                continue
            # Descarta se for só números (improvável ser nome de empresa)
            if not any(c.isalpha() for c in nome):
                continue
            return nome
    return None


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
