"""Extrai linha digitável + beneficiário de um boleto a partir de uma foto, via Vision AI.

Auto-detecta qual provider de IA está disponível no ambiente:
  1. GOOGLE_AI_STUDIO_KEY → Gemini 2.0 Flash (1500 req/dia grátis)
  2. GROQ_API_KEY → Llama 4 Scout vision (14400 req/dia grátis)
  3. OPENROUTER_API_KEY → roteamento aberto

Override manual via env BOLETO_VISION_PROVIDER (gemini|groq|openrouter).

ROTAÇÃO AUTOMÁTICA: fotos de boleto frequentemente vêm deitadas ou de cabeça
pra baixo. O serviço tenta a imagem em 4 orientações (0°, 90°, 270°, 180°) e
usa o DV (dígito verificador) do parser FEBRABAN como checksum para escolher
a leitura correta — para na primeira rotação cujo DV bate.
"""
import base64
import json
import os
import re
import httpx
import logging
from dataclasses import dataclass
from io import BytesIO

log = logging.getLogger(__name__)

# Ordem das rotações testadas. 0° primeiro (foto já correta acerta em 1 chamada).
# 90° costuma resolver fotos deitadas; 270° e 180° cobrem o resto.
_ROTACOES = [0, 90, 270, 180]


@dataclass
class BoletoVisionResult:
    linha_digitavel: str
    beneficiario: str | None  # nome da empresa, None se IA não identificou

_TIMEOUT_S = float(os.getenv("BOLETO_VISION_TIMEOUT_S", "15"))


