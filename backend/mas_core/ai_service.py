import httpx
import os
import logging
from typing import Dict, Any, List
from uuid import uuid4

log = logging.getLogger(__name__)

class AIClient:
    """
    Cliente Oficial da Era na Nuvem (Groq API).
    Velocidade Extrema, 0 gargalos na CPU local. Arquitetura OpenAI-Compatible.
    """
    
    def __init__(self):
        # Migração Estratégica: Pulando do hardware local e entrando na Nuvem Oficial da Groq.
        self.base_url = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
        # Groq aposentou o gemma2-9b-it. Atualizado para o monstruoso e ultrarrápido Llama 3.3 de 70B!
        self.model = os.getenv("AI_MODEL", "llama-3.3-70b-versatile") 
        self.endpoint = f"{self.base_url}/chat/completions"
        self.api_key = os.getenv("GROQ_API_KEY")
        self.timeout_seconds = float(os.getenv("AI_TIMEOUT_SECONDS", "25"))

    async def chat_completion(self, messages: List[Dict], tools: List[Dict] = None) -> Dict[str, Any]:
        """
        Gemma 2 9B rodando no Cluster Groq. (Latência Zero)
        """
        
        if not self.api_key:
             return {
                 "status": "error",
                 "message": {"role": "assistant", "content": "⚠️ Chave de API da Groq ausente! Coloque a `GROQ_API_KEY` no seu arquivo .env para ativar meu cérebro na nuvem."}
             }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0
        }

        # Sub-Agentes LIGADOS! Groq processa function calling da forma nativa que a OpenAI ensinou.
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        request_id = str(uuid4())
        print(f"[☁️ GROQ AI] request_id={request_id} model={self.model} tools={len(tools or [])}")

        try:
            # Tempo de espera baixou drasticamente porque Groq cospe o resultado instantaneamente
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                # A API compatível com OpenAI cospe o resultado dentro do array 'choices'
                message_obj = data["choices"][0]["message"]
                
                if message_obj.get('content'):
                    print(f"[☁️ GROQ] Log de Raciocínio: \n>>> {message_obj.get('content', '')}")
                
                if message_obj.get("tool_calls"):
                    print(f"⚠️ [☁️ GROQ] O Modelo ativou habilidades especiais: {message_obj['tool_calls']}")

                return {
                    "status": "success",
                    "message": message_obj,
                    "model_used": self.model,
                    "request_id": request_id,
                }
                
        except httpx.HTTPStatusError as e:
            err_body = e.response.text
            log.error(f"[☁️ GROQ] Erro de Servidor HTTP {e.response.status_code}: {err_body}")
            return {
                "status": "error",
                "message": {"role": "assistant", "content": f"Groq rejeitou a payload: {err_body}"},
                "request_id": request_id,
            }
        except Exception as e:
            error_details = repr(e)
            log.error(f"[☁️ GROQ] Erro na Rede Fio Navalha: {error_details}")
            return {
                "status": "error",
                "message": {"role": "assistant", "content": f"Groq Offline/Corda Cortada: {error_details}"},
                "request_id": request_id,
            }
