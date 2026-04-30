# Agente NVS

Agente de análise de anúncios Mercado Livre e Shopee para Novaes / NØR Group.

## Quick Start

```bash
# 1. Setup Python env
python -m venv .venv
.venv\Scripts\activate                  # Windows
rtk pip install -r requirements.txt

# 2. Instalar skills + MCPs (ver INSTALL.md)

# 3. Analisar um MLB
python src/main.py --mlb MLB3661846735
```

## Estrutura

```
Agent NVS/
├── SPEC.md                 Especificação técnica completa
├── INSTALL.md              Passos manuais (MCPs, plugins CC, infsh)
├── README.md               Este arquivo
├── requirements.txt        Deps Python
├── config/
│   ├── settings.yaml       Configuração central
│   └── prompts/            Prompts-mãe por trilha
├── src/
│   ├── main.py             Entry point
│   ├── coleta/             Stage 1 — coleta de dados
│   ├── trilhas/            Stage 2 — 4 trilhas de análise
│   │   ├── descricao/      Trilha A
│   │   ├── fotos/          Trilha B
│   │   ├── objecoes/       Trilha C
│   │   └── concorrentes/   Trilha D
│   └── sintese/            Stage 4 — síntese + export
├── .claude/
│   └── skills/             5 skills próprias NVS
├── data/
│   ├── input/
│   └── output/
└── vendor/                 Prompt packs baixados
```

## Documentação

- [SPEC.md](SPEC.md) — especificação completa do agente
- [INSTALL.md](INSTALL.md) — instruções de instalação de MCPs, plugins e apps infsh

## Mantra ativo

Este projeto roda sempre com economia de token:
- RTK em todo comando bash
- infsh-first para IA externa
- Batch tool calls em paralelo
- Prompt caching Claude API
