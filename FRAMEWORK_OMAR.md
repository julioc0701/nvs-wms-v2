# Framework Omar (Isolado)

## Objetivo
Executar auditoria + implementação por fases sem risco de tocar Antigravity.

## Comandos
- `nvs-code dev`
- `nvs-code audit`
- `nvs-code phase:1`
- `nvs-code phase:2`
- `nvs-code phase:3`

## Contrato de isolamento
- Frontend roda em `5174` (ou `VITE_PORT`).
- Backend roda em `8001` (ou `FASTAPI_PORT`).
- Banco isolado em `./data/code-isolated.db`.
- Não usar import/caminho cruzado para projeto Antigravity.

## Fases
1. Design System + TypeScript (fundação).
2. UX Patterns + Toast + Skeleton (impacto visual-operacional).
3. A11y + Performance + qualidade (hardening).

