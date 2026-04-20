# USER.md — Julio

## Perfil
- **Nome:** Julio (julioc0701)
- **Papel:** Gestor/desenvolvedor do sistema de armazém da Antigra
- **Contexto:** Brasil, operação de e-commerce com picking de pedidos

## Missão
Manter e evoluir o warehouse-picker v2 — sistema que os operadores do armazém usam no dia a dia para separar pedidos da Olist (Tiny ERP).

## Foco Atual
- Fluxo de separação do Tiny ERP (Opção 2)
- Exibir número do pedido real (não ID interno)
- Performance das chamadas à API Tiny
- UX da tela de bipagem (PickingListDetail)

## Preferências de Trabalho
- Respostas curtas e diretas — sem preambles, sem trailing summaries
- Sem emojis (a menos que pedido)
- Confirmar entendimento antes de executar mudanças grandes
- Mostrar o problema antes de mostrar a solução

## Stack que Julio usa
- Python (FastAPI), React, Tailwind CSS
- SQLite local, Railway em produção
- Tiny ERP API (Olist)
- Claude Code como assistente principal

## Métricas de Sucesso
- Operadores conseguem separar pedidos sem erros de UI
- Número do pedido Olist visível na tela de separação
- Performance: resposta da API Tiny < 3 segundos
- Zero downtime em produção
