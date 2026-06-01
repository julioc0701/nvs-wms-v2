# 09 — Frete (custo do vendedor) e Faturamento em lote

Fontes: FAQ `/pt_br/mercado-envios-custos-e-cotacoes` e `/pt_br/faturamento-billing-info` (05/05/2026). Destilado.

## Frete do VENDEDOR (o número que falta numa chamada) — é POR PEDIDO
- Fonte autoritativa: **`GET /shipments/{id}/costs`** → **`senders[].cost`** = o que foi cobrado do **vendedor**; **`receiver.cost`** = o que o **comprador** pagou.
- `senders[].cost == 0` → vendedor não foi cobrado. `receiver.cost == 0` → comprador não pagou.
- `promoted_amount`/`save` = informativos (subsídio), NÃO usar como base de faturamento.
- ⚠️ Nosso `calc.py` usa `shipping_option.cost`/`list_cost`; a doc recomenda **`senders[].cost`** pra conciliação. Possível ajuste de precisão (validar — o Excel bateu 100% nos casos testados, mas senders[].cost é o oficial).
- **Não há multiget de shipments documentado.** O frete do vendedor é **1 chamada `/shipments/{id}/costs` por pedido** → é a RAJADA atual.

## Faturamento em LOTE (o candidato pra eliminar a rajada)
- A doc confirma: existem **"endpoints de faturamento/billing POR PERÍODOS"** (Relatórios de Faturamento / Pagamentos) pra detalhe de impostos/descontos/charges. Pra breakdown completo às vezes **combina** billing-por-período + `/shipments/{id}/costs`.
- → **Candidato pra pegar frete/charges em LOTE = Relatórios de Faturamento / Relatórios de Pagamentos** (1 relatório por período com line items por pedido). A página "Relatórios de Faturamento" tem o endpoint exato (não lido limpo ainda — testar local).
- Não confundir com `billing_info` (legado depreciado → novo `/orders/billing-info/{site_id}/{billing_info_id}`): isso é **dado FISCAL do comprador** (nota fiscal), NÃO frete.

## Implicação pro redesenho
- 1 chamada `/orders/search` (50 pedidos) já traz tarifa + frete comprador + valores + status. Só o **frete vendedor** falta.
- Se o **Relatório de Faturamento/Pagamentos por período** trouxer o frete vendedor por pedido em lote → robô faz ~1 busca + 1 relatório por período em vez de centenas de `/shipments`. **Resolve a rajada (CloudFront).**
- Plano B (se não houver lote): buscar `/shipments/{id}/costs` só dos pedidos NOVOS, devagar/espalhado, com circuit-breaker duro no 429. Ver [[06-rate-limit-429-faq]].
