# Agent de Análise de Anúncio
### NVS Agent — Documentação do Projeto
**Cliente:** Novaes / NØR Group
**Data de início:** Abril 2026
**Status atual:** Operacional (aguardando token Mercado Livre para testes em produção)

---

## 1. O Problema

A Novaes opera um catálogo de peças e acessórios de moto no Mercado Livre (marcas AWA, WGK, SCUD, DDL, Peels, MT Helmets, Pro Tork, Polimet, entre outras). O processo de análise e otimização dos anúncios era feito manualmente — um anúncio por vez — usando um GPT customizado da NØR Group no ChatGPT.

Esse processo tinha limitações sérias:

| Limitação | Impacto |
|---|---|
| Análise manual, MLB por MLB | Escala impossível para catálogos grandes |
| Sem análise de fotos (qualidade técnica) | Infrações de PQT passavam despercebidas |
| Sem análise de concorrentes | Gaps de posicionamento não identificados |
| Sem detecção de canibalização | Múltiplos MLBs do mesmo SKU fragmentando tráfego |
| Reviews zerados distorciam o score | Anúncios novos pareciam ruins sem motivo |
| Custo alto com GPT sem cache | Cada análise custava mais do que precisava |
| Output manual, sem padrão fixo | Difícil reproduzir ou escalar para equipe |

---

## 2. A Solução — O NVS Agent

Um agente de IA construído com Claude Code que analisa anúncios do Mercado Livre de forma automática, gerando:

1. **Diagnóstico multidimensional** (4 eixos: saúde, imagens, ficha técnica, reviews)
2. **Conteúdo otimizado pronto para usar** (título, descrição, prompts de imagem e vídeo)
3. **Plano de ação prescritivo** com priorização por impacto

O agente substitui o trabalho manual do GPT NØR com uma pipeline automatizada, auditável e escalável.

---

## 3. Arquitetura — Como Funciona

O agente opera em 4 estágios encadeados:

```
ENTRADA: ID do anúncio (MLB...)
    │
    ▼
ESTÁGIO 1 — COLETA
    Busca todos os dados do anúncio via API Mercado Livre:
    título, descrição, fotos, ficha técnica, reviews,
    perguntas, saúde (health), infrações ativas
    │
    ▼
ESTÁGIO 2 — ANÁLISE (4 trilhas rodando em paralelo)
    ┌──────────────────────────────────────────┐
    │ TRILHA A — Descrição                     │
    │   Analisa título (60 chars, PI_FAKES,    │
    │   keyword stuffing) e descrição          │
    │   (links proibidos, estrutura mínima)    │
    ├──────────────────────────────────────────┤
    │ TRILHA B — Fotos                         │
    │   Analisa qualidade técnica via IA       │
    │   (NIMA score), valida fundo branco,     │
    │   detecta violações PQT                  │
    ├──────────────────────────────────────────┤
    │ TRILHA C — Objeções                      │
    │   Minera reviews e perguntas para        │
    │   mapear objeções reais dos compradores  │
    │   e pontos fortes do produto             │
    ├──────────────────────────────────────────┤
    │ TRILHA D — Concorrentes                  │
    │   Analisa top concorrentes da categoria, │
    │   percentil de preço, keywords faltando  │
    └──────────────────────────────────────────┘
    │
    ▼
ESTÁGIO 3 — SCORECARD
    Calcula score de 0-100 para cada eixo,
    replica exatamente a Planilha NVS Diagnóstico
    │
    ▼
ESTÁGIO 4 — GERAÇÃO LLM (Claude Sonnet)
    Gera título otimizado, descrição completa,
    8 prompts de imagem, 5 prompts de vídeo
    │
    ▼
SAÍDA: Relatório 7 blocos NØR
```

---

## 4. O que Foi Construído

### 4.1 Skills Claude Code (5 skills proprietárias)

Skills são módulos reutilizáveis que encapsulam lógica especializada. Foram criadas 5 skills exclusivas para o projeto NVS:

