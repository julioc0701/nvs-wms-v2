# Agente NVS — Especificação Técnica

**Versão:** 0.1.0
**Data:** 2026-04-17
**Cliente:** Novaes / NØR Group
**Catálogo:** Peças e acessórios de moto (Honda, Yamaha; marcas AWA, WGK, SCUD, DDL, Peels, MT Helmets, Pro Tork, Polimet)

---

## 1. Objetivo

Agente de IA que analisa anúncios do Mercado Livre e Shopee, gerando diagnóstico multidimensional + plano de ação prescritivo + assets prontos (descrição, prompts de imagem/vídeo) no padrão da operação atual da Novaes.

## 2. Gaps do Fluxo Atual que o Agente Resolve

| Gap | Solução |
|---|---|
| Trabalho manual MLB por MLB no GPT NØR | Batch catálogo com priorização automática |
| Sem análise semântica de título | NLP + validador determinístico (60ch, PI_FAKES, COMPATS) |
| Descrição via GPT sem cache → custo OpenAI alto | Prompt caching via Claude API |
| Sem análise de concorrentes | Trilha D dedicada (embeddings + Qdrant) |
| Sem detecção de canibalização (múltiplos MLBs mesmo SKU) | Skill `nvs-canibalizacao-detector` |
| Reviews zerado distorce score geral | Ponderação dinâmica (skip dim se N < threshold) |
| Diagnóstico não prescritivo fora de infração | Síntese gera plano mesmo sem infração ativa |
| Coleta manual (copiar/colar) | MCP oficial ML + MCP comunidade + fallback scraping |

---

## 3. Arquitetura — 4 Trilhas + Síntese

```
ENTRADA: MLB ou lista de MLBs
   │
   ▼
STAGE 1 — COLETA (MCP ML oficial + lumile-mcp)
   • Anúncio (health, tags, status, substatus)
   • Ficha técnica (schema completo da categoria)
   • Imagens (URLs + tags de qualidade)
   • Perguntas, reviews, infrações, histórico preço
   • Reputação vendedor
   │
   ▼
STAGE 2 — ANÁLISE (4 trilhas paralelas)
   ┌─────────────────────────────────────────┐
   │ TRILHA A — Descrição                    │
   │ • claude-seo /seo ecommerce             │
   │ • marketingskills copywriting           │
   │ • guideline-validator (60ch, PI_FAKES)  │
   │ • Detecta keyword stuffing              │
   ├─────────────────────────────────────────┤
   │ TRILHA B — Fotos                        │
   │ • pyiqa (NIMA/MUSIQ/BRISQUE)            │
   │ • rembg (valida fundo branco)           │
   │ • infsh ai-product-photography          │
   │ • nvs-photo-funnel-8 (gera 8 prompts)   │
   ├─────────────────────────────────────────┤
   │ TRILHA C — Objeções                     │
   │ • advertising-skills VoC + Objection-   │
   │   Crusher                               │
   │ • BERTopic (clustering)                 │
   │ • PyABSA (aspecto+sentimento)           │
   │ • ai-rag-pipeline (index histórico)     │
   ├─────────────────────────────────────────┤
   │ TRILHA D — Concorrentes                 │
   │ • sentence-transformers + Qdrant        │
   │ • OpenCLIP (matching visual)            │
   │ • competitor-teardown skill             │
   │ • canibalizacao-detector                │
   └─────────────────────────────────────────┘
   │
   ▼
STAGE 3 — INFRAÇÕES (trilha paralela dedicada)
   • Cruza histórico com tratativa prescrita (10 grupos ML)
   • Prioriza por impacto: PQT > COMPATS > PI_FAKES > …
   │
   ▼
STAGE 4 — SÍNTESE (Sonnet + prompt caching)
   • nvs-scorecard-4eixos (replica Planilha NVS Diagnóstico)
   • nvs-video-sequence-5 (Veo 2 + sequência Clips ML)
   • wshobson/agents orquestra
   │
   ▼
SAÍDA: .xlsx + .md + .json
```

