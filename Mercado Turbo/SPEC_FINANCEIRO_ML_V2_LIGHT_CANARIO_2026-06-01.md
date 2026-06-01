# SPEC — Financeiro ML V2 Light — Canario de Ingestao

Data: 2026-06-01
Status: aprovado para implementacao tecnica local, sem rodar producao sem etapa explicita.

## Objetivo funcional

Provar em producao, com risco controlado, que o problema nao esta na busca por data do Mercado Livre. O problema esta no enriquecimento acelerado dos dados faltantes, principalmente frete vendedor via `shipments`.

A V2 Light mantem a experiencia funcional:

1. Usuario escolhe uma data.
2. Sistema busca pedidos do dia via `/orders/search`.
3. Sistema salva a base recebida.
4. Sistema marca o que falta.
5. Fila lenta completa as pendencias depois.

## Decisao da mesa

Comecar por:

`/orders/search por data -> salvar base -> criar pendencias -> enriquecer devagar`

Nao comecar por Postgres, SQS real ou billing como motor principal.

Billing continua como camada posterior de conciliacao/auditoria.

## O que muda contra o fluxo atual

Hoje o worker tenta buscar o dia e completar todos os pedidos na mesma execucao. Isso transforma uma busca funcional por data em muitas chamadas sequenciais para `/shipments` e `/shipments/{id}/costs`.

Na V2 Light, a busca por data termina cedo e grava o que ja veio. O que falta vira pendencia.

## Canario 1 — base por data

Escopo:

- 1 seller.
- 1 dia.
- Chamar apenas `/orders/search`.
- Nao chamar `/shipments`.
- Nao chamar `/shipments/{id}/costs`.
- Nao alterar o painel financeiro atual.

Saida esperada:

- quantidade de pedidos encontrados;
- quantidade de chamadas feitas;
- quantidade de pedidos completos;
- quantidade de pendencias de frete vendedor;
- quantidade de pendencias de desconto;
- status final do teste.

## Canario 2 — fila lenta de pendencias

Escopo:

- pegar poucas pendencias criadas no Canario 1;
- processar 1 por vez;
- limite duro de chamadas por ciclo;
- parar no primeiro 429;
- gravar sucesso/erro por pendencia.

## Status funcional dos dados

Um pedido pode estar em:

- `base_imported`: veio do `/orders/search`;
- `pending_seller_shipping`: falta frete vendedor;
- `pending_discount`: tem tag de desconto;
- `pending_shipping_cost`: precisa refinamento de frete comprador/Flex/loyal;
- `blocked_rate_limit`: processamento pausado por 429;
- `enriched`: pendencias principais processadas;
- `failed`: erro nao recuperado.

## Regra de seguranca

O canario deve ficar isolado em tabelas proprias. Ele nao deve gravar pedido parcial no cache usado pelo painel ate validarmos a regra financeira.

## Criterio de sucesso

Canario 1 passa se:

- `/orders/search` retorna pedidos do dia;
- nao gera 429;
- cria pendencias sem chamar endpoints de enriquecimento.

Canario 2 passa se:

- processa pendencias sem rajada;
- para imediatamente no primeiro 429;
- registra quantas chamadas foram feitas antes de parar.

## Criterio de bloqueio

Se o canario tomar 429 em `/orders/search` puro, nao prosseguir para shipments. A causa precisa ser investigada como cota/app/IP/endpoints antes de qualquer enriquecimento.

Se o canario tomar 429 em poucas chamadas de shipment, manter fila pausada e reduzir orcamento/ritmo antes de novo teste.

