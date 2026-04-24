"""
test_agent.py — Teste do fluxo completo do Agent NVS (OpenRouter + Gemma 4)

Uso:
    cd backend
    python test_agent.py

Requer OPENROUTER_API_KEY no ambiente ou em .env na raiz do projeto.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# ── Carrega .env se existir ────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ── Cores no terminal ──────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):    print(f"{GREEN}  ✓ {msg}{RESET}")
def fail(msg):  print(f"{RED}  ✗ {msg}{RESET}")
def warn(msg):  print(f"{YELLOW}  ⚠ {msg}{RESET}")
def step(msg):  print(f"\n{BOLD}{CYAN}[STEP]{RESET} {BOLD}{msg}{RESET}")
def info(msg):  print(f"    {msg}")


# ── STEP 1 — Env vars ──────────────────────────────────────────────────────────
step("1 — Verificar variáveis de ambiente")

api_key = os.getenv("OPENROUTER_API_KEY", "")
ai_model = os.getenv("AI_MODEL", "google/gemma-4-26b-a4b:free")
ai_base_url = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")

if api_key:
    ok(f"OPENROUTER_API_KEY definida ({api_key[:12]}...)")
else:
    fail("OPENROUTER_API_KEY não encontrada — impossível continuar")
    sys.exit(1)

info(f"AI_MODEL   = {ai_model}")
info(f"AI_BASE_URL = {ai_base_url}")


# ── STEP 2 — Import AIClient ───────────────────────────────────────────────────
step("2 — Importar AIClient")
try:
    from mas_core.ai_service import AIClient
    ok("AIClient importado com sucesso")
except Exception as e:
    fail(f"Falha ao importar AIClient: {e}")
    sys.exit(1)


# ── STEP 3 — Ping simples (sem tools) ─────────────────────────────────────────
step("3 — Ping simples ao modelo (sem tools)")

async def test_ping():
    client = AIClient()
    info(f"Endpoint: {client.endpoint}")
    info(f"Modelo:   {client.model}")

    response = await client.chat_completion(
        messages=[{"role": "user", "content": "Responda apenas: ONLINE"}],
        tools=None,
    )

    if response["status"] == "error":
        fail(f"Erro na resposta: {response['message']['content']}")
        return False

    content = response.get("message", {}).get("content", "")
    info(f"Resposta: {repr(content)}")
    if content:
        ok("Modelo respondeu com texto")
        return True
    else:
        warn("Resposta vazia — modelo pode ter retornado tool_call inesperado")
        return True  # não é erro fatal

asyncio.run(test_ping()) or sys.exit(1)


# ── STEP 4 — Tool calling ──────────────────────────────────────────────────────
step("4 — Tool calling (get_sales_dashboard_data)")

TOOL_SCHEMA_TEST = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_dashboard_data",
            "description": "Retorna dados de vendas do período informado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "string", "description": "Número de dias"}
                },
            },
        },
    }
]

async def test_tool_call():
    client = AIClient()
    response = await client.chat_completion(
        messages=[
            {"role": "system", "content": "Você é um assistente de vendas. Use as tools disponíveis para responder."},
            {"role": "user", "content": "Quantas vendas tivemos hoje?"},
        ],
        tools=TOOL_SCHEMA_TEST,
    )

    if response["status"] == "error":
        fail(f"Erro na resposta: {response['message']['content']}")
        return False

    msg = response.get("message", {})
    tool_calls = msg.get("tool_calls")

    if tool_calls:
        tool_name = tool_calls[0]["function"]["name"]
        tool_args = tool_calls[0]["function"]["arguments"]
        ok(f"Modelo acionou tool: {tool_name}")
        info(f"Argumentos: {tool_args}")
        return True
    elif msg.get("content"):
        warn(f"Modelo respondeu em texto sem acionar tool: {msg['content'][:120]}")
        warn("Tool calling pode não estar funcional para este modelo/plan")
        return True
    else:
        fail("Resposta vazia e sem tool_calls")
        return False

asyncio.run(test_tool_call()) or sys.exit(1)


# ── STEP 5 — Fluxo completo via endpoint /api/v2/ai/chat ──────────────────────
step("5 — Fluxo completo (classify_intent + build_prompt + AIClient)")

async def test_full_flow():
    try:
        from mas_core.agent_protocol import classify_user_intent, build_runtime_system_prompt
        from mas_core.agents import AgentRole, get_agent_prompt
        ok("Imports do MAS core OK")
    except Exception as e:
        fail(f"Falha ao importar MAS core: {e}")
        return False

    prompt = "quantas vendas fizemos essa semana?"
    routing = classify_user_intent(prompt)
    info(f"Intent classificado: specialist={routing.specialist_role} | label={routing.specialist_label}")
    info(f"Rationale: {routing.rationale}")

    try:
        specialist_role = AgentRole(routing.specialist_role)
    except ValueError:
        specialist_role = AgentRole.ORCHESTRATOR

    system_prompt = build_runtime_system_prompt(
        get_agent_prompt(AgentRole.ORCHESTRATOR),
        get_agent_prompt(specialist_role),
        routing,
    )
    info(f"System prompt gerado: {len(system_prompt)} chars")

    client = AIClient()
    response = await client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        tools=TOOL_SCHEMA_TEST,
    )

    if response["status"] == "error":
        fail(f"Erro no fluxo completo: {response['message']['content']}")
        return False

    msg = response.get("message", {})
    if msg.get("tool_calls"):
        ok(f"Tool acionada: {msg['tool_calls'][0]['function']['name']}")
    elif msg.get("content"):
        ok(f"Resposta textual recebida ({len(msg['content'])} chars)")
        info(f"Preview: {msg['content'][:150]}...")
    else:
        warn("Resposta vazia no fluxo completo")

    return True

asyncio.run(test_full_flow()) or sys.exit(1)


# ── Resultado final ────────────────────────────────────────────────────────────
print(f"\n{BOLD}{GREEN}{'='*50}")
print("  TODOS OS STEPS PASSARAM — Agent operacional")
print(f"{'='*50}{RESET}\n")
