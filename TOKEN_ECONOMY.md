# Token Economy (Obrigatório)

## Session Initialization
- Carregar somente contexto essencial:
- `SOUL.md` (quando existir)
- `USER.md` (quando existir)
- `design-tokens.json` (quando existir)
- Nunca carregar `node_modules`, `dist`, `.git`.

## Model Routing
- Modelo padrão: análise/refatoração de baixo risco.
- Modelo de maior capacidade: apenas decisões arquiteturais críticas.

## Batch Processing
- Processar arquivos em lotes (até 10 por bloco).
- Agrupar validações para reduzir custo de contexto.

## Rate Limiting
- 5s entre mudanças pequenas.
- 30s entre refactors grandes.
- Teto recomendado: 100 arquivos/hora.

## Prompt Caching
- Cache permitido: design tokens, templates de componente, padrões de diálogo.
- Não cachear: outputs, diffs, logs sensíveis.