| Skill | O que faz |
|---|---|
| `nvs-scorecard-4eixos` | Replica as fórmulas exatas da Planilha NVS Diagnóstico. Calcula health, imagens, ficha técnica e reviews com ponderação dinâmica (ignora reviews se N < 5 para não distorcer anúncios novos) |
| `nvs-guideline-validator` | Validador determinístico das regras do Mercado Livre — 60 chars no título, PI_FAKES, fundo branco nas fotos, atributos obrigatórios, COMPATS para peças |
| `nvs-photo-funnel-8` | Gera 8 prompts de imagem cobrindo o funil completo de compra: capa → detalhe → benefício → ajuste → encaixe → estrutura → lifestyle → kit |
| `nvs-video-sequence-5` | Gera 5 prompts de vídeo para Google Veo 2 (9:16 vertical, 5 segundos, sem texto) + sequência de montagem otimizada para Clips ML |
| `nvs-canibalizacao-detector` | Detecta quando o mesmo produto está em múltiplos anúncios do vendedor, fragmentando tráfego. Recomenda consolidar ou diferenciar |

### 4.2 Código Python (src/)

O núcleo do agente são módulos Python organizados por responsabilidade:

**Coleta de dados:**
- `src/coleta/ml_client.py` — Wrapper da API oficial do Mercado Livre. Coleta tudo em uma chamada: título, descrição, fotos, ficha técnica, reviews, perguntas, health, infrações ativas

**Análise (4 trilhas):**
- `src/trilhas/fotos/analyzer.py` — Trilha B: analisa cada foto com IA (NIMA score via pyiqa), valida fundo branco (análise de pixels), detecta violações PQT, identifica lacunas no funil de imagens
- `src/trilhas/descricao/analyzer.py` — Trilha A: detecta automaticamente PI_FAKES, excesso de caracteres, keyword stuffing, links proibidos
- `src/trilhas/objecoes/analyzer.py` — Trilha C: minera reviews e perguntas, agrupa por tema (compatibilidade, qualidade, instalação, prazo...), gera tratativas automáticas
- `src/trilhas/concorrentes/analyzer.py` — Trilha D: busca top concorrentes da categoria, calcula percentil de preço, identifica keywords faltando

**Scoring:**
- `src/scoring/scorecard.py` — Implementação exata das fórmulas da Planilha NVS Diagnóstico

**Geração LLM:**
- `src/llm/client.py` — Wrapper Anthropic com roteamento de modelos (Haiku para tarefas rápidas, Sonnet para geração criativa)
- `src/llm/gerador.py` — Gera título otimizado, descrição estruturada, 8 prompts de imagem e 5 prompts de vídeo

**Orquestração:**
- `src/sintese/orchestrator.py` — Coordena todas as trilhas e produz o relatório final

### 4.3 Prompts-Mãe (config/prompts/)

6 arquivos que definem o comportamento do agente em cada etapa:
- `orchestrator.md` — Regras gerais e roteamento de modelos
- `trilha_a_descricao.md` — Análise e geração de título/descrição
- `trilha_b_fotos.md` — Pipeline de análise de imagens
- `trilha_c_objecoes.md` — Mineração e tratamento de objeções
- `trilha_d_concorrentes.md` — Análise competitiva
- `sintese.md` — Formato dos 7 blocos NØR de output

### 4.4 Infraestrutura

- **Python 3.13** com ambiente virtual isolado (`.venv`)
- **pyiqa 0.1.15** — biblioteca de métricas de qualidade de imagem por IA (NIMA, BRISQUE)
- **rembg[cpu] 2.0.75** — remoção de fundo (validação de fundo branco)
- **PyTorch CPU** — backend dos modelos de análise de imagem
- **anthropic SDK** — integração com Claude API

---

## 5. Os Desafios Enfrentados

### 5.1 Encoding Windows (cp1252)
**Problema:** O terminal Windows não aceita emojis e caracteres Unicode (✓ ✗ ─ ━). Todo script que tentava imprimir esses símbolos travava com `UnicodeEncodeError`.

**Solução:** Dois caminhos conforme o caso — (1) substituir por ASCII puro nos prints de terminal (`[OK]` em vez de `✓`, `--` em vez de `─`), e (2) adicionar `sys.stdout.reconfigure(encoding="utf-8")` nos scripts que precisam exibir o output rico gerado pelo LLM (que naturalmente usa emojis).

### 5.2 Instalação simultânea de dependências
**Problema:** Ao tentar instalar dois pacotes em paralelo no mesmo `.venv`, o Windows travava com `WinError 32` (arquivo em uso por outro processo), corrompendo a instalação.

**Solução:** Nunca rodar dois `pip install` ao mesmo tempo. Aguardar sempre o término completo de uma instalação antes de iniciar a próxima.

### 5.3 Dependências encadeadas (pyiqa → torchvision → transformers)
**Problema:** O `pyiqa` tem uma cadeia de dependências pesadas que não são instaladas automaticamente: precisa de `torchvision`, que precisa de `torch`, que precisa de `transformers`. Instalar apenas `pyiqa` resulta em `ModuleNotFoundError` em cascata.

