"""Extrai a linha digitável de um boleto a partir de uma foto, via Vision AI.

Auto-detecta qual provider de IA está disponível no ambiente:
  1. GOOGLE_AI_STUDIO_KEY → Gemini 2.0 Flash (1500 req/dia grátis)
  2. GROQ_API_KEY → Llama 3.2 90B Vision (14400 req/dia grátis)
  3. OPENROUTER_API_KEY → roteamento aberto

Override manual via env BOLETO_VISION_PROVIDER (gemini|groq|openrouter).
"""
import os
import re
import httpx
import logging

log = logging.getLogger(__name__)

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
    "Olhe com atenção em todas as direções da imagem e encontre a 'linha digitável' — "
    "uma sequência de 47 dígitos numéricos agrupados (geralmente impressa "
    "acima do código de barras grosso). "
    "Exemplo de formato: 23792.37213 90016.790967 25000.527306 3 14580000058182. "
    "RESPONDA APENAS com os 47 dígitos numéricos CONSECUTIVOS, sem pontos, sem espaços, "
    "sem qualquer outro texto. "
    "Se não conseguir identificar com 100% de certeza, responda exatamente: NAO_ENCONTRADO"
)


class BoletoVisionError(Exception):
    """Erro na chamada de visão (timeout, API key faltando, modelo recusou)."""


async def extrair_linha_digitavel(foto_b64: str) -> str:
    """Recebe uma foto em base64 e retorna a linha digitável (47 dígitos numéricos).

    Levanta BoletoVisionError em qualquer falha.
    """
    provider, api_key, base_url, model = _detectar_provider()
    log.info(f"[VISION] provider={provider} model={model}")

    # Normaliza o base64: aceita tanto "data:image/jpeg;base64,..." quanto string pura
    if foto_b64.startswith("data:"):
        data_url = foto_b64
    else:
        data_url = f"data:image/jpeg;base64,{foto_b64}"

    payload = {
        "model": model,
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
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
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
