import asyncio
import re
import httpx
import os
import logging
from typing import Dict, Any, List
from uuid import uuid4

log = logging.getLogger(__name__)

_THOUGHT_RE = re.compile(r"<thought>.*?</thought>\s*", re.DOTALL | re.IGNORECASE)

def _strip_thought(text: str) -> str:
    """Remove <thought>...</thought> blocks que Gemma 4 emite antes da resposta."""
    return _THOUGHT_RE.sub("", text).strip()


_RETRY_ATTEMPTS = int(os.getenv("AI_RETRY_ATTEMPTS", "3"))
_RETRY_DELAY_S  = float(os.getenv("AI_RETRY_DELAY_S", "2.0"))

# Modelos tentados em ordem quando 429 no principal
_MODEL_FALLBACK_CHAIN = [
    m.strip() for m in os.getenv(
        "AI_MODEL_FALLBACK_CHAIN",
        "gemma-4-26b-a4b-it,gemma-4-31b-it,gemma-3-27b-it"
    ).split(",") if m.strip()
]


class AIClient:
    """
    Cliente OpenRouter — OpenAI-Compatible.
    Provider: openrouter.ai | Default model: google/gemma-4-26b-a4b-it:free
    Retry automático em 429 (rate limit upstream).
    """

    def __init__(self):
        self.base_url = os.getenv("AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
        self.model = os.getenv("AI_MODEL", "gemma-4-9b-it")
        self.endpoint = f"{self.base_url}/chat/completions"
        # Prioridade: GOOGLE_AI_STUDIO_KEY > OPENROUTER_API_KEY
        self.api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.timeout_seconds = float(os.getenv("AI_TIMEOUT_SECONDS", "30"))

    async def chat_completion(self, messages: List[Dict], tools: List[Dict] = None) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "error",
                "message": {"role": "assistant", "content": "⚠️ Chave AI não configurada. Defina GOOGLE_AI_STUDIO_KEY no .env."},
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        request_id = str(uuid4())

        models_to_try = _MODEL_FALLBACK_CHAIN if self.model in _MODEL_FALLBACK_CHAIN else [self.model] + _MODEL_FALLBACK_CHAIN

        for model in models_to_try:
            payload["model"] = model
            print(f"[AI] id={request_id} model={model} tools={len(tools or [])}")

            for attempt in range(1, _RETRY_ATTEMPTS + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        response = await client.post(self.endpoint, headers=headers, json=payload)

                        if response.status_code == 429:
                            wait = _RETRY_DELAY_S * attempt
                            print(f"[AI] 429 em {model} (tentativa {attempt}/{_RETRY_ATTEMPTS}) — {wait}s")
                            if attempt < _RETRY_ATTEMPTS:
                                await asyncio.sleep(wait)
                                continue
                            # esgotou tentativas neste modelo → tenta próximo
                            print(f"[AI] {model} esgotado, tentando fallback...")
                            break

                        response.raise_for_status()
                        data = response.json()
                        message_obj = data["choices"][0]["message"]

                        # Remove <thought> blocks do Gemma 4
                        if message_obj.get("content"):
                            message_obj["content"] = _strip_thought(message_obj["content"])
                            print(f"[AI] [{model}] {message_obj['content'][:200]}")
                        if message_obj.get("tool_calls"):
                            names = [tc["function"]["name"] for tc in message_obj["tool_calls"]]
                            print(f"[AI] tool_calls: {names}")

                        return {
                            "status": "success",
                            "message": message_obj,
                            "model_used": model,
                            "request_id": request_id,
                        }

                except httpx.HTTPStatusError as e:
                    err_body = e.response.text
                    log.error(f"[AI] HTTP {e.response.status_code} em {model}: {err_body}")
                    break  # erro não-429 → tenta próximo modelo
                except Exception as e:
                    detail = repr(e)
                    log.error(f"[AI] Rede em {model}: {detail}")
                    break

        return {
            "status": "error",
            "message": {
                "role": "assistant",
                "content": "⚠️ Todos os modelos estão sobrecarregados no momento. Tente novamente em alguns segundos.",
            },
            "request_id": request_id,
        }