**Solução:** Instalar na ordem correta: primeiro `torch + torchvision` via PyTorch CPU index (evita baixar a versão CUDA, que é 3x maior), depois `transformers`, depois `pyiqa`.

### 5.4 rembg sem backend
**Problema:** O `rembg` instalado sem extras não funciona — exige `onnxruntime` explicitamente. A mensagem de erro era confusa: "No onnxruntime backend found".

**Solução:** Instalar com o extra correto: `pip install "rembg[cpu]"` que inclui o `onnxruntime-cpu` automaticamente.

### 5.5 Parser de prompts gerados pelo LLM
**Problema:** O Claude Sonnet não retorna os prompts sempre no mesmo formato — às vezes usa `**IMAGEM 1**` (com markdown bold), às vezes `IMAGEM 1 -`, às vezes adiciona `#` antes. O parser inicial que procurava prefixo exato `"VIDEO "` não encontrava os blocos de vídeo.

**Solução:** Reescrever o parser para ser tolerante a variações — remove `*` e `#` antes de comparar, aceita tanto `:` quanto `-` após o número, e captura texto multi-linha para o campo `prompt`.

### 5.6 Créditos Anthropic em workspace errada
**Problema:** A primeira chave de API fornecida retornava erro `credit balance too low` mesmo após o usuário ter adicionado créditos ($9). Os créditos foram adicionados em uma workspace diferente da que gerou a chave.

