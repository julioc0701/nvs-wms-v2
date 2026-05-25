"""Testa extração de linha digitável + beneficiário em uma única chamada.

Estratégia: pedir JSON estruturado, mais fácil de parsear no backend.
"""
import asyncio
import base64
import json
import os
import re
import sys
from io import BytesIO
from PIL import Image
import httpx


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("BOLETO_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

PROMPT_JSON = (
    "Esta imagem é uma foto de um boleto bancário brasileiro. "
    "A foto pode estar rotacionada — analise em todas as direções. "
    "Extraia dois dados:\n"
    "1) A LINHA DIGITÁVEL: sequência de 47 dígitos numéricos consecutivos "
    "(exemplo: 23792.37213 90016.790967 25000.527306 3 14580000058182). "
    "Devolva apenas os 47 dígitos juntos, sem pontos nem espaços.\n"
    "2) O BENEFICIÁRIO (também chamado de 'Cliente'): nome da empresa "
    "para quem o pagamento é feito, escrito abaixo do campo "
    "'Local de Pagamento' / 'Beneficiário'. Exemplo: 'BRF S.A. - CD JUNDIAI'.\n\n"
    "RESPONDA APENAS em JSON válido neste formato exato:\n"
    '{"linha_digitavel": "<47 dígitos ou NAO_ENCONTRADO>", '
    '"beneficiario": "<nome do beneficiário ou NAO_ENCONTRADO>"}\n'
    "Sem texto adicional antes ou depois do JSON."
)


async def chamar_groq(api_key: str, imagem_b64: str, prompt: str) -> dict:
    payload = {
        "model": MODEL,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagem_b64}"}},
                ],
            }
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)
        return {"status_code": resp.status_code, "body": resp.json() if resp.status_code == 200 else resp.text}


def carregar(path: str) -> str:
    img = Image.open(path)
    max_lado = 1600
    if max(img.size) > max_lado:
        e = max_lado / max(img.size)
        img = img.resize((int(img.size[0] * e), int(img.size[1] * e)))
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


async def main():
    if len(sys.argv) < 2:
        print("Uso: python test_groq_beneficiario.py /caminho/foto.jpg")
        sys.exit(1)
    foto_path = sys.argv[1]
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Defina GROQ_API_KEY")
        sys.exit(1)

    print(f"Foto: {foto_path}")
    imagem_b64 = carregar(foto_path)
    resp = await chamar_groq(api_key, imagem_b64, PROMPT_JSON)
    if resp["status_code"] != 200:
        print(f"HTTP {resp['status_code']}: {resp['body'][:300]}")
        return
    content = resp["body"]["choices"][0]["message"]["content"].strip()
    print(f"\nResposta crua:\n{content}\n")

    # Tenta parsear JSON (mesmo se modelo embrulhou em ```)
    bloco = re.search(r"\{.*\}", content, re.DOTALL)
    if not bloco:
        print("Não achei JSON na resposta.")
        return
    try:
        parsed = json.loads(bloco.group(0))
        print(f"linha_digitavel: {parsed.get('linha_digitavel')}")
        print(f"beneficiario:    {parsed.get('beneficiario')}")
    except json.JSONDecodeError as e:
        print(f"JSON inválido: {e}")


if __name__ == "__main__":
    asyncio.run(main())