def _detectar_provider() -> tuple[str, str, str, str]:
    """Retorna (provider_nome, api_key, base_url, model) baseado nas envs disponíveis.

    Lança BoletoVisionError se nenhuma chave for encontrada.
    """
    override = os.getenv("BOLETO_VISION_PROVIDER", "").lower()
    google_key = os.getenv("GOOGLE_AI_STUDIO_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    # Permite override manual
    if override == "gemini" and google_key:
        return ("gemini", google_key,
                "https://generativelanguage.googleapis.com/v1beta/openai",
                os.getenv("BOLETO_VISION_MODEL", "gemini-2.0-flash"))
    if override == "groq" and groq_key:
        return ("groq", groq_key,
                "https://api.groq.com/openai/v1",
                os.getenv("BOLETO_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"))
    if override == "openrouter" and openrouter_key:
        return ("openrouter", openrouter_key,
                "https://openrouter.ai/api/v1",
                os.getenv("BOLETO_VISION_MODEL", "google/gemini-2.0-flash-exp:free"))

    # Auto-detecção em ordem de preferência
    if google_key:
        return ("gemini", google_key,
                "https://generativelanguage.googleapis.com/v1beta/openai",
                os.getenv("BOLETO_VISION_MODEL", "gemini-2.0-flash"))
    if groq_key:
        return ("groq", groq_key,
                "https://api.groq.com/openai/v1",
                os.getenv("BOLETO_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"))
    if openrouter_key:
        return ("openrouter", openrouter_key,
                "https://openrouter.ai/api/v1",
                os.getenv("BOLETO_VISION_MODEL", "google/gemini-2.0-flash-exp:free"))

    raise BoletoVisionError(
        "Nenhuma chave de IA configurada. Defina GOOGLE_AI_STUDIO_KEY, "
        "GROQ_API_KEY ou OPENROUTER_API_KEY no Railway."
    )

_PROMPT = (
    "Esta imagem é uma foto de um boleto bancário brasileiro. "
    "A foto pode estar rotacionada (deitada, de cabeça pra baixo ou em qualquer ângulo). "
    "Analise em todas as direções e extraia DOIS dados:\n"
    "1) LINHA_DIGITAVEL: sequência de 47 dígitos numéricos consecutivos "
    "(exemplo formatado: 23792.37213 90016.790967 25000.527306 3 14580000058182). "
    "Devolva apenas os 47 dígitos juntos, sem pontos nem espaços.\n"
    "2) BENEFICIARIO: nome da empresa que vai receber o pagamento. "
    "Aparece logo abaixo do campo 'Local de Pagamento' ou rotulado como 'Beneficiário' "
    "ou 'Cliente'. Exemplo: 'BRF S.A. - CD JUNDIAI'. Retorne o texto inteiro como está.\n\n"
    "RESPONDA APENAS em JSON válido neste formato exato, sem ``` nem texto adicional:\n"
    '{"linha_digitavel": "<47 dígitos ou NAO_ENCONTRADO>", '
    '"beneficiario": "<nome ou NAO_ENCONTRADO>"}'
)


class BoletoVisionError(Exception):
    """Erro na chamada de visão (timeout, API key faltando, modelo recusou)."""


def _normalizar_b64(foto_b64: str) -> bytes:
    """Extrai os bytes da imagem a partir de base64 (com ou sem prefixo data:)."""
    if foto_b64.startswith("data:"):
        foto_b64 = foto_b64.split(",", 1)[1]
    return base64.b64decode(foto_b64)


def _rotacionar_para_b64(raw: bytes, graus: int) -> str:
    """Corrige orientação EXIF, rotaciona `graus` (anti-horário) e devolve base64 JPEG.

    Se Pillow não estiver disponível, devolve o base64 original (fallback).
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        log.warning("[VISION] Pillow indisponível — usando imagem sem rotação")
        return base64.b64encode(raw).decode()

    img = Image.open(BytesIO(raw))
    img = ImageOps.exif_transpose(img)  # corrige orientação automática de celular
    if graus:
        img = img.rotate(graus, expand=True)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


async def _chamar_modelo(b64: str, api_key: str, base_url: str, model: str) -> tuple[str, str | None] | None:
    """Chama o modelo de visão UMA vez. Retorna (digitos, beneficiario) ou None.

    Retorna None se o modelo respondeu NAO_ENCONTRADO ou JSON inválido (falha leve).
    Levanta BoletoVisionError só em falhas duras (timeout, HTTP, chave).
    """
    payload = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise BoletoVisionError("Tempo esgotado ao chamar o modelo de visão")
    except httpx.HTTPStatusError as e:
        log.error(f"Vision HTTP {e.response.status_code}: {e.response.text[:300]}")
        raise BoletoVisionError(f"Erro do modelo de visão ({e.response.status_code})")
    except Exception as e:
        raise BoletoVisionError(f"Falha inesperada: {e}")

    try:
        resposta = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError):
        return None

    bloco = re.search(r"\{.*\}", resposta, re.DOTALL)
    if not bloco:
        return None
    try:
        parsed_json = json.loads(bloco.group(0))
    except json.JSONDecodeError:
        return None

    linha_raw = str(parsed_json.get("linha_digitavel", "")).strip()
    benef_raw = str(parsed_json.get("beneficiario", "")).strip()
    if not linha_raw or "NAO_ENCONTRADO" in linha_raw.upper():
        return None

    digitos = re.sub(r"\D", "", linha_raw)
    beneficiario = None
    if benef_raw and "NAO_ENCONTRADO" not in benef_raw.upper():
        beneficiario = benef_raw
    return (digitos, beneficiario)


async def extrair_linha_digitavel(foto_b64: str) -> BoletoVisionResult:
    """Recebe foto em base64 e retorna BoletoVisionResult com linha + beneficiário.

    Tenta a imagem em várias rotações (0°, 90°, 270°, 180°). Para cada leitura,
    valida com o parser FEBRABAN e usa o DV como checksum:
      - Se o DV bate → retorna imediatamente (leitura correta garantida)
      - Senão guarda como fallback (44/47 dígitos, mas DV não confere)
    Se nenhuma rotação produz leitura válida, levanta BoletoVisionError.
    """
    from services.boleto_parser import parse_boleto, BoletoInvalidoError

    provider, api_key, base_url, model = _detectar_provider()
    log.info(f"[VISION] provider={provider} model={model}")

    raw = _normalizar_b64(foto_b64)
    fallback: BoletoVisionResult | None = None

    for graus in _ROTACOES:
        b64 = _rotacionar_para_b64(raw, graus)
        try:
            res = await _chamar_modelo(b64, api_key, base_url, model)
        except BoletoVisionError:
            raise  # falha dura (timeout/HTTP/chave) aborta tudo
        if not res:
            log.info(f"[VISION] rotação {graus}°: nada reconhecido")
            continue

        digitos, beneficiario = res
        if len(digitos) not in (44, 47):
            log.info(f"[VISION] rotação {graus}°: {len(digitos)} dígitos (descarta)")
            continue

        try:
            parsed = parse_boleto(digitos)
        except BoletoInvalidoError:
            log.info(f"[VISION] rotação {graus}°: parser rejeitou")
            continue

        if parsed.dv_ok:
            log.info(f"[VISION] rotação {graus}°: DV OK ✓ (banco {parsed.banco})")
            return BoletoVisionResult(linha_digitavel=digitos, beneficiario=beneficiario)

        # DV não bate, mas tamanho ok — guarda como último recurso
        if fallback is None:
            log.info(f"[VISION] rotação {graus}°: DV não bate, guardando fallback")
            fallback = BoletoVisionResult(linha_digitavel=digitos, beneficiario=beneficiario)

    if fallback is not None:
        log.info("[VISION] nenhuma rotação com DV válido — retornando melhor leitura")
        return fallback

    raise BoletoVisionError(
        "Não foi possível ler o boleto. Tente uma foto mais nítida, "
        "bem enquadrada e com boa iluminação."
    )
