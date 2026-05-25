"""Script de teste para diagnosticar a leitura de boleto via Groq Vision.

Uso:
    GROQ_API_KEY=... python scripts/test_groq_vision.py /caminho/foto.jpg

O script testa 3 cenários:
  1. Foto original como está
  2. Foto rotacionada -90° (caso esteja deitada)
  3. Foto rotacionada +90°

Para cada cenário, mostra a resposta crua do modelo.
Útil pra entender por que o NAO_ENCONTRADO vem.

NÃO commita a chave no git. Passa só via env var.
"""
import asyncio
import base64
import os
import sys
from io import BytesIO
from PIL import Image
import httpx


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("BOLETO_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

PROMPT = (
    "Esta imagem é de um boleto bancário brasileiro. "
    "Localize a linha digitável (sequência de 47 dígitos numéricos agrupados "
    "tipo '00000.00000 00000.000000 00000.000000 0 00000000000000') "
    "que aparece impressa acima do código de barras. "
    "Responda APENAS com os 47 dígitos, sem pontos, sem espaços, sem texto adicional. "
    "Se não conseguir identificar com certeza, responda exatamente: NAO_ENCONTRADO."
)

PROMPT_V2 = (
    "Esta imagem é uma foto de um boleto bancário brasileiro. "
    "A foto pode estar rotacionada (deitada, de cabeça pra baixo ou em qualquer ângulo). "
    "Olhe com atenção em todas as direções da imagem e encontre a 'linha digitável' — "
    "uma sequência de 47 dígitos numéricos agrupados (geralmente impressa "
    "acima do código de barras grosso). "
    "Exemplo de formato: 23792.37213 90016.790967 25000.527306 3 14580000058182. "
    "RESPONDA APENAS com os 47 dígitos numéricos consecutivos, sem pontos, sem espaços, sem qualquer outro texto. "
    "Se não conseguir identificar com 100% de certeza, responda exatamente: NAO_ENCONTRADO"
)


async def chamar_groq(api_key: str, imagem_b64: str, prompt: str, model: str) -> dict:
    """Faz a chamada e retorna a resposta crua."""
    payload = {
        "model": model,
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
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)
        return {
            "status_code": resp.status_code,
            "body": resp.json() if resp.status_code == 200 else resp.text,
        }


def carregar_e_rotacionar(path: str, rotacao: int) -> str:
    """Carrega a imagem, rotaciona, retorna base64."""
    img = Image.open(path)
    if rotacao != 0:
        img = img.rotate(rotacao, expand=True)
    # Redimensiona pra max 1600px e salva como JPEG
    max_lado = 1600
    if max(img.size) > max_lado:
        escala = max_lado / max(img.size)
        novo_w = int(img.size[0] * escala)
        novo_h = int(img.size[1] * escala)
        img = img.resize((novo_w, novo_h))
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


async def main():
    if len(sys.argv) < 2:
        print("Uso: python test_groq_vision.py /caminho/foto.jpg")
        sys.exit(1)

    foto_path = sys.argv[1]
    if not os.path.exists(foto_path):
        print(f"Arquivo não encontrado: {foto_path}")
        sys.exit(1)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Defina GROQ_API_KEY no env")
        sys.exit(1)

    print(f"Foto: {foto_path}")
    print(f"Model: {MODEL}\n")

    cenarios = [
        ("Original (sem rotação)", 0, PROMPT),
        ("Rotacionado -90° (anti-horário)", -90, PROMPT),
        ("Rotacionado +90° (horário)", 90, PROMPT),
        ("Original com prompt v2 (rotation-aware)", 0, PROMPT_V2),
        ("Rotacionado -90° com prompt v2", -90, PROMPT_V2),
    ]

    for nome, rotacao, prompt in cenarios:
        print(f"=== {nome} ===")
        try:
            imagem_b64 = carregar_e_rotacionar(foto_path, rotacao)
            resp = await chamar_groq(api_key, imagem_b64, prompt, MODEL)
            if resp["status_code"] != 200:
                print(f"  HTTP {resp['status_code']}: {resp['body'][:300]}")
                continue
            content = resp["body"]["choices"][0]["message"]["content"].strip()
            print(f"  Resposta: {content[:200]}")
            # Conta dígitos
            digitos = "".join(c for c in content if c.isdigit())
            print(f"  Dígitos extraídos: {len(digitos)} → {digitos[:60]}")
        except Exception as e:
            print(f"  ERRO: {e}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
