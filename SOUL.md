# SOUL.md — warehouse-picker v2

## Missão
Sistema de gestão de separação de pedidos para o armazém da Antigra. Integra com Tiny ERP (Olist) para buscar separações, consolidar picking lists e registrar execução em tempo real pelos operadores.

## Princípios Operacionais

### 1. CLI-First (Método Omar)
Quando precisar de capacidades de IA externas (imagem, vídeo, LLM, busca web, áudio):
- **Usar `infsh` CLI primeiro** — respostas curtas, contexto preservado
- **Evitar MCPs verbosos** — JSON gigante incha o contexto e degrada performance
- Verificar apps disponíveis: `infsh app list | grep <keyword>`

### 2. RTK Obrigatório
Todo comando bash deve usar prefixo `rtk`:
- `rtk git status`, `rtk git diff`, `rtk git log`
- `rtk ls <path>`, `rtk grep <pattern>`
- `rtk npm run <script>`, `rtk pip install`
- Mesmo em chains: `rtk git add . && rtk git commit -m "msg"`

### 3. Model Routing
| Tarefa | Modelo |
|---|---|
| Leitura, busca, edição simples, grep | Haiku |
| Debug complexo, arquitetura, segurança, multi-step | Sonnet |
| Decisões críticas de produção | Sonnet |

### 4. Session Initialization (Token Economy)
Carregar apenas: `SOUL.md`, `USER.md`, arquivo de memória do dia (`memory/YYYY-MM-DD.md` se existir).
Nunca carregar: `node_modules`, `dist`, `.git`, histórico completo de sessões.

### 5. Rate Limiting
- 5s mínimo entre chamadas API externas
- Batchear trabalho similar (1 chamada para 10 itens, não 10 chamadas)
- Se erro 429/35 (Tiny rate limit): parar, aguardar 5 minutos, retry

### 6. Prompt Caching
- Manter `SOUL.md` e `USER.md` estáveis durante a sessão (não editar mid-session)
- Mudanças nestes arquivos só em janelas de manutenção

## Stack do Projeto
- **Backend:** FastAPI (Python), SQLite, SQLAlchemy
- **Frontend:** React + Vite, Tailwind CSS
- **Integração:** Tiny ERP API v2 (Olist), `httpx` async
- **AI:** `/v2/ai/chat` endpoint (Groq/Claude)
- **Deploy:** Railway (produção), local dev em portas 8001/5174

## Regras de Código
- Sem mock de banco de dados em testes
- Sem error handling para cenários impossíveis
- Sem abstrações para uso único
- Sem comentários óbvios — só onde lógica não é autoexplicativa
- Respostas concisas, sem trailing summaries

## infsh Apps Relevantes para este Projeto
```bash
# Busca web (pesquisa de produto, SKU, info de mercado)
infsh app run tavily/search-assistant --input '{"query": "..."}'

# Remoção de fundo de fotos de produto
infsh app run rembg/background-removal --input '{"image_url": "..."}'

# LLM alternativo (quando Groq estiver lento)
infsh app run openrouter/claude-haiku-45 --input '{"prompt": "..."}'

# TTS para picking por voz (futuro)
infsh app run elevenlabs/tts --input '{"text": "...", "voice_id": "..."}'
```
