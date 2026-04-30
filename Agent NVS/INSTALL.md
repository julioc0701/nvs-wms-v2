# INSTALL — Passos Manuais

Comandos que precisam ser executados pelo usuário (requerem auth, slash commands do CC, ou escolhas interativas).

---

## 1. Python env

```bash
cd "C:/Users/julio/OneDrive/Documentos/Antigra/Claude Code/Agent NVS"
python -m venv .venv
.venv\Scripts\activate
rtk pip install -r requirements.txt
```

> Nota: `torch` e `pyiqa` são pesados (~2-3 GB). Para CPU-only:
> `rtk pip install torch --index-url https://download.pytorch.org/whl/cpu`

---

## 2. Plugins Claude Code (oficiais Anthropic — badge verificado)

No terminal do Claude Code:

```
/plugin install brightdata@claude-plugins-official
/plugin install firecrawl@claude-plugins-official
/plugin install intercom@claude-plugins-official
```

---

## 3. Skills de comunidade GitHub

```bash
# Diretório do usuário para skills globais do CC
cd C:/Users/julio/.claude/skills

rtk git clone https://github.com/realkimbarrett/advertising-skills
rtk git clone https://github.com/AgriciDaniel/claude-seo
rtk git clone https://github.com/coreyhaines31/marketingskills
rtk git clone https://github.com/zubair-trabzada/ai-marketing-claude
rtk git clone https://github.com/wshobson/agents wshobson-agents
```

---

## 4. MCPs — Mercado Livre

### 4.1 MCP oficial ML
Editar `~/.claude.json` (Windows: `C:/Users/julio/.claude.json`) adicionar em `mcpServers`:

```json
{
  "mcpServers": {
    "mercadolibre-official": {
      "command": "npx",
      "args": ["-y", "@mercadolibre/mcp-server"],
      "env": {
        "ML_CLIENT_ID": "SEU_CLIENT_ID",
        "ML_CLIENT_SECRET": "SEU_SECRET",
        "ML_REFRESH_TOKEN": "SEU_REFRESH_TOKEN"
      }
    },
    "mercadolibre-reviews": {
      "command": "npx",
      "args": ["-y", "@lumile/mercadolibre-mcp"],
      "env": {}
    },
    "mcp-image-gemini": {
      "command": "npx",
      "args": ["-y", "@shinpr/mcp-image"],
      "env": {
        "GEMINI_API_KEY": "SEU_GEMINI_KEY"
      }
    },
    "mcp-veo2": {
      "command": "npx",
      "args": ["-y", "@mario-andreschak/mcp-veo2"],
      "env": {
        "GOOGLE_API_KEY": "SEU_GOOGLE_KEY"
      }
    }
  }
}
```

### 4.2 Credenciais ML (como obter)

1. Acessar https://developers.mercadolivre.com.br/
2. Criar app → pegar `CLIENT_ID` e `CLIENT_SECRET`
3. Rodar OAuth flow para obter `REFRESH_TOKEN` (válido por 6 meses)
4. Configurar `redirect_uri` do app

---

## 5. Prompt packs (clone local)

```bash
cd "C:/Users/julio/OneDrive/Documentos/Antigra/Claude Code/Agent NVS/vendor"

rtk git clone https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts
rtk git clone https://github.com/ZeroLu/awesome-nanobanana-pro
rtk git clone https://github.com/ComfyAssets/kiko-flux2-prompt-builder
rtk git clone https://github.com/geekjourneyx/awesome-ai-video-prompts
```

---

## 6. Infsh (mantra infsh-first)

```bash
# Verificar apps disponíveis
rtk infsh app list | grep -E "background-removal|nano-banana|google-veo|flux|product-photography|upscaling"

# Login (se necessário)
rtk infsh login
```

Apps confirmados que usaremos:
- `infsh/background-removal`
- `infsh/image-upscaling`
- `infsh/nano-banana-2`
- `infsh/google-veo`
- `infsh/flux-image`
- `infsh/ai-product-photography`

---

## 7. Qdrant (vector DB local para Trilha D)

Opção A — Docker (recomendado):
```bash
docker run -p 6333:6333 -p 6334:6334 -v ./qdrant_storage:/qdrant/storage qdrant/qdrant
```

Opção B — Python embedded (sem Docker):
```bash
rtk pip install qdrant-client[fastembed]
# Usar modo `:memory:` ou path local no código
```

---

## 8. Variáveis de ambiente (.env)

Criar `.env` na raiz do projeto:

```
ML_CLIENT_ID=...
ML_CLIENT_SECRET=...
ML_REFRESH_TOKEN=...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
GOOGLE_API_KEY=...
SHOPEE_PARTNER_ID=...
SHOPEE_PARTNER_KEY=...
```

> `.env` está no `.gitignore` — nunca commitar.

---

## 9. Checklist de Verificação

Após executar todos os passos acima, rodar:

```bash
python src/main.py --check
```

Saída esperada:
```
[OK] Python deps (pyiqa, rembg, bertopic, ...)
[OK] ML MCP connection
[OK] Anthropic API key
[OK] infsh CLI
[OK] Qdrant reachable
[SKIP] Shopee (disabled in settings)
```