**Solução:** Gerar uma nova chave diretamente na mesma conta/workspace onde os créditos foram adicionados em [console.anthropic.com/settings/api-keys](https://console.anthropic.com/settings/api-keys).

---

## 6. O que Já Funciona — Validado ao Vivo

O agente foi testado de ponta a ponta com dados reais do produto **Par Retrovisor Honda CG Titan Fan Start** (MLB3661846735), usando dados mockados extraídos da análise anterior do GPT NØR.

### Resultado do teste:

**Scorecard calculado:**
```
Saúde ML       72.0%
Imagens (PQT)  77.1%
Ficha Técnica  48.4%   ← gap crítico identificado
Reviews        54.4%
──────────────────────
GERAL          63.0%   [BOM]
Experience     97.3%
```

**Título otimizado (Claude Sonnet):**
```
ANTES:  Par Retrovisor Espelho Honda CG Titan Fan Start 150 160  (55 chars)
        ⚠ Violação PI_FAKES: "Honda" sem "para" ou "compatível com"

DEPOIS: Par Retrovisor para Honda CG Titan Fan Start 150 160     (52 chars)
        ✓ PI_FAKES resolvido, dentro dos 60 chars
```

**Descrição gerada:** 5 seções estruturadas (hook → compatibilidade com lista ✔/✗ → specs técnicas → kit → garantia), tratando a objeção principal mapeada nos reviews (compatibilidade, mencionada por 35% dos compradores).

**8 prompts de imagem gerados:** todos em inglês, com especificações Canon EOS R5 85mm f/2.8, formato 3:4, sem CGI — cobrindo o funil completo de capa a kit.

**5 prompts de vídeo gerados:** formato 9:16 vertical, 5 segundos, para Google Veo 2 — slow motion, uso real, ajuste, detalhe premium e reveal orbital.

**15 testes automatizados passando:**
- Scorecard 4 Eixos: 6/6
- Trilha A (Descrição): 4/4
- Trilha B (Fotos): 5/5

---

## 7. Estrutura de Arquivos do Projeto

```
Agent NVS/
├── .claude/
│   └── skills/                    ← 5 skills proprietárias NVS
│       ├── nvs-scorecard-4eixos/
│       ├── nvs-guideline-validator/
│       ├── nvs-photo-funnel-8/
│       ├── nvs-video-sequence-5/
│       └── nvs-canibalizacao-detector/
├── config/
│   ├── settings.yaml              ← Configurações globais (modelos, pesos, thresholds)
│   └── prompts/                   ← 6 prompts-mãe das trilhas
├── src/
│   ├── main.py                    ← Entry point
│   ├── coleta/ml_client.py        ← Wrapper API Mercado Livre
│   ├── scoring/scorecard.py       ← Scorecard 4 Eixos
│   ├── trilhas/
│   │   ├── fotos/analyzer.py      ← Trilha B (pyiqa + PIL)
│   │   ├── descricao/analyzer.py  ← Trilha A
│   │   ├── objecoes/analyzer.py   ← Trilha C
│   │   └── concorrentes/analyzer.py ← Trilha D
│   ├── llm/
│   │   ├── client.py              ← Wrapper Anthropic (Haiku/Sonnet)
│   │   └── gerador.py             ← Geração de título, descrição, prompts
│   └── sintese/orchestrator.py    ← Orquestrador geral
├── tests/
│   ├── test_scorecard.py          ← 6/6 ✓
│   ├── test_trilha_a.py           ← 4/4 ✓
│   ├── test_trilha_b_smoke.py     ← 5/5 ✓
│   └── test_e2e_retrovisor.py     ← Teste ponta a ponta ✓
├── data/input/                    ← Dados de entrada (gitignored)
├── data/output/                   ← Relatórios gerados (gitignored)
├── .env                           ← Chaves de API (gitignored)
├── SPEC.md                        ← Especificação técnica completa
├── INSTALL.md                     ← Guia de instalação e setup
└── STATUS.md                      ← Estado atual + próximos passos
```

---

## 8. Chaves e Integrações

| Serviço | Status | Observação |
|---|---|---|
| Anthropic API (Claude) | ✅ Ativa | Créditos $9 carregados, conta julioc0701@gmail.com |
| Mercado Livre API | ⏳ Pendente | Token OAuth ainda não gerado |
| Google Veo 2 | 📋 Planejado | Via infsh `google-veo` ou MCP `mario-andreschak/mcp-veo2` |
| Gemini (imagens) | 📋 Planejado | Via infsh `nano-banana-2` |

---

## 9. O que Falta para Produção Completa

### Próxima sessão (alta prioridade)

1. **Token Mercado Livre**
   - Acessar [developers.mercadolivre.com.br](https://developers.mercadolivre.com.br)
   - Criar App, gerar App ID + Client Secret
   - Trocar pelo access_token via OAuth
   - Salvar em `.env` → `ML_ACCESS_TOKEN=APP_USR-...`
   - Rodar: `python src/main.py MLB3661846735`

2. **Primeiro teste com anúncio real**
   - Comparar output real vs. mock do retrovisor
   - Validar se os dados da API batem com o esperado

3. **Export .xlsx**
   - Gerar relatório compatível com a Planilha NVS Diagnóstico atual
   - Usar `openpyxl` já instalado

### Próximas semanas

4. **BERTopic** — Instalar para clustering avançado de objeções (hoje usa heurística de palavras-chave)
5. **Refresh automático do token ML** — Token expira em 6h; implementar renovação automática
6. **Análise visual de fotos real** — Usar `rembg` de fato para validar fundo branco (hoje usa heurística de pixels de borda)

### Futuro (roadmap)

- Integração Shopee API
- Interface web ou dashboard visual
- Qdrant + sentence-transformers para Trilha D (busca semântica de concorrentes)
- Batch: analisar catálogo inteiro de uma vez com priorização automática
- Fine-tune do modelo NIMA com fotos do catálogo Novaes (mais preciso que modelo genérico)

---

## 10. Como Rodar (quando tiver o token ML)

```bash
# 1. Ativar ambiente
cd "C:\Users\julio\OneDrive\Documentos\Antigra\Claude Code\Agent NVS"
.venv\Scripts\activate

# 2. Verificar dependências
python src/main.py --check

# 3. Analisar um anúncio
set ML_ACCESS_TOKEN=APP_USR-...
python src/main.py MLB3661846735

# 4. Só análise de fotos
python src/main.py MLB3661846735 --only-trilha B

# 5. Teste ponta a ponta sem token (dados mockados)
python tests/test_e2e_retrovisor.py
```

---

## 11. Princípios do Projeto

**MANTRA — protocolo de economia de tokens (sempre ativo):**
- `rtk` em todos os comandos bash
- Roteamento de modelos: Haiku para tarefas rápidas, Sonnet para geração criativa
- Prompt caching obrigatório nas chamadas LLM
- Batch de tool calls em paralelo sempre que possível
- Nunca rodar dois `pip install` simultâneos no Windows

**Segurança:**
- Chaves de API salvas apenas em `.env` (gitignored, nunca commitado)
- Usar exclusivamente API oficial ML (sem scraping) para não arriscar ban de conta
- Skills de terceiros: apenas repositórios MIT/Apache com >500 stars e SECURITY.md

---

*Documento gerado em 2026-04-19 | Projeto NVS Agent v0.1.0*