---

## 4. Stack Tecnológica Consolidada

### 4.1 Core Claude Code (obrigatórias — mantra)
- `infsh-cli`, `python-sdk`, `agent-tools` — executor infsh
- `llm-models` — routing Haiku/Sonnet
- `claude-api` — prompt caching
- `python-executor` — sandbox
- `prompt-engineering` — versionamento
- `anthropic-skills:xlsx` — export
- `ai-rag-pipeline` — memória histórica

### 4.2 Skills importadas do GitHub
| Skill | Repo | Trilha |
|---|---|---|
| advertising-skills | realkimbarrett/advertising-skills | C |
| claude-seo | AgriciDaniel/claude-seo | A |
| marketingskills | coreyhaines31/marketingskills | A |
| ai-marketing-claude | zubair-trabzada/ai-marketing-claude | D |
| ABSA | ScalaConsultants/Aspect-Based-Sentiment-Analysis | C |
| wshobson/agents | wshobson/agents | Síntese |
| brightdata (plugin oficial Anthropic) | anthropics/claude-plugins-official | Coleta fallback |
| firecrawl (plugin oficial Anthropic) | anthropics/claude-plugins-official | D |
| intercom (plugin oficial Anthropic) | anthropics/claude-plugins-official | C |

### 4.3 MCPs
| MCP | Repo | Papel |
|---|---|---|
| ML oficial | mercadolibre/mercadolibre-mcp-server | Gateway principal |
| ML reviews | lumile/mercadolibre-mcp | Reviews + reputação |
| Gemini 2-stage | shinpr/mcp-image | Prompts Gemini Pro enriquecidos |
| Veo 2 | mario-andreschak/mcp-veo2 | Vídeos 9:16 5s |

### 4.4 Bibliotecas Python
- `pyiqa` — NIMA, MUSIQ, BRISQUE (qualidade foto)
- `rembg` — fundo branco
- `bertopic` — clustering objeções
- `pyabsa` — aspect-sentiment
- `sentence-transformers` — embeddings texto
- `open-clip-torch` — embeddings imagem
- `qdrant-client` — vector DB
- `openpyxl` — export xlsx

### 4.5 Apps infsh (mantra infsh-first)
- `background-removal`
- `image-upscaling`
- `nano-banana-2` (Gemini)
- `google-veo` (Veo)
- `flux-image`
- `ai-product-photography`

### 4.6 Skills próprias NVS (construídas neste projeto)
| Skill | Papel |
|---|---|
| `nvs-photo-funnel-8` | 8 prompts de imagem cobrindo funil (capa→detalhe→benefício→ajuste→encaixe→estrutura→lifestyle→kit) |
| `nvs-video-sequence-5` | 5 prompts Veo 2 + sequência Clips ML (ex: `[5]→[1]→[3]→[2]→[4]`) |
| `nvs-guideline-validator` | Validador determinístico (60ch título, fundo branco, 95% frame, PI_FAKES, COMPATS) |
| `nvs-canibalizacao-detector` | Detecta SKUs duplicados no catálogo do vendedor |
| `nvs-scorecard-4eixos` | Scorecard 4 eixos compatível com Planilha NVS Diagnóstico |

---

## 5. Formato de Entrada

```yaml
input:
  mlb_id: MLB3661846735        # obrigatório
  mode: single | batch          # single (default) ou batch
  batch_source: csv | api       # se batch, origem da lista
  output_formats: [xlsx, md, json]
  run_trilhas: [A, B, C, D]    # default: todas
```

## 6. Formato de Saída

### 6.1 Scorecard (replica Planilha NVS Diagnóstico)

```yaml
scorecard:
  mlb_id: MLB3661846735
  health_pct: 80.05
  images_pct: 76.13
  specs_pct: 50.31
  reviews_pct: 0.00       # ponderação dinâmica se N < threshold
  general_pct: 66.00
  experience_pct: 57.51
```

