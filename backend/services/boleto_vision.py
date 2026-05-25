"""Extrai a linha digitável de um boleto a partir de uma foto, via Gemini Vision.

Usa a mesma API OpenAI-compatible do Google AI Studio (`GOOGLE_AI_STUDIO_KEY`)
já configurada para o resto do projeto.

Modelo padrão: `gemini-2.0-flash` (vision built-in, free tier 1500 req/dia).
Override via env `BOLETO_VISION_MODEL`.
"""
import os
import re
import httpx
import logging

log = logging.getLogger(__name__)

_BASE_URL = os.getenv(
    "BOLETO_VISION_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai",
)
_MODEL = os.getenv("BOLETO_VISION_MODEL", "gemini-2.0-flash")
_TIMEOUT_S = float(os.getenv("BOLETO_VISION_TIMEOUT_S", "15"))

_PROMPT = (
    "Esta imagem é de um boleto bancário brasileiro. "
    "Localize a linha digitável (sequência de 47 dígitos numéricos agrupados "
    "tipo '00000.00000 00000.000000 00000.000000 0 00000000000000') "
    "que aparece impressa acima do código de barras. "
    "Responda APENAS com os 47 dígitos, sem pontos, sem espaços, sem texto adicional. "
    "Se não conseguir identificar com certeza, responda exatamente: NAO_ENCONTRADO."
)


class BoletoVisionError(Exception):
    """Erro na chamada de visão (timeout, API key faltando, modelo recusou)."""


async def extrair_linha_digitavel(foto_b64: str) -> str:
    """Recebe uma foto em base64 e retorna a linha digitável (47 dígitos numéricos).

    Levanta BoletoVisionError em qualquer falha.
    """
    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise BoletoVisionError("Chave de IA não configurada (GOOGLE_AI_STUDIO_KEY)")

    # Normaliza o base64: aceita tanto "data:image/jpeg;base64,..." quanto string pura
    if foto_b64.startswith("data:"):
        data_url = foto_b64
    else:
        data_url = f"data:image/jpeg;base64,{foto_b64}"

    payload = {
        "model": _MODEL,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(
                f"{_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise BoletoVisionError("Tempo esgotado ao chamar o modelo de visão")
    except httpx.HTTPStatusError as e:
        log.error(f"Vision HTTP {e.response.status_code}: {e.response.text[:200]}")
        raise BoletoVisionError(f"Erro do modelo de visão ({e.response.status_code})")
    except Exception as e:
        raise BoletoVisionError(f"Falha inesperada: {e}")

    try:
        resposta = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError):
        raise BoletoVisionError("Resposta do modelo em formato inesperado")

    log.info(f"[VISION] resposta bruta: {resposta[:80]}")

    if "NAO_ENCONTRADO" in resposta.upper():
        raise BoletoVisionError("Não foi possível identificar o boleto na foto")

    # Limpa qualquer separador que o modelo possa ter incluído
    digitos = re.sub(r"\D", "", resposta)

    if len(digitos) != 47 and len(digitos) != 44:
        raise BoletoVisionError(
            f"Modelo retornou {len(digitos)} dígitos (esperado 47 ou 44)"
        )

    return digitos