### 6.2 Diagnóstico

```yaml
diagnostico:
  trilha_a:
    titulo_atual: "Par Retrovisor Moto Honda Titan Start Fan Cg 125 150 160"
    titulo_atual_chars: 63
    titulo_sugerido: "Par retrovisor moto cg titan fan 125 150 160"
    titulo_sugerido_chars: 55
    aprovado: true
    problemas: ["Ultrapassa 60 caracteres", "Termos fora do padrão de busca"]
    keyword_stuffing_detected: false
    pi_fakes_risk: false
  trilha_b:
    nima_score: 7.2
    fundo_branco: false
    produto_95_frame: true
    resolucao: "1200x1200"
    infracao_pqt_risk: medium
  trilha_c:
    objecoes: [...]            # 8 objeções
    pontos_fortes: [...]       # 8 pontos
    aspect_sentiment: {...}
  trilha_d:
    top_concorrentes: [...]    # top 10
    delta_preco: -12.5
    canibalizacao_detectada: false
```

### 6.3 Assets prontos
- Título otimizado
- Descrição completa (copy pronta, formato NØR com `━━━`)
- 8 prompts de imagem (Gemini Pro, 3:4, Canon EOS R5, 85mm, f/2.8)
- 5 prompts de vídeo (Veo 2, 9:16, 5s, no CGI)
- Sequência de montagem Clips ML

### 6.4 Plano de ação
- Priorizado por impacto × esforço
- Inclui tratativa de cada infração ativa
- Deadline sugerido

---

## 7. Metodologia de Scoring (replica planilha NVS Diagnóstico)

- **Saúde** = `health` direto da API ML
- **Imagens** = média ponderada de tags `good_quality_picture` + pyiqa NIMA
- **Specs** = Σ(atributos preenchidos × peso_relevancia) / Σ(total × peso)
  - Pesos: Obrigatório=3, Relevante=2, Oculto=2, Comum=2 (compatível Planilha Ficha Técnica 2.0)
- **Reviews** = média nota × log(N+1) — ponderação por volume
- **Geral** = média simples de 4 eixos (skip se eixo N<threshold)
- **Experience** = 1 - (claims_rate + delayed_rate + canceled_rate) / 3

---

## 8. Mantra — Economia de Token (sempre ativo)

- RTK em todo comando bash
- infsh-first para IA externa (não MCP verboso)
- Model routing: Haiku (leitura/busca) / Sonnet (síntese/análise)
- Batch tool calls em paralelo
- Prompt caching obrigatório via claude-api
- Session lean (não carregar node_modules, dist, .git)
- CLAUDE.md estável (não editar mid-session)

---

## 9. Fases de Entrega

| Fase | Escopo | Status |
|---|---|---|
| 0 | Scaffold + SPEC + Skills próprias | Em execução |
| 1 | MVP Trilha B (fotos) — pyiqa + rembg em 1 MLB | Próximo |
| 2 | Coleta ML (MCPs) + Trilha C (objeções) | Planejada |
| 3 | Trilha A (descrição) + Trilha D (concorrentes) | Planejada |
| 4 | Síntese + Export xlsx | Planejada |
| 5 | Batch catálogo + Agendamento | Futuro |

---

## 10. Riscos Conhecidos

| Risco | Mitigação |
|---|---|
| Ban de conta por scraping ML/Shopee | Usar exclusivamente API oficial + brightdata plugin verificado |
| Custo de LLM sem cache | Prompt caching em 100% das chamadas LLM |
| Skills comunidade com supply-chain risk | Instalar apenas plugins com badge "Anthropic Verified" + repos MIT/Apache com >500 stars + SECURITY.md |
| Modelo IQA treinado fora do domínio (AVA vs peças de moto) | Fine-tune posterior com catálogo Novaes ou fallback em tags API ML |
| Gap brasileiro de ferramentas pt-BR | Construir próprio → publicar como skill pack NVS no futuro |
